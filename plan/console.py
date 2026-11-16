# Ground-only console: every row is parsed from files under ROOT or emitted by a live subprocess.
# Panels read NOT EXECUTED until a subprocess has returned.

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "pipeline"))
from enterprise_pipeline import align, staged, store  # noqa: E402
try:  # B5 dials module is owned by another lane; panels read NOT EXECUTED until it exists
    from enterprise_pipeline import dials  # noqa: E402
except ImportError:
    dials = None
PLANNER_SH = ROOT / "planner" / "run.sh"
JUST_DIR = ROOT / "justfile.d"
NOT_RUN = "NOT EXECUTED"
LONG_TIMEOUT = 60 * 60

st.set_page_config(page_title="plan live solver console", layout="wide")


# ---------------------------------------------------------------- introspection
def parse_pddl_objects(text: str) -> pd.DataFrame:
    m = re.search(r"\(:objects(.*?)\)", text, re.S)
    if not m:
        return pd.DataFrame()
    rows = []
    for chunk in re.finditer(r"([^\-\n]+)-\s*([A-Za-z0-9_]+)", m.group(1)):
        for o in chunk.group(1).split():
            rows.append({"Object Symbol": o, "PDDL Type": chunk.group(2).strip()})
    return pd.DataFrame(rows)


def parse_pddl_fluents(text: str) -> list[dict]:
    rows = []
    for m in re.finditer(r"\(=\s*\(([^)]+)\)\s*([-+]?\d+(?:\.\d+)?)\)", text):
        val = float(m.group(2)) if "." in m.group(2) else int(m.group(2))
        rows.append({"fluent": m.group(1).strip(), "value": val, "raw": m.group(0)})
    return rows


def parse_pddl_init_facts(text: str) -> list[str]:
    m = re.search(r"\(:init(.*?)\)\s*\(:goal", text, re.S)
    if not m:
        return []
    body = re.sub(r";[^\n]*", "", m.group(1))
    facts = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("(") and not s.startswith("(=") and not s.startswith("(at "):
            facts.append(s)
    return facts


def parse_plan(out: str) -> pd.DataFrame:
    steps = []
    for line in out.splitlines():
        m = re.match(r"^\s*([\d.]+):\s*\(([^)]+)\)\s*\[([\d.]+)\]", line)
        if m:
            start, dur = float(m.group(1)), float(m.group(3))
            tokens = m.group(2).split()
            steps.append({
                "Seq": len(steps) + 1, "Start": start, "End": round(start + dur, 4),
                "Duration": dur, "Action": tokens[0],
                "Grounded Arguments": " ".join(tokens[1:]),
            })
    return pd.DataFrame(steps)


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


# ---------------------------------------------------------------- subprocess
def run_cmd(cmd: list[str], cwd: Path = ROOT, timeout: int | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or b"")
        partial = partial.decode() if isinstance(partial, bytes) else partial
        return -1, f"TIMEOUT after {timeout}s\n{partial}"
    return proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()


def run_just(mod: Path, recipe: str) -> tuple[int, str]:
    return run_cmd(["just", "--justfile", str(mod), recipe], timeout=LONG_TIMEOUT)


def just_recipes(mod: Path) -> list[str]:
    rc, out = run_cmd(["just", "--justfile", str(mod), "--summary"], timeout=LONG_TIMEOUT)
    return out.split() if rc == 0 else []


def run_planner(domain: Path, problem: Path) -> tuple[int, str]:
    return run_cmd(["bash", str(PLANNER_SH), str(domain), str(problem)], timeout=LONG_TIMEOUT)


# ---------------------------------------------------------------- result panels
def keep(key: str, rc: int, out: str) -> None:
    st.session_state[key] = (rc, out)


def panel(key: str, gantt: bool = False) -> None:
    res = st.session_state.get(key)
    if res is None:
        st.info(NOT_RUN)
        return
    rc, out = res
    st.metric("Exit code", rc)
    if gantt and rc == 0:
        plot_plan(parse_plan(out))
    st.code(out)


