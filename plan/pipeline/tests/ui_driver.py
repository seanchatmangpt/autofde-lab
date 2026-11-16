"""Chicago-style (state-based, zero-mock) browser test for console.py.

A real `streamlit run console.py` subprocess on a fresh PLAN_STORE, a real Chromium via Python
Playwright, every symbol/rate/date/byte drawn at run time inside the TOML envelopes. Assertions
are on observable state: events.ndjson, the compiled PDDL shown by the UI, planner NO PLAN text,
and the exact ledger output."""
import contextlib
import hashlib
import math
import os
import random
import re
import shutil
import signal
import socket
import string
import subprocess
import sys
import time
import tomllib
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

from enterprise_pipeline import staged, store

ROOT = Path(__file__).resolve().parents[2]
CFG = tomllib.loads((Path(__file__).resolve().parent / "ui_envelopes.toml").read_text())
UI, VIEWS, ORACLE = CFG["ui"], CFG["views"], CFG["oracles"]


# ---------------------------------------------------------------- bounded polls (deadline, not count)
def poll(pred, timeout_ms, what):
    deadline = time.monotonic() + timeout_ms / 1000.0
    while True:
        v = pred()
        if v:
            return v
        if time.monotonic() >= deadline:
            raise TimeoutError(f"poll timed out: {what}")
        time.sleep(0.05)  # SLEEP-CLASS: POLL-STEP (bounded by monotonic deadline)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def port_open(port) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


# ---------------------------------------------------------------- world generation from envelopes
def gen_world(rng: random.Random) -> dict:
    n = CFG["generators"]["symbol_length"]
    used = set()

    def sym():
        while True:
            s = rng.choice(string.ascii_lowercase) + "".join(
                rng.choices(string.ascii_lowercase + string.digits, k=n - 1))
            if s not in used:
                used.add(s)
                return s

    e, t = CFG["bounds"]["economics"], CFG["bounds"]["temporal"]
    prov_rate = rng.randint(e["provider_rate_min_cents"], e["provider_rate_max_cents"])
    cli_rate = prov_rate + rng.randint(e["margin_spread_min_cents"], e["margin_spread_max_cents"])
    quoted = rng.randint(t["quoted_duration_min_floor"], t["quoted_duration_min_ceil"])
    mult = rng.randint(e["nte_headroom_multiplier_min"], e["nte_headroom_multiplier_max"])
    onsite = rng.randint(t["onsite_sla_min_floor"], t["onsite_sla_min_ceil"])
    complete = onsite + rng.randint(t["complete_sla_spread_min"], t["complete_sla_spread_max"])
    expiry = date.today() + timedelta(days=rng.randint(t["doc_valid_future_days_min"],
                                                       t["doc_valid_future_days_max"]))
    keys = ("ent dba ss4 w9e trade sub state prio cli site asset coord prov prov2 w9p con coi lic "
            "wo wotype bef aft tag").split()
    w = {k: sym() for k in keys}
    assert cli_rate > prov_rate and complete > onsite
    nbytes = t["upload_bytes_size"]
    w.update(
        channel=rng.choice(store.domain_constants("delivery_channel")),
        client_kind=rng.choice([k for k in store.subtypes("client") if k != "secondary_client"]),
        provider_kind=rng.choice(store.subtypes("provider")),
        wo_kind=rng.choice(store.subtypes("work_order")),
        terms=rng.randint(e["payment_terms_days_min"], e["payment_terms_days_max"]),
        prov_rate=prov_rate, cli_rate=cli_rate, quoted=quoted,
        nte=max(cli_rate * mult, math.ceil(quoted * cli_rate / 60) + prov_rate),
        onsite=onsite, complete=complete, expiry=expiry,
        bef_bytes=rng.randbytes(nbytes), aft_bytes=rng.randbytes(nbytes), tag_bytes=rng.randbytes(nbytes))
    return w


# ---------------------------------------------------------------- live server
@contextlib.contextmanager
def live_server(tmp_path):
    port = free_port()
    sf = tmp_path / "events.ndjson"
    env = {**os.environ, "PLAN_STORE": str(sf), "TMPDIR": str(tmp_path),
           "PYTHONPATH": str(ROOT / "pipeline")}
    log = (tmp_path / "streamlit.log").open("w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "console.py"), "--server.port", str(port),
         "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        poll(lambda: port_open(port), CFG["server"]["startup_timeout_ms"], "streamlit port")
        yield {"url": f"http://127.0.0.1:{port}", "store": sf, "tmp": tmp_path}
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=20)


