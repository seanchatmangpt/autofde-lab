#!/usr/bin/env python3
"""Native planner bootstrap reprove, emitted live as OCEL 2.0 events.

Steps (each emits ActionStarted -> ActionCompleted | ActionFailed, and the
episode emits NativePlannerBootstrapStarted -> Completed | Failed):

  1. submodules   : `git submodule status` shows every cpp/sdk/* populated
  2. configure    : reuse cpp/build (CMakeCache.txt present; key vars logged)
  3. cmake-build  : `cmake --build build -j4` from cpp/
  4. uv-sync      : documented bootstrap (`uv sync --extra=all --frozen`) — builds the
                    __autofde_lab_hub_cpp extension via scikit-build-core
                    (ONLY_PYTHON=true) into .venv; cpp/build has
                    BUILD_PYTHON_BINDING=OFF so it can never yield it
  5. import       : .venv/bin/python -c 'import autofde_lab.hub.__autofde_lab_hub_cpp'
  6. native-solve : native_solve_min.py (C++ A* on a 10x10 grid)

Fails closed: the first failing step ends the episode with
NativePlannerBootstrapFailed carrying the exact error text; validate.py is run
on the log regardless. stdlib only. Usage:

  python3 tools/crown2/native/bootstrap.py [--skip-uv-sync] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "ocel_v2"))
import emitter  # noqa: E402
import validate  # noqa: E402

SDK_SUBMODULES = ("Catch2", "PEGTL", "backward-cpp", "json", "nng", "nngpp", "pybind11", "spdlog")
TAIL = 25


def _tail(s: str, n: int = TAIL) -> str:
    lines = s.rstrip().splitlines()
    return "\n".join(lines[-n:])


def run(cmd: list[str], cwd: str, log, timeout: int = 3600) -> tuple[int, str]:
    log.write(f"\n$ (cd {cwd} && {' '.join(cmd)})\n")
    log.flush()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    out = p.stdout + p.stderr
    log.write(out)
    log.write(f"EXIT={p.returncode}\n")
    log.flush()
    return p.returncode, out


class Bootstrap:
    def __init__(self, out_path: str, log) -> None:
        self.out = out_path
        self.log = log
        self.n = 0
        emitter.init(out_path)
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=REPO, capture_output=True, text=True).stdout.strip()
        self.sha, self.branch = sha, branch
        emitter.add_object(out_path, "Worktree", "wt:autofde-compose", {"path": REPO, "branch": branch, "base_ref": "main"})
        emitter.add_object(out_path, "Commit", "commit:" + sha[:12], {"sha": sha})
        emitter.add_object(out_path, "SolverImplementation", "solver:astar-native",
                           {"name": "Astar", "kind": "cpp:_AStarSolver_", "version": sha[:12]})
        emitter.add_object(out_path, "ProcessEpisode", "episode:native-bootstrap",
                           {"label": "NativePlannerBootstrap", "started_at": emitter._now_iso()})
        emitter.add_event(out_path, "NativePlannerBootstrapStarted", "ev:bootstrap-started",
                          {"worktree": REPO, "sha": sha}, ["wt:autofde-compose", "commit:" + sha[:12], "episode:native-bootstrap"])

    def step(self, name: str, fn) -> str:
        """Run fn() -> result_summary str; raise RuntimeError on failure."""
        self.n += 1
        aid = f"action:{self.n:02d}-{name}"
        emitter.add_object(self.out, "Action", aid, {"name": name, "kind": "bootstrap-step", "args_json": "{}"})
        emitter.add_event(self.out, "ActionStarted", f"ev:{self.n:02d}-{name}-started", {"name": name}, [aid, "episode:native-bootstrap"])
        t0 = time.time()
        try:
            summary = fn()
        except Exception as e:  # noqa: BLE001 — every failure must land in the log
            err = f"{type(e).__name__}: {e}"
            emitter.add_event(self.out, "ActionFailed", f"ev:{self.n:02d}-{name}-failed", {"name": name, "error": err[-4000:]}, [aid, "episode:native-bootstrap"])
            emitter.add_event(self.out, "NativePlannerBootstrapFailed", "ev:bootstrap-failed",
                              {"failing_step": name, "error": err[-4000:]}, [aid, "episode:native-bootstrap", "wt:autofde-compose"])
            raise
        summary = f"{summary} ({time.time() - t0:.1f}s)"
        emitter.add_event(self.out, "ActionCompleted", f"ev:{self.n:02d}-{name}-completed", {"name": name, "result_summary": summary[-4000:]}, [aid, "episode:native-bootstrap"])
        return summary

    # ---- steps -----------------------------------------------------------
    def submodules(self) -> str:
        rc, out = run(["git", "submodule", "status"], REPO, self.log)
        if rc != 0:
            raise RuntimeError(f"git submodule status exit={rc}: {_tail(out)}")
        seen = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].startswith("cpp/sdk/"):
                seen[parts[1].split("/")[-1]] = line[0]
        missing = [m for m in SDK_SUBMODULES if m not in seen or seen[m] == "-"]
        if missing:
            raise RuntimeError(f"cpp/sdk submodules not populated: {missing}; status={seen}")
        return f"cpp/sdk populated: {sorted(seen)}"

    def configure(self) -> str:
        cache = os.path.join(REPO, "cpp", "build", "CMakeCache.txt")
        if not os.path.exists(cache):
            raise RuntimeError(f"no reusable configure: {cache} missing")
        keys = {}
        with open(cache, encoding="utf-8") as f:
            for line in f:
                for k in ("BUILD_PYTHON_BINDING", "ONLY_PYTHON", "CMAKE_BUILD_TYPE", "CMAKE_GENERATOR"):
                    if line.startswith(k + ":"):
                        keys[k] = line.strip().split("=", 1)[1]
        self.log.write(f"reuse cpp/build CMakeCache: {keys}\n")
        return f"reused cpp/build CMakeCache {keys}"

    def cmake_build(self) -> str:
        rc, out = run(["cmake", "--build", "build", "-j4"], os.path.join(REPO, "cpp"), self.log)
        tail = _tail(out)
        if rc != 0 or "error:" in out:
            raise RuntimeError(f"cmake --build exit={rc}\n{tail}")
        return f"cmake --build build -j4 exit=0; tail: {tail}"

    def uv_sync(self) -> str:
        # --frozen: install exactly uv.lock. Plain `uv sync --extra=all`
        # re-resolves and fails on the `ocpq` extra (unpublished `wasm4pm`,
        # added to pyproject after uv.lock was last written) — see
        # check_uv_lock_extras.py, the falsifier for that drift.
        rc, out = run(["uv", "sync", "--extra=all", "--frozen"], REPO, self.log, timeout=7200)
        if rc != 0:
            raise RuntimeError(f"uv sync --extra=all --frozen exit={rc}\n{_tail(out, 40)}")
        return f"uv sync --extra=all --frozen exit=0; tail: {_tail(out, 8)}"

    def import_ext(self) -> str:
        py = os.path.join(REPO, ".venv", "bin", "python")
        if not os.path.exists(py):
            raise RuntimeError(f"repo python env missing: {py}")
        code = "import autofde_lab.hub.__autofde_lab_hub_cpp as m, sys; print(m.__file__); print(sys.version.split()[0])"
        rc, out = run([py, "-c", code], REPO, self.log)
        if rc != 0:
            raise RuntimeError(f"import exit={rc}: {_tail(out)}")
        self.extension_path = out.splitlines()[0].strip()
        return f"imported {self.extension_path} python={out.splitlines()[1].strip()}"

    def native_solve(self) -> str:
        py = os.path.join(REPO, ".venv", "bin", "python")
        rc, out = run([py, os.path.join(os.path.dirname(__file__), "native_solve_min.py")], REPO, self.log, timeout=600)
        if rc != 0:
            raise RuntimeError(f"native solve exit={rc}: {_tail(out)}")
        self.solve_summary = json.loads([l for l in out.splitlines() if l.startswith("{")][-1])
        return json.dumps(self.solve_summary, sort_keys=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "native-bootstrap.ocel.json"))
    ap.add_argument("--skip-uv-sync", action="store_true", help="reuse an existing .venv extension build")
    a = ap.parse_args(argv[1:])
    log_path = a.out.replace(".ocel.json", ".log")
    status = "BLOCKED"
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"pwd={REPO}\n")
        b = Bootstrap(a.out, log)
        log.write(f"branch={b.branch} sha={b.sha}\n")
        try:
            b.step("submodules", b.submodules)
            b.step("configure", b.configure)
            b.step("cmake-build", b.cmake_build)
            if not a.skip_uv_sync:
                b.step("uv-sync", b.uv_sync)
            b.step("import", b.import_ext)
            b.step("native-solve", b.native_solve)
            emitter.add_event(a.out, "NativePlannerBootstrapCompleted", "ev:bootstrap-completed",
                              {"extension_path": b.extension_path, "solve_summary_json": b.solve_summary},
                              ["episode:native-bootstrap", "wt:autofde-compose", "solver:astar-native"])
            status = "ALIVE" if b.solve_summary.get("ok") else "PARTIAL"
        except Exception as e:  # noqa: BLE001
            log.write(f"\nBLOCKED at step {b.n}: {e}\n")
    with open(a.out, encoding="utf-8") as f:
        summary = validate.validate(json.load(f))
    print(json.dumps({"status": status, "ocel": a.out, "log": log_path, "validate": summary}))
    return 0 if status == "ALIVE" and all(v == 0 for v in summary.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