def plot_plan(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No timed action lines parsed from solver stdout.")
        return
    fig = px.bar(df, base="Start", x="Duration", y="Action", color="Action", orientation="h",
                 hover_data=["Seq", "Grounded Arguments", "Start", "End"])
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(showlegend=False, height=max(280, len(df) * 40))
    st.plotly_chart(fig, width="stretch")
    st.dataframe(df, width="stretch", hide_index=True)


def just_runner(mod_glob: str, key: str, label_prefix: str = "") -> None:
    """Pick recipe from the module's own --summary and run it live."""
    mods = sorted(JUST_DIR.glob(mod_glob)) if JUST_DIR.exists() else []
    if not mods:
        st.warning(f"No justfile module matches {mod_glob}.")
        return
    mod = st.selectbox("Justfile module", mods, format_func=lambda p: p.name, key=f"mod_{key}")
    recipes = just_recipes(mod)
    if not recipes:
        st.warning(f"`just --summary` returned no recipes for {mod.name}.")
        return
    recipe = st.selectbox("Recipe", recipes, key=f"rec_{key}")
    if st.button(f"{label_prefix}Run `{mod.name} {recipe}`", type="primary", key=f"btn_{key}"):
        with st.spinner(f"just --justfile {mod.name} {recipe}"):
            rc, out = run_just(mod, recipe)
        keep(key, rc, out)
    panel(key)


def lane_pddl_runner(lane: str) -> None:
    folder = ROOT / lane
    doms = sorted(p for p in folder.rglob("*domain*.pddl"))
    probs = sorted(p for p in folder.rglob("*.pddl") if p not in doms)
    if not doms or not probs:
        st.warning(f"No domain/problem PDDL under {lane}/.")
        return
    d = st.selectbox("Domain PDDL", doms, format_func=rel, key=f"dom_{lane}")
    p = st.selectbox("Problem PDDL", probs, format_func=rel, key=f"prob_{lane}")
    with st.expander("Raw problem PDDL on disk"):
        st.code(p.read_text())
    if st.button(f"Solve {p.name} with planner/run.sh", type="primary", key=f"solve_{lane}"):
        with st.spinner("planner/run.sh"):
            rc, out = run_planner(d, p)
        keep(f"plan_{lane}", rc, out)
    panel(f"plan_{lane}", gantt=True)


# ---------------------------------------------------------------- receipts
def read_lane_receipts() -> pd.DataFrame:
    d = ROOT / "receipts"
    rows = []
    for p in sorted(d.glob("*.md")) if d.exists() else []:
        lines = p.read_text().splitlines()
        line2 = lines[1] if len(lines) > 1 else ""
        ok = line2.lower().startswith("standing:")
        rows.append({
            "Lane": p.stem,
            "Standing (line 2)": line2.split(":", 1)[1].strip() if ok else "MALFORMED",
            "File": rel(p),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- sidebar
st.sidebar.title("plan solver console")
st.sidebar.caption(f"Workspace: `{ROOT}`")

VIEWS = [
    "1. Receipts and gates",
    "2. Regression fixtures (FIXTURE, test-only: spec/ + planner/)",
    "3. Dispatcher alignment (alignment/ + cpsat/)",
    "4. Enterprise JSON to PDDL pipeline (pipeline/)",
    "5. Preventive maintenance (pm/)",
    "6. ProcurePass parts and NTE (procurepass/)",
    "7. Replay executor and ledger (executor/ + ledger/)",
    "8. Adversarial courts (courts/)",
]
NEW = [
    "A. Super Admin",
    "B. Alignment",
    "C. Coordinator",
    "D. Field / QA / AR",
    "E. Compile and plan",
    "F. Event log",
    "G. Policy dials",
]
view = st.sidebar.radio("View", NEW + VIEWS)


def _people():
    try:
        return [p["id"] for p in store.reduce(store.read()).get("people", [])]
    except (store.Refused, KeyError, ValueError):
        return []


ACTING = st.sidebar.selectbox("Acting as", _people(), index=None,
                              placeholder="select person" if _people() else "no people yet",
                              key="acting_as")

# ---------------------------------------------------------------- avatar forms (store-backed)
def cur():
    return store.reduce(store.read())


def ids(coll):
    return [x["id"] for x in cur().get(coll, [])]


def assets_all():
    return [a for s_ in cur().get("sites", []) for a in s_["assets"]]


def pick(label, options, key):
    return st.selectbox(label, options, index=None,
                        placeholder="select" if options else "none yet", key=key)


def record(avatar, kind, payload):
    payload = {k: v for k, v in payload.items() if v not in (None, "", [])}
    if ACTING and kind not in ("person", "role_grant"):
        avatar = ACTING
    try:
        ev = store.append(avatar, kind, payload)
        st.success(f"recorded seq {ev['seq']}: {kind}")
    except store.Refused as e:
        st.error(str(e))
    except (ValueError, KeyError) as e:
        st.error(f"REFUSED[{type(e).__name__}: {e}]")


def form(avatar, kind, fields):
    """fields: [(name, widget, options-or-None)]; every widget starts empty."""
    with st.form(f"{avatar}_{kind}", clear_on_submit=True):
        st.markdown(f"**{kind}**")
        vals = {}
        for name, w, opts in fields:
            k = f"{avatar}_{kind}_{name}"
            if w == "text":
                vals[name] = st.text_input(name, key=k)
            elif w == "int":
                vals[name] = st.number_input(name, value=None, step=1, key=k)
            elif w == "select":
                vals[name] = pick(name, opts() if callable(opts) else opts, k)
            elif w == "bool":
                vals[name] = st.checkbox(name, key=k)
            elif w == "date":
                d = st.date_input(name, value=None, key=k)
                vals[name] = d.isoformat() if d else None
            elif w == "list":
                raw = st.text_input(f"{name} (comma separated)", key=k)
                vals[name] = [x.strip() for x in raw.split(",") if x.strip()]
        if st.form_submit_button("Record event"):
            for k, v in vals.items():
                if isinstance(v, float) and v == int(v):
                    vals[k] = int(v)
            record(avatar, kind, vals)


TYPE_DOC = lambda: store.subtypes("doc_slot")
TYPE_MEDIA = lambda: store.subtypes("media_artifact")
STAGE_WOS = lambda: ids("work_orders")

if view in NEW:
    st.header(view)
    st.caption(f"Store: `{store.store_path()}` (append-only; created by the first recorded event)")
    if view == NEW[0]:
        ENT = lambda: ids("entities")
        form("admin", "entity", [("name", "text", None), ("dba", "text", None),
                                 ("dbas", "list", None)])
        form("admin", "entity_dba", [("entity", "select", ENT), ("dba", "text", None)])
        form("admin", "entity_doc", [("entity", "select", ENT),
                                     ("doc_type", "select", TYPE_DOC), ("name", "text", None)])
        form("admin", "templates_bound", [("entity", "select", ENT)])
        form("admin", "person", [("name", "text", None), ("display", "text", None)])
        form("admin", "role_grant", [("person", "select", _people),
                                     ("role", "select", lambda: ["super_user", "entity_lead",
                                                                 "team_lead", "coordinator",
                                                                 "provider_ops"]),
                                     ("entity", "select", ENT),
                                     ("client", "select", lambda: ids("clients"))])
        st.subheader("People and roles")
        people = cur().get("people", [])
        if people:
            st.dataframe(pd.DataFrame([{"person": p["id"], "roles": str(p.get("roles", []))}
                                       for p in people]), width="stretch", hide_index=True)
        else:
            st.info(NOT_RUN)
        form("admin", "taxonomy", [("type", "select", lambda: store.subtypes("taxonomy")),
                                   ("name", "text", None)])
        form("admin", "client", [("name", "text", None),
                                 ("entity", "select", lambda: ids("entities")),
                                 ("quick_add", "bool", None),
                                 ("kind", "select", lambda: store.subtypes("client")),
                                 ("parent", "select", lambda: ids("clients")),
                                 ("delivery_mode", "select",
                                  lambda: store.domain_constants("delivery_channel")),
                                 ("payment_terms_days", "int", None)])
        form("admin", "client_rate", [("client", "select", lambda: ids("clients")),
                                      ("trade", "select", lambda: cur()["trades"]),
                                      ("cents", "int", None)])
        form("admin", "site", [("name", "text", None),
                               ("client", "select", lambda: ids("clients")),
                               ("state", "select", lambda: cur()["states"]),
                               ("territory_client", "select", lambda: ids("clients"))])
        form("admin", "asset", [("name", "text", None), ("site", "select", lambda: ids("sites"))])
        form("admin", "coordinator", [("name", "text", None)])
    elif view == NEW[1]:
        P = lambda: ids("providers")
        T = lambda: cur()["trades"]
        form("align", "provider", [("name", "text", None),
                                   ("entity", "select", lambda: ids("entities")),
                                   ("kind", "select", lambda: store.subtypes("provider"))])
        form("align", "provider_doc", [("provider", "select", P), ("doc_type", "select", TYPE_DOC),
                                       ("name", "text", None), ("valid", "bool", None),
                                       ("expiry_date", "date", None)])
        form("align", "provider_approval", [("provider", "select", P), ("trade", "select", T),
                                            ("sub_trade", "select", lambda: cur()["sub_trades"])])
        form("align", "provider_rate", [("provider", "select", P), ("trade", "select", T),
                                        ("cents", "int", None)])
        form("align", "provider_rate_approved", [("provider", "select", P), ("trade", "select", T)])
        form("align", "provider_rank", [("provider", "select", P), ("trade", "select", T),
                                        ("rank", "int", None)])
        form("align", "provider_blacklist", [("provider", "select", P)])
        form("align", "device_attested", [("provider", "select", P)])
        form("align", "provider_filter", [("provider", "select", P),
                                          ("dim", "select", lambda: align.DIMS),
                                          ("mode", "select", lambda: ["inc", "exc"]),
                                          ("values", "list", None)])
    elif view == NEW[2]:
        form("coord", "work_order", [
            ("name", "text", None), ("kind", "select", lambda: store.subtypes("work_order")),
            ("wo_type", "text", None), ("client", "select", lambda: ids("clients")),
            ("site", "select", lambda: ids("sites")), ("trade", "select", lambda: cur()["trades"]),
            ("sub_trade", "select", lambda: cur()["sub_trades"]),
            ("priority", "select", lambda: cur()["priorities"]),
            ("coordinator", "select", lambda: ids("coordinators")),
            ("nte_cents", "int", None), ("onsite_sla_min", "int", None),
            ("complete_sla_min", "int", None),
            ("part_asset", "select", assets_all),
            ("link_kind", "select", lambda: ["change_order", "recall"]),
            ("parent_wo", "select", STAGE_WOS)])
        form("coord", "visit_open", [("wo", "select", STAGE_WOS)])
        form("coord", "required_media", [("wo", "select", STAGE_WOS),
                                         ("media_type", "select", TYPE_MEDIA)])
        st.subheader("Territory (flag, sales notice, waiver)")
        form("coord", "territory_flag", [("wo", "select", STAGE_WOS),
                                         ("client", "select", lambda: ids("clients")),
                                         ("site", "select", lambda: ids("sites"))])
        form("coord", "sales_rep_notified", [("wo", "select", STAGE_WOS),
                                             ("client", "select", lambda: ids("clients")),
                                             ("rep", "text", None)])
        form("coord", "territory_waiver", [("wo", "select", STAGE_WOS),
                                           ("authority", "text", None)])
        st.subheader("Overrides and change order")
        form("coord", "change_order_approved", [("wo", "select", STAGE_WOS),
                                                ("new_nte_cents", "int", None),
                                                ("authority", "text", None)])
        form("coord", "nte_override_receipt", [("wo", "select", STAGE_WOS),
                                               ("id", "text", None), ("reason", "text", None)])
        form("coord", "dispatch_override", [("wo", "select", STAGE_WOS),
                                            ("provider", "select", lambda: ids("providers")),
                                            ("authority", "text", None),
                                            ("reason", "text", None)])
        form("coord", "proposal_quote", [("wo", "select", STAGE_WOS), ("minutes", "int", None)])
        st.subheader("Dispatch (refused unless the real MiniZinc alignment says eligible)")
        with st.form("coord_dispatch", clear_on_submit=True):
            wo_id = pick("wo", STAGE_WOS(), "coord_dispatch_wo")
            prov_id = pick("provider", ids("providers"), "coord_dispatch_provider")
            if st.form_submit_button("Record dispatch"):
                if not wo_id or not prov_id:
                    st.error("MISSING[wo/provider]")
                else:
                    state = cur()
                    wo = next(w for w in state["work_orders"] if w["id"] == wo_id)
                    usable = [p for p in state["providers"] if not staged._provider_gap(p)]
                    elig, _ = staged.eligibility(state, wo, usable)
                    if not elig.get(prov_id):
                        st.error(f"REFUSED[not eligible: {prov_id}]; eligibility={elig}")
                    else:
                        record("coord", "dispatch", {"wo": wo_id, "provider": prov_id})
    elif view == NEW[3]:
        form("field", "geofence_attest", [("wo", "select", STAGE_WOS)])
        form("field", "checkin", [("wo", "select", STAGE_WOS)])
        form("field", "checkout", [("wo", "select", STAGE_WOS)])
        st.subheader("Media (sha256 is computed from the uploaded bytes)")
        with st.form("field_media", clear_on_submit=True):
            wo_id = pick("wo", STAGE_WOS(), "media_wo")
            mt = pick("media_type", TYPE_MEDIA(), "media_type")
            name = st.text_input("name", key="media_name")
            up = st.file_uploader("file", key="media_file")
            if st.form_submit_button("Record media"):
                if up is None:
                    st.error("MISSING[file]")
                else:
                    record("field", "media", {"wo": wo_id, "media_type": mt, "name": name,
                                              "sha256": store.file_sha256(up.getvalue())})
        st.subheader("Media prompt (missing required media)")
        mm = getattr(store, "missing_media", None)
        pw = pick("wo (media prompt)", STAGE_WOS(), "media_prompt_wo")
        if not pw or mm is None:
            st.info(NOT_RUN)
        else:
            w_ = next((x for x in cur()["work_orders"] if x["id"] == pw), None)
            miss = mm(w_) if w_ else []
            mode = dials.media_prompt_mode() if dials else NOT_RUN
            (st.warning if miss else st.success)(
                f"missing media: {', '.join(miss)} (mode {mode})" if miss
                else "no required media missing")
        form("qa", "client_attest", [("wo", "select", STAGE_WOS), ("minutes", "int", None)])
    elif view == NEW[4]:
        wos = STAGE_WOS()
        w = pick("Work order", wos, "plan_wo_pick")
        if w and st.button("Compile and plan (planner/run.sh)", type="primary"):
            with st.spinner("staged compile, MiniZinc, planner"):
                r = staged.plan_wo(cur(), w)
            st.session_state["staged_plan"] = r
            obs = staged.observe_plan(cur(), w, r)
            if obs:
                try:
                    store.append("system", *obs)
                except store.Refused as e:
                    st.error(str(e))
            of = getattr(staged, "observe_flags", None)
            for kind_, payload_ in (of(cur(), w, r) if of else []):
                try:
                    store.append("system", kind_, payload_)
                except store.Refused as e:
                    st.error(str(e))
        r = st.session_state.get("staged_plan")
        if not r:
            st.info(NOT_RUN)
        else:
            st.metric("Planner exit code", "not called" if r["rc"] is None else r["rc"])
            if r["rc"] is None or (r["rc"] != 0 and not r["steps"]):
                st.error("NO PLAN: " + ("; ".join(r["missing"]) if r["missing"] else "planner found none"))
            st.write("Goal:", r["goal"] or "none")
            st.write("Flags:", ", ".join(r.get("flags", [])) or "none")
            for m in r["missing"]:
                st.error(m)
            for i_ in r["info"]:
                st.caption(i_)
            if r["problem"]:
                with st.expander("Compiled problem (exactly what was sent)"):
                    st.code(r["problem"])
            if r["steps"]:
                plot_plan(parse_plan(r["out"]))
            if r["out"]:
                st.code(r["out"])
        if w and st.button("Settle with exact ledger"):
            rc, out = staged.settle(cur(), w)
            st.session_state["staged_ledger"] = (rc, out)
            obs = staged.observe_settle(w, rc, out)
            if obs:
                try:
                    store.append("system", *obs)
                except store.Refused as e:
                    st.error(str(e))
        led = st.session_state.get("staged_ledger")
        st.subheader("Ledger (AR / AP / margin)")
        if led:
            st.metric("Ledger exit code", led[0])
            st.code(led[1])
        else:
            st.info(NOT_RUN)
    elif view == NEW[6]:
        st.caption("Policy dials (open switches); values read from dials.py, never edited here")
        if dials is None:
            st.info(NOT_RUN)
        else:
            rows = []
            for sw, default in sorted(dials.defaults().items()):
                try:
                    val = dials.get(sw)
                except ValueError as e:
                    val = str(e)
                rows.append({"switch": sw, "value": val, "default": default})
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.write("clock_policy:", dials.clock_policy())
    else:
        evs = store.read()
        if not evs:
            st.info("Store is empty.")
        else:
            st.dataframe(pd.DataFrame([{"seq": e["seq"], "ts": e["ts"], "avatar": e["avatar"],
                                        "kind": e["kind"], "payload": str(e["payload"])}
                                       for e in evs]), width="stretch", hide_index=True)

# ---------------------------------------------------------------- 1
elif view == VIEWS[0]:
    st.header("Recorded lane standings and live gates")
    df = read_lane_receipts()
    if df.empty:
        st.warning("No receipt files in receipts/.")
    else:
        st.dataframe(df, width="stretch", hide_index=True)
        f = st.selectbox("Inspect receipt", sorted((ROOT / "receipts").glob("*.md")),
                         format_func=lambda p: p.name)
        with st.expander(f.name):
            st.markdown(f.read_text())
    st.subheader("Run a lane gate")
    just_runner("*.just", "gates")

# ---------------------------------------------------------------- 2
elif view == VIEWS[1]:
    st.header("Regression fixtures")
    st.warning("FIXTURE (test-only): these problems carry pre-set facts and numbers. They are not "
               "live state. Use views A to E for runtime state.")
    spec = ROOT / "spec"
    doms = sorted(spec.glob("*domain*.pddl"))
    probs = sorted(p for p in spec.glob("*.pddl") if p not in doms)
    if not doms or not probs:
        st.error("Missing domain or problem PDDL in spec/.")
    else:
        dom = st.selectbox("Domain", doms, format_func=rel)
        prob = st.selectbox("Problem", probs, format_func=rel)
        raw = prob.read_text()
        fluents, facts = parse_pddl_fluents(raw), parse_pddl_init_facts(raw)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Objects (parsed)")
            st.dataframe(parse_pddl_objects(raw), width="stretch", hide_index=True)
        with c2:
            st.subheader("Numeric fluents (from :init)")
            edited = {f["fluent"]: st.number_input(f["fluent"], value=f["value"]) for f in fluents}
        with st.expander("Ground predicates from :init (uncheck to test refusal)"):
            kept = {x for x in facts if st.checkbox(x, value=True, key=f"fact_{x}")}
        if st.button("Solve with planner/run.sh", type="primary"):
            mutated = raw
            for f in fluents:
                if edited[f["fluent"]] != f["value"]:
                    mutated = mutated.replace(f["raw"], f"(= ({f['fluent']}) {edited[f['fluent']]})")
            for x in facts:
                if x not in kept:
                    mutated = mutated.replace(x, f"; omitted-by-user: {x}")
            tmp = Path("/tmp/console_spec_problem.pddl")
            tmp.write_text(mutated)
            with st.spinner("planner/run.sh"):
                rc, out = run_planner(dom, tmp)
            keep("plan_spec", rc, out)
        panel("plan_spec", gantt=True)

# ---------------------------------------------------------------- 3
elif view == VIEWS[2]:
    st.header("10-D alignment solver")
    mzns = sorted((ROOT / "alignment").glob("*.mzn"))
    dzns = sorted((ROOT / "alignment").rglob("*.dzn"))
    if not mzns or not dzns:
        st.warning("No .mzn or .dzn under alignment/.")
    else:
        c1, c2, c3 = st.columns(3)
        mzn = c1.selectbox("Model", mzns, format_func=rel)
        dzn = c2.selectbox("Instance", dzns, format_func=rel)
        rc_s, solvers_out = run_cmd(["minizinc", "--solvers-json"])
        names = re.findall(r'"id"\s*:\s*"[^"]*\.([A-Za-z0-9_-]+)"', solvers_out) if rc_s == 0 else []
        solver = c3.selectbox("Backend", sorted(set(names)) or [NOT_RUN])
        text = st.text_area("Instance data (from disk, editable)", dzn.read_text(), height=260)
        b1, b2 = st.columns(2)
        if b1.button("Solve with minizinc", type="primary"):
            tmp = Path("/tmp/console_active.dzn")
            tmp.write_text(text)
            with st.spinner("minizinc"):
                rc, out = run_cmd(["minizinc", "--solver", solver, str(mzn), str(tmp)],
                                  timeout=LONG_TIMEOUT)
            keep("mzn", rc, out)
        py, diff = ROOT / "cpsat" / ".venv" / "bin" / "python", ROOT / "cpsat" / "diff_vs_minizinc.py"
        if py.exists() and diff.exists() and b2.button("Run CP-SAT vs MiniZinc harness"):
            with st.spinner("cpsat/diff_vs_minizinc.py"):
                rc, out = run_cmd([str(py), str(diff)], cwd=ROOT / "cpsat", timeout=LONG_TIMEOUT)
            keep("cpsat_diff", rc, out)
        st.subheader("MiniZinc result")
        panel("mzn")
        st.subheader("CP-SAT vs MiniZinc")
        panel("cpsat_diff")

# ---------------------------------------------------------------- 4
elif view == VIEWS[3]:
    st.header("Enterprise state compiler")
    jsons = sorted((ROOT / "pipeline").rglob("*.json"))
    if jsons:
        jf = st.selectbox("State JSON", jsons, format_func=rel)
        st.code(jf.read_text(), language="json")
    just_runner("*pipeline*.just", "pipeline")

# ---------------------------------------------------------------- 5
elif view == VIEWS[4]:
    st.header("Preventive maintenance")
    lane_pddl_runner("pm")
    just_runner("*pm*.just", "pm")

# ---------------------------------------------------------------- 6
elif view == VIEWS[5]:
    st.header("ProcurePass parts and NTE")
    lane_pddl_runner("procurepass")
    just_runner("*procurepass*.just", "procurepass")

# ---------------------------------------------------------------- 7
elif view == VIEWS[6]:
    st.header("Replay executor and exact ledger")
    solns = sorted(p for p in ROOT.rglob("*.soln") if ".venv" not in p.parts)
    if solns:
        sf = st.selectbox("Plan trace on disk", solns, format_func=rel)
        st.code(sf.read_text())
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Executor")
        just_runner("*executor*.just", "executor")
    with c2:
        st.subheader("Ledger")
        just_runner("*ledger*.just", "ledger")

# ---------------------------------------------------------------- 8
else:
    st.header("Adversarial courts: mutants that must be refused")
    st.caption("Mutants are generated and restored byte-exact by courts/court.py; output below is verbatim.")
    just_runner("*l8*.just", "courts")