def events(sf):
    return store.read(sf)


# ---------------------------------------------------------------- ARIA helpers
def idle(page: Page):
    """Streamlit exposes its script state for tests; act only while no rerun is in flight."""
    expect(page.locator("[data-testid='stApp']")).to_have_attribute(
        "data-test-script-state", "notRunning", timeout=CFG["server"]["solver_timeout_ms"])


def goto_view(page: Page, label: str):
    page.get_by_test_id("stSidebar").get_by_text(label, exact=True).click()
    expect(page.get_by_role("heading", name=label)).to_be_visible(timeout=CFG["server"]["step_timeout_ms"])
    idle(page)


def form_box(page: Page, heading: str):
    strong = page.locator("strong", has_text=re.compile(rf"^{re.escape(heading)}$"))
    return page.locator("[data-testid='stForm']").filter(has=strong).first


def button_form(page: Page, button: str):
    return page.locator("[data-testid='stForm']").filter(
        has=page.get_by_role("button", name=button, exact=True)).first


CHOOSE_LOG: list = []  # (label, option, reason) for every bounded open-list retry


def _open_list(page, sel, box, option, window_ms):
    """One attempt: focus, clear, type, verify the typed text landed, wait for the option."""
    sel.scroll_into_view_if_needed()
    box.click()
    box.focus()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    page.keyboard.type(option)
    if box.input_value() != option:
        return f"typed text not retained: {box.input_value()!r}"
    try:
        expect(page.get_by_role("option", name=option, exact=True)).to_have_count(1, timeout=window_ms)
    except AssertionError:
        return "option list did not show exactly one match"
    return None


def choose(scope, page: Page, label: str, option: str):
    # get_by_label stops resolving once a sibling select holds a value, so address the select by
    # its visible label text inside Streamlit's selectbox container
    idle(page)
    sel = scope.locator("[data-testid='stSelectbox']").filter(
        has=page.get_by_text(label, exact=True)).first
    box = sel.locator("input").first.element_handle()  # stable handle: label text moves while open
    deadline = time.monotonic() + CFG["server"]["step_timeout_ms"] / 1000.0
    window = CFG["server"]["open_window_ms"]
    while True:
        reason = _open_list(page, sel, box, option, window)
        if reason is None:
            break
        CHOOSE_LOG.append((label, option, reason))
        if time.monotonic() >= deadline:
            raise TimeoutError(f"select {label!r}: could not open list for {option!r}: {CHOOSE_LOG[-3:]}")
        page.keyboard.press("Escape")
        idle(page)
    if page.get_by_role("option").count() == 1:
        page.keyboard.press("Enter")  # keyboard needs no stable click target
    else:
        page.get_by_role("option", name=option, exact=True).click(force=True)
    idle(page)
    poll(lambda: sel.locator("input").first.get_attribute("value") == option or sel.get_by_role("combobox").input_value() == option, CFG["server"]["step_timeout_ms"], f"select {label!r} did not display {option!r}")  # displayed value


def fill_date(box, label: str, d: date):
    """Streamlit's date field is a group of contenteditable spinbuttons (year/month/day)."""
    group = box.get_by_label(label, exact=True)
    for seg, text in (("year", f"{d.year:04d}"), ("month", f"{d.month:02d}"), ("day", f"{d.day:02d}")):
        sp = group.get_by_role("spinbutton", name=re.compile(rf"^{seg},"))
        sp.click()
        sp.press_sequentially(text)
        expect(sp).not_to_have_attribute("aria-valuetext", "Empty", timeout=CFG["server"]["step_timeout_ms"])


def submit(page, sf, box, kind, button=None, expect_payload=None):
    """Click submit; the oracle is the disk log growing by exactly one event of `kind`."""
    n0 = len(events(sf))
    box.get_by_role("button", name=button or UI["submit_event"], exact=True).click()
    poll(lambda: len(events(sf)) > n0, CFG["server"]["step_timeout_ms"], f"event {kind} not recorded")
    evs = events(sf)
    assert len(evs) == n0 + 1 and evs[-1]["kind"] == kind, (kind, evs[-1])
    for k, v in (expect_payload or {}).items():
        assert evs[-1]["payload"].get(k) == v, (kind, k, evs[-1]["payload"])
    # the rerun that follows the write must finish before the next widget is touched
    expect(page.get_by_text(f"recorded seq {n0 + 1}: {kind}").first).to_be_visible(
        timeout=CFG["server"]["step_timeout_ms"])
    idle(page)


