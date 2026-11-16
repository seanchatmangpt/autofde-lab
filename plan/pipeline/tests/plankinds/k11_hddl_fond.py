"""K11: HDDL/HTN + FOND. `run` routes to the autofde-lab coprocessor (htn / fond kinds);
`run_oracle` keeps the ferroplan `hddl_solve` op (prebuilt ferroplan_wasm.wasm, driven by node).

The ferroplan `ff` CLI has no HDDL entry point (README/--help); HDDL solving is exposed through the
ferroplan-wasm JSON ABI (fp_alloc/fp_call). Node hosts the module with minimal WASI stubs."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from enterprise_pipeline import autofde_backend as backend
from plankinds import Case, Outcome, Skip

KIND = "K11"
TITLE = "HDDL/HTN + FOND (ferroplan hddl_solve)"
ROOT = Path(os.environ.get("FERROPLAN_ROOT", "/Users/sac/ferroplan"))
WASM = Path(os.environ.get("FERROPLAN_WASM", "/Users/sac/ex4pm/priv/ferroplan/ferroplan_wasm.wasm"))
DOM = ROOT / "domains"
SA2A = Path("/Users/sac/xaas/tasks/sa2a_diataxis.hddl")
TIMEOUT_S = 120

HOST_JS = r"""
const fs=require("fs");
const [,, wasmPath, reqPath]=process.argv;
let ex;
const dv=()=>new DataView(ex.memory.buffer);
const w={
 random_get:(p,l)=>{require("crypto").randomFillSync(new Uint8Array(ex.memory.buffer,p,l));return 0},
 environ_get:()=>0,
 environ_sizes_get:(a,b)=>{dv().setUint32(a,0,true);dv().setUint32(b,0,true);return 0},
 clock_time_get:(id,prec,out)=>{dv().setBigUint64(out,process.hrtime.bigint(),true);return 0},
 fd_close:()=>0, fd_fdstat_get:()=>8, fd_filestat_get:()=>8, fd_prestat_get:()=>8,
 fd_prestat_dir_name:()=>8,
 fd_read:(fd,iovs,n,out)=>{dv().setUint32(out,0,true);return 0},
 fd_write:(fd,iovs,n,out)=>{let t=0;for(let i=0;i<n;i++){t+=dv().getUint32(iovs+i*8+4,true)}
   dv().setUint32(out,t,true);return 0},
 path_open:()=>76,
 proc_exit:(c)=>{throw new Error("proc_exit "+c)},
 sched_yield:()=>0,
};
const mod=new WebAssembly.Module(fs.readFileSync(wasmPath));
ex=new WebAssembly.Instance(mod,{wasi_snapshot_preview1:w}).exports;
const req=fs.readFileSync(reqPath);
const p=ex.fp_alloc(req.length);
new Uint8Array(ex.memory.buffer,p,req.length).set(req);
const r=BigInt.asUintN(64,ex.fp_call(p,req.length));
const op=Number(r>>32n),ol=Number(r&0xffffffffn);
process.stdout.write(Buffer.from(new Uint8Array(ex.memory.buffer,op,ol)).toString("utf8"));
"""

SA2A_PROBLEM = ("(define (problem sa2a-p1) (:domain xaas-sa2a-diataxis) (:objects x - subject)\n"
                " (:htn :parameters () :ordered-subtasks (and (t (brce x))))\n"
                " (:init (observed x) (authorized x)) (:goal (and (replayed x))))\n")


def probe():
    if not Path(backend.AUTOFDE_VENV_PYTHON).exists():
        return Skip("autofde-lab venv absent", "cd /Users/sac/autofde-lab && uv sync")
    return None


def oracle_probe():
    if not shutil.which("node"):
        return Skip("node not on PATH (needed to host the ferroplan wasm module)", "brew install node")
    if not WASM.exists():
        return Skip(f"ferroplan wasm absent: {WASM}",
                    f"cd {ROOT} && cargo build -p ferroplan-wasm --release --target wasm32-wasip1")
    for p in (DOM / "wo-dispatch-fond.hddl", DOM / "solve_x.hddl", SA2A):
        if not p.exists():
            return Skip(f"HDDL input missing: {p}", "")
    return None


def _mutate_empty_init(problem: str) -> str:
    return re.sub(r"\(:init.*?\)\s*(?=\(:goal)", "(:init)\n  ", problem, count=1, flags=re.S)


def cases():
    wo_d = (DOM / "wo-dispatch-fond.hddl").read_text()
    wo_p = (DOM / "wo-dispatch-fond.problem.hddl").read_text()
    sx_d = (DOM / "solve_x.hddl").read_text()
    sx_p = (DOM / "solve_x.problem.hddl").read_text()
    sa_d = SA2A.read_text()
    out = [
        Case("wo-dispatch-fond", "PLAN", {"domain": wo_d, "problem": wo_p}),
        Case("solve-x", "PLAN", {"domain": sx_d, "problem": sx_p}),
        Case("sa2a-diataxis", "PLAN", {"domain": sa_d, "problem": SA2A_PROBLEM}),
        Case("wo-dispatch-fond-mutated-init", "NO_PLAN",
             {"domain": wo_d, "problem": _mutate_empty_init(wo_p)}),
        Case("solve-x-mutated-init", "NO_PLAN",
             {"domain": sx_d, "problem": _mutate_empty_init(sx_p)}),
        Case("sa2a-diataxis-mutated-init", "NO_PLAN",
             {"domain": sa_d, "problem": _mutate_empty_init(SA2A_PROBLEM)}),
        # removing an action that a method still references is refused at grounding
        Case("sa2a-diataxis-mutated-remove-action", "REFUSED",
             {"domain": sa_d.replace("(:action construct", "(:action construct-renamed"),
              "problem": SA2A_PROBLEM}),
    ]
    return out


def run(case):
    """Coprocessor: typed domains (`:types`) -> htn; propositional (oneof-capable) -> fond."""
    dom, prob = case.payload["domain"], case.payload["problem"]
    if "(:types" in dom:
        r = backend.solve("htn", {"domain_text": dom, "problem_text": prob}, timeout=TIMEOUT_S)
    else:
        r = backend.solve("fond", {"hddl_domain_text": dom, "hddl_problem_text": prob},
                          timeout=TIMEOUT_S)
    status = "NO_PLAN" if r.status == "INFEASIBLE" else r.status
    return Outcome(status, f"coprocessor:{r.kind} solver={r.solver} {str(r.diagnostics)[:120]}")


def run_oracle(case):
    sk = oracle_probe()
    if sk:
        return Outcome("SKIP", sk.reason)
    with tempfile.TemporaryDirectory() as tmp:
        host = os.path.join(tmp, "host.js")
        req = os.path.join(tmp, "req.json")
        Path(host).write_text(HOST_JS)
        Path(req).write_text(json.dumps({"op": "hddl_solve", "domain": case.payload["domain"],
                                         "problem": case.payload["problem"]}))
        try:
            r = subprocess.run(["node", host, str(WASM), req], capture_output=True, text=True,
                               timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return Outcome("UNSUPPORTED", f"timeout>{TIMEOUT_S}s")
    if r.returncode != 0:
        return Outcome("REFUSED", f"node exit={r.returncode} {r.stderr.strip()[:200]}")
    try:
        j = json.loads(r.stdout)
    except ValueError:
        return Outcome("REFUSED", f"non-JSON stdout: {r.stdout[:120]!r}")
    err = j.get("error")
    if err:
        if err.get("code") == "FP_MODEL" and "NoPlan" in err.get("message", ""):
            return Outcome("NO_PLAN", f"{err['code']}: {err['message']}")
        return Outcome("REFUSED", f"{err.get('code')}: {err.get('message', '')[:160]}")
    if j.get("solved"):
        return Outcome("PLAN", f"{j.get('planning_type')} policy_entries={len(j.get('policy', []))} "
                               f"notes={j.get('notes')}")
    return Outcome("NO_PLAN", f"solved=false notes={j.get('notes')}")
