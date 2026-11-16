"""Interpret a factory-generated plan (jtbd_factories.Scenario.steps) through the real UI.

Playwright only clicks. Each step's expected outcome is checked against observable state (the
append-only event log, planner and ledger text in the DOM). This module never writes events."""
from enterprise_pipeline import ocel_bridge as obt
import math
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

import ui_driver as ud
from enterprise_pipeline import staged, store
from jtbd_factories import EXPECT

CFG, UI, VIEWS, ORACLE = ud.CFG, ud.UI, ud.VIEWS, ud.ORACLE
STEP_MS, SOLVE_MS = CFG["server"]["step_timeout_ms"], CFG["server"]["solver_timeout_ms"]


def _kinds(sf):
    return [e["kind"] for e in ud.events(sf)]


def _fill(box, page, fields):
    for label, widget, value in fields:
        if widget in ("text", "number"):
            box.get_by_label(label, exact=True).fill(str(value))
        elif widget == "select":
            ud.choose(box, page, label, value)
        elif widget == "date":
            ud.fill_date(box, label, value)
        elif widget == "list":
            box.get_by_label(f"{label} (comma separated)", exact=True).fill(",".join(value) if isinstance(value, (list, tuple)) else str(value))
        elif widget == "check":
            box.get_by_text(label, exact=True).click()


def _payload(fields):
    return {l: (int(v) if w == "number" else v) for l, w, v in fields if w in ("text", "number", "select")}


def _terminal_appeared(sf, kind, n_before):
    return ud.poll(lambda: _kinds(sf).count(kind) > n_before, SOLVE_MS, f"terminal event {kind}")


def run_plan(url, sc, store_file, tmp, headed=False) -> dict:
    """Run every step of `sc.steps`; raises AssertionError naming the step whose outcome differed."""
    sf, tmp = Path(store_file), Path(tmp)
    w = sc.world
    with sync_playwright() as pw:
        browser, ctx = ud.new_context(pw, tmp, headed)
        page = ctx.new_page()
        current = None
        done = 0
        try:
            page.goto(url)
            for i, st in enumerate(sc.steps):
                where = f"{sc.name} step {i} {st.action}:{st.heading or st.kind}"
                view = {"form": st.view, "dispatch": st.view, "upload": st.view,
                        "compile": VIEWS["compile"], "settle": VIEWS["compile"]}[st.action]
                if view != current:
                    ud.goto_view(page, view)
                    current = view
                if st.action == "form":
                    box = ud.form_box(page, st.heading)
                    _fill(box, page, st.fields)
                    ud.submit(page, sf, box, st.kind, expect_payload=_payload(st.fields))
                elif st.action == "dispatch":
                    box = ud.button_form(page, st.heading)
                    _fill(box, page, st.fields)
                    if st.expect == EXPECT["recorded"]:
                        ud.submit(page, sf, box, "dispatch", button=st.heading,
                                  expect_payload={"provider": dict((l, v) for l, _, v in st.fields)["provider"]})
                    else:
                        n0 = len(ud.events(sf))
                        box.get_by_role("button", name=st.heading, exact=True).click()
                        expect(page.get_by_text(UI["refusal_marker"], exact=False).first).to_be_visible(timeout=STEP_MS)
                        assert len(ud.events(sf)) == n0, f"{where}: refused dispatch wrote an event"
                elif st.action == "upload":
                    f = {l: v for l, _, v in st.fields}
                    ud.upload(page, sf, f["wo"], st.heading, f["name"], st.data)
                elif st.action == "compile":
                    n0 = len(ud.events(sf))
                    terminal = "plan_dispatched" if st.stage == 1 else "plan_closed"
                    c0 = _kinds(sf).count(terminal)
                    ud.compile_plan(page, st.heading)
                    if st.expect == EXPECT["plan_ok"]:
                        needed = [ORACLE["stage1_required_action"]] if st.stage == 1 \
                            else ORACLE["stage2_required_actions"]
                        for act in needed:
                            expect(page.get_by_text(act).first).to_be_visible(timeout=SOLVE_MS)
                        if st.stage == 1:
                            page.get_by_text(UI["problem_expander"]).click()
                            problem = page.locator("[data-testid='stExpander'] [data-testid='stCode']").first.inner_text()
                            for bad in ORACLE["stage1_forbidden_predicates"]:
                                assert bad not in problem, f"{where}: stage-1 problem leaked {bad}"
                        _terminal_appeared(sf, terminal, c0)
                    else:
                        expect(page.get_by_text(UI["no_plan_marker"]).first).to_be_visible(timeout=SOLVE_MS)
                        assert _kinds(sf).count(terminal) == c0, f"{where}: refused plan wrote {terminal}"
                elif st.action == "settle":
                    c0 = _kinds(sf).count("ledger_settled")
                    wo_id = dict((l, v) for l, _, v in st.fields).get("wo")
                    if wo_id:
                        ud.choose(page, page, UI["work_order_select"], wo_id)
                    page.get_by_role("button", name=UI["settle_button"], exact=True).click()
                    expect(page.get_by_text(UI["ledger_metric"])).to_be_visible(timeout=STEP_MS)
                    ledger = page.get_by_test_id("stCode").last
                    if st.expect == EXPECT["ledger_ok"]:
                        _terminal_appeared(sf, "ledger_settled", c0)
                        state = store.reduce(store.read(sf))
                        wo_state = next((x for x in state["work_orders"] if x["id"] == wo_id), state["work_orders"][0])
                        visits = wo_state.get("visits") or [wo_state["visit"]]
                        mins = sum(staged.internal_minutes(v) or 0 for v in visits)
                        lg = w["ledger"][wo_id] if wo_id else w
                        ar = math.ceil(lg["attest"] * lg["cli_rate"] / 60)
                        ap = math.ceil(mins * lg["prov_rate"] / 60)
                        expect(ledger).to_contain_text(str(ar))
                        expect(ledger).to_contain_text(str(ap))
                    else:
                        expect(ledger).to_contain_text(UI["ledger_refusal_marker"])
                        assert _kinds(sf).count("ledger_settled") == c0, f"{where}: refused ledger wrote an event"
                done = i + 1
        except BaseException:
            page.screenshot(path=str(tmp / "failure.png"), full_page=True)
            print(f"FAILED plan={sc.name} step={done} artifacts={tmp}")
            raise
        finally:
            ctx.tracing.stop(path=str(tmp / "trace.zip"))
            browser.close()
    return {"plan": sc.name, "steps_done": done, "observed": obt.trace(sf), "intended": sc.intended}