def upload(page, sf, wo, mtype, name, data):
    box = button_form(page, UI["submit_media"])
    choose(box, page, "wo", wo)
    choose(box, page, "media_type", mtype)
    box.get_by_label("name", exact=True).fill(name)
    box.locator("input[type='file']").set_input_files(
        {"name": f"{name}.bin", "mimeType": "application/octet-stream", "buffer": data})
    expect(box.get_by_text(f"{name}.bin")).to_be_visible(timeout=CFG["server"]["step_timeout_ms"])
    submit(page, sf, box, "media", UI["submit_media"],
           {"sha256": hashlib.sha256(data).hexdigest(), "media_type": mtype})


def compile_plan(page, wo):
    choose(page, page, UI["work_order_select"], wo)
    page.get_by_role("button", name=UI["compile_button"], exact=True).click()


def new_context(pw, tmp, headed):
    browser = pw.chromium.launch(headless=not headed, slow_mo=150 if headed else 0)
    ctx = browser.new_context(viewport={"width": 1440, "height": 960})
    ctx.tracing.start(screenshots=True, snapshots=True)
    return browser, ctx


def drive_ui_journey(url, cfg, store_file, include_model_tag: bool, seed=None, tmp=None, headed=False) -> dict:
    """Drive the full blank-slate to settlement journey through the real UI; returns the world dict."""
    seed = int.from_bytes(os.urandom(4), "big") if seed is None else seed
    print(f"seed={seed}")
    w = gen_world(random.Random(seed))
    w["seed"] = seed
    sf = Path(store_file)
    tmp = Path(tmp) if tmp else sf.parent
    step_ms, solve_ms = cfg["server"]["step_timeout_ms"], cfg["server"]["solver_timeout_ms"]
    with sync_playwright() as pw:
        browser, ctx = new_context(pw, tmp, headed)
        page = ctx.new_page()
        try:
            page.goto(url)
            S = lambda box, kind, **kw: submit(page, sf, box, kind, **kw)

            # Super Admin
            goto_view(page, VIEWS["super_admin"])
            b = form_box(page, "entity")
            b.get_by_label("name", exact=True).fill(w["ent"])
            b.get_by_label("dba", exact=True).fill(w["dba"])
            S(b, "entity", expect_payload={"name": w["ent"], "dba": w["dba"]})
            for dt, nm in (("ss4_doc", w["ss4"]), ("w9_doc", w["w9e"])):
                b = form_box(page, "entity_doc")
                choose(b, page, "doc_type", dt)
                b.get_by_label("name", exact=True).fill(nm)
                S(b, "entity_doc", expect_payload={"doc_type": dt, "name": nm})
            S(form_box(page, "templates_bound"), "templates_bound")
            for ty, nm in (("trade", w["trade"]), ("sub_trade", w["sub"]),
                           ("state_jurisdiction", w["state"]), ("priority_tier", w["prio"])):
                b = form_box(page, "taxonomy")
                choose(b, page, "type", ty)
                b.get_by_label("name", exact=True).fill(nm)
                S(b, "taxonomy", expect_payload={"type": ty, "name": nm})
            b = form_box(page, "client")
            b.get_by_label("name", exact=True).fill(w["cli"])
            choose(b, page, "kind", w["client_kind"])
            choose(b, page, "delivery_mode", w["channel"])
            b.get_by_label("payment_terms_days", exact=True).fill(str(w["terms"]))
            S(b, "client", expect_payload={"name": w["cli"], "payment_terms_days": w["terms"]})
            b = form_box(page, "client_rate")
            choose(b, page, "client", w["cli"])
            choose(b, page, "trade", w["trade"])
            b.get_by_label("cents", exact=True).fill(str(w["cli_rate"]))
            S(b, "client_rate", expect_payload={"cents": w["cli_rate"]})
            b = form_box(page, "site")
            b.get_by_label("name", exact=True).fill(w["site"])
            choose(b, page, "client", w["cli"])
            choose(b, page, "state", w["state"])
            choose(b, page, "territory_client", w["cli"])
            S(b, "site", expect_payload={"name": w["site"]})
            b = form_box(page, "asset")
            b.get_by_label("name", exact=True).fill(w["asset"])
            choose(b, page, "site", w["site"])
            S(b, "asset", expect_payload={"name": w["asset"]})
            b = form_box(page, "coordinator")
            b.get_by_label("name", exact=True).fill(w["coord"])
            S(b, "coordinator", expect_payload={"name": w["coord"]})

            # Alignment: one eligible provider, one with no recorded documents (negative control)
            goto_view(page, VIEWS["alignment"])
            for pv in (w["prov"], w["prov2"]):
                b = form_box(page, "provider")
                b.get_by_label("name", exact=True).fill(pv)
                choose(b, page, "kind", w["provider_kind"])
                S(b, "provider", expect_payload={"name": pv})
            for dt, nm, exp in (("w9_doc", w["w9p"], None), ("contract_doc", w["con"], None),
                                ("coi_doc", w["coi"], w["expiry"]), ("license_doc", w["lic"], w["expiry"])):
                b = form_box(page, "provider_doc")
                choose(b, page, "provider", w["prov"])
                choose(b, page, "doc_type", dt)
                b.get_by_label("name", exact=True).fill(nm)
                b.get_by_text("valid", exact=True).click()
                if exp:
                    fill_date(b, "expiry_date", exp)
                S(b, "provider_doc", expect_payload={"name": nm, "valid": True})
            b = form_box(page, "provider_approval")
            choose(b, page, "provider", w["prov"]); choose(b, page, "trade", w["trade"])
            choose(b, page, "sub_trade", w["sub"])
            S(b, "provider_approval")
            b = form_box(page, "provider_rate")
            choose(b, page, "provider", w["prov"]); choose(b, page, "trade", w["trade"])
            b.get_by_label("cents", exact=True).fill(str(w["prov_rate"]))
            S(b, "provider_rate", expect_payload={"cents": w["prov_rate"]})
            b = form_box(page, "provider_rate_approved")
            choose(b, page, "provider", w["prov"]); choose(b, page, "trade", w["trade"])
            S(b, "provider_rate_approved")
            b = form_box(page, "device_attested")
            choose(b, page, "provider", w["prov"])
            S(b, "device_attested")

            # Coordinator: work order requiring a part replacement
            goto_view(page, VIEWS["coordinator"])
            b = form_box(page, "work_order")
            b.get_by_label("name", exact=True).fill(w["wo"])
            choose(b, page, "kind", w["wo_kind"])
            b.get_by_label("wo_type", exact=True).fill(w["wotype"])
            for lab, val in (("client", w["cli"]), ("site", w["site"]), ("trade", w["trade"]),
                             ("sub_trade", w["sub"]), ("priority", w["prio"]),
                             ("coordinator", w["coord"]), ("part_asset", w["asset"])):
                choose(b, page, lab, val)
            b.get_by_label("nte_cents", exact=True).fill(str(w["nte"]))
            b.get_by_label("onsite_sla_min", exact=True).fill(str(w["onsite"]))
            b.get_by_label("complete_sla_min", exact=True).fill(str(w["complete"]))
            S(b, "work_order", expect_payload={"name": w["wo"], "nte_cents": w["nte"]})

            # Stage 1: UI-shown problem has no future facts; planner dispatches
            goto_view(page, VIEWS["compile"])
            compile_plan(page, w["wo"])
            expect(page.get_by_text(ORACLE["stage1_required_action"]).first).to_be_visible(timeout=solve_ms)
            page.get_by_text(UI["problem_expander"]).click()
            problem = page.locator("[data-testid='stExpander'] [data-testid='stCode']").first.inner_text()
            for bad in ORACLE["stage1_forbidden_predicates"]:
                assert bad not in problem, f"stage-1 problem leaked {bad}"

            # Dispatch: refused for the provider with no documents, accepted for the eligible one
            goto_view(page, VIEWS["coordinator"])
            b = button_form(page, UI["submit_dispatch"])
            choose(b, page, "wo", w["wo"]); choose(b, page, "provider", w["prov2"])
            n0 = len(events(sf))
            b.get_by_role("button", name=UI["submit_dispatch"], exact=True).click()
            expect(page.get_by_text(UI["refusal_marker"], exact=False).first).to_be_visible(timeout=step_ms)
            assert len(events(sf)) == n0, "refused dispatch still wrote an event"
            b = form_box(page, "proposal_quote")
            choose(b, page, "wo", w["wo"])
            b.get_by_label("minutes", exact=True).fill(str(w["quoted"]))
            S(b, "proposal_quote", expect_payload={"minutes": w["quoted"]})
            b = button_form(page, UI["submit_dispatch"])
            choose(b, page, "wo", w["wo"]); choose(b, page, "provider", w["prov"])
            S(b, "dispatch", button=UI["submit_dispatch"], expect_payload={"provider": w["prov"]})

            # Field: geofence, check-in, check-out, client attest, before/after (model tag withheld)
            goto_view(page, VIEWS["field_qa"])
            for kind in ("geofence_attest", "checkin", "checkout"):
                b = form_box(page, kind)
                choose(b, page, "wo", w["wo"])
                S(b, kind, expect_payload={"wo": w["wo"]})
            b = form_box(page, "client_attest")
            choose(b, page, "wo", w["wo"])
            b.get_by_label("minutes", exact=True).fill(str(w["quoted"]))
            S(b, "client_attest", expect_payload={"minutes": w["quoted"]})
            upload(page, sf, w["wo"], "before_media", w["bef"], w["bef_bytes"])
            upload(page, sf, w["wo"], "after_media", w["aft"], w["aft_bytes"])

            # Anti-vacuity: no model tag -> real planner refusal
            goto_view(page, VIEWS["compile"])
            compile_plan(page, w["wo"])
            expect(page.get_by_text(UI["no_plan_marker"]).first).to_be_visible(timeout=solve_ms)
            pre_tag_events = list(events(sf))
            if not include_model_tag:
                return w

            # Upload the tag: refusal flips to a plan with invoice and payout; ledger exact
            goto_view(page, VIEWS["field_qa"])
            upload(page, sf, w["wo"], "model_tag_photo", w["tag"], w["tag_bytes"])
            goto_view(page, VIEWS["compile"])
            compile_plan(page, w["wo"])
            for act in ORACLE["stage2_required_actions"]:
                expect(page.get_by_text(act).first).to_be_visible(timeout=solve_ms)
            page.get_by_role("button", name=UI["settle_button"], exact=True).click()
            expect(page.get_by_text(UI["ledger_metric"])).to_be_visible(timeout=step_ms)
            state = store.reduce(store.read(sf))
            mins = staged.internal_minutes(state["work_orders"][0]["visit"])
            ar = math.ceil(w["quoted"] * w["cli_rate"] / 60)
            ap = math.ceil(mins * w["prov_rate"] / 60)
            ledger = page.get_by_test_id("stCode").last
            expect(ledger).to_contain_text(str(ar))
            expect(ledger).to_contain_text(str(ap))

            # The flip is caused by that single upload: same log minus the tag event still refuses
            terminal = set(ORACLE["terminal_event_kinds"])  # recorded by console after solver success
            minus = [e for e in store.read(sf)
                     if e["payload"].get("name") != w["tag"] and e["kind"] not in terminal]
            assert len(minus) == len([e for e in pre_tag_events if e["kind"] not in terminal])
            alt = tmp / "minus_tag.ndjson"
            alt.write_text("".join(__import__("json").dumps(e, sort_keys=True) + "\n" for e in minus))
            r = staged.plan_wo(store.reduce(store.read(alt)), w["wo"])
            assert r["rc"] == ORACLE["stage2_refusal_exit_code"], r["out"]
        except BaseException:
            page.screenshot(path=str(tmp / "failure.png"), full_page=True)
            (tmp / "failure_options.txt").write_text(
                repr([(o.inner_text(), o.is_visible()) for o in page.get_by_role("option").all()])
                + "\n" + repr(page.locator("[role='listbox']").count())
                + "\n" + repr(CHOOSE_LOG)
                + "\n" + repr(page.locator("input[role='combobox']").evaluate_all(
                    "els => els.map(e => [e.getAttribute('aria-expanded'), e.value, e.getAttribute('aria-label'), e === document.activeElement])")))
            print(f"FAILED seed={seed} artifacts={tmp}")
            raise
        finally:
            ctx.tracing.stop(path=str(tmp / "chicago_visual_trace.zip"))
            print(f"trace={tmp / 'chicago_visual_trace.zip'} retries={len(CHOOSE_LOG)}")
            browser.close()
    return w
