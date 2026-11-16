"""K15 gymact: real BPMN run, POWL conformance, combinatorial explore via `uv run --project`."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from . import Case, Outcome, Skip

KIND = "K15"
TITLE = "gymact (BPMN runtime, POWL conformance, possibility-graph explore)"
REPO = Path(os.environ.get("GYMACT_REPO", str(Path.home() / "gymact")))
FIX = REPO / "tests/fixtures"
UNSUPPORTED_KINDS = ["SAT/SMT", "behavior trees", "executable state machine", "replanning",
                     "preference planning", "fast-downward", "VAL"]

_DRIVER = r'''
import json, sys, warnings
warnings.filterwarnings("ignore")
a = json.loads(sys.argv[1])
if a["kind"] == "bpmn":
    from gymact.bpmn_runtime import run_bpmn_workflow, BpmnWorkflowRefusal
    try:
        r = run_bpmn_workflow(a["path"], a["process"])
        print(json.dumps({"status": "PLAN" if r.is_completed else "NO_PLAN",
                          "detail": ",".join(r.completed_task_names)}))
    except BpmnWorkflowRefusal as e:
        print(json.dumps({"status": "REFUSED", "detail": str(e)[:160]}))
else:
    from gymact.powl.algebra import Atom, PartialOrder, OrderEdge
    from gymact.powl.conformance import check_ocel_conformance
    from wasm4pm_compat_pydantic.generated import OcelEvent, OcelEventAttribute as A
    m = PartialOrder(children=(Atom(label="a"), Atom(label="b")), order=frozenset({OrderEdge(0, 1)}))
    ev = tuple(OcelEvent(id=f"e{i}", type="powl_structural_fire", time="2026-01-01T00:00:00Z",
                         attributes=[A(name="detail", value=l)], relationships=[])
               for i, l in enumerate(a["trace"]))
    r = check_ocel_conformance(m, ev)
    print(json.dumps({"status": "PLAN" if r.conforms else "INFEASIBLE",
                      "detail": f"conforms={r.conforms} div={r.divergence_label} enabled={r.divergence_enabled_labels}"}))
'''


def probe() -> Skip | None:
    if not (REPO / ".venv").is_dir():
        return Skip(f"GYMACT_REPO={REPO} has no .venv", f"export GYMACT_REPO=<gymact checkout>; cd {REPO} && uv sync --extra bpmn")
    r = subprocess.run(["uv", "run", "--extra", "bpmn", "--project", str(REPO), "python", "-W", "ignore", "-c",
                        "import gymact.bpmn_runtime, gymact.powl.conformance"],
                       capture_output=True, text=True)
    if r.returncode:
        return Skip(f"gymact import failed: {r.stderr.strip()[-200:]}", f"cd {REPO} && uv sync --extra bpmn")
    return None


def cases() -> list[Case]:
    bpmn = str(FIX / "simple_sequential.bpmn")
    return [
        Case("bpmn-simple-sequential", "PLAN", {"kind": "bpmn", "path": bpmn, "process": "simple_sequential"}),
        Case("bpmn-unknown-process", "REFUSED", {"kind": "bpmn", "path": bpmn, "process": "no_such_process"}),
        Case("powl-conformant-trace", "PLAN", {"kind": "powl", "trace": ["a", "b"]}),
        Case("powl-nonconformant-trace", "INFEASIBLE", {"kind": "powl", "trace": ["b", "a"]}),
        Case("explore-cli-fixture", "PLAN", {"kind": "explore", "path": str(FIX / "cli_explore_request.json")}),
        Case("explore-cli-bad-request", "REFUSED", {"kind": "explore", "bad": True}),
    ]


def run(case: Case) -> Outcome:
    p = case.payload
    if p["kind"] == "explore":
        with tempfile.TemporaryDirectory() as d:
            path = p.get("path")
            if p.get("bad"):
                path = str(Path(d) / "bad.json")
                Path(path).write_text('{"x": 1}')
            r = subprocess.run(["uv", "run", "--quiet", "--extra", "bpmn", "--project", str(REPO), "gymact", "explore", path],
                               capture_output=True, text=True)
            if r.returncode:
                return Outcome("REFUSED", f"rc={r.returncode} {r.stderr.strip()[-100:]}")
            n = len(json.loads(r.stdout)["exploration"]["evaluations"])
            return Outcome("PLAN", f"rc=0 evaluations={n}")
    r = subprocess.run(["uv", "run", "--quiet", "--extra", "bpmn", "--project", str(REPO), "python", "-W", "ignore", "-c",
                        _DRIVER, json.dumps(p)], capture_output=True, text=True)
    if r.returncode:
        return Outcome("REFUSED", f"driver rc={r.returncode} {r.stderr.strip()[-150:]}")
    o = json.loads(r.stdout.strip().splitlines()[-1])
    return Outcome(o["status"], o["detail"])
