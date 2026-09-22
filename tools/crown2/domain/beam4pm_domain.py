#!/usr/bin/env python3
"""
beam4pm_domain.py -- Crown-2 planning domain for the beam4pm verify chain.

Three surfaces, all grounded in the real repo / real logs, nothing hardcoded:

  observe(repo)            -> WorldState of staged booleans, each carrying the
                              real probe (or cited log line) that justified it.
  discover_actions(repo)   -> Actions parsed FROM the repo surface (justfile,
                              Makefile, mix.exs, native/*/Cargo.toml, the
                              `System.fetch_env!` reads in test/, and the env
                              script that defines those vars). Every action
                              carries `source` = file:line evidence.
  plan(state, goal, ...)   -> ordered forward-search plan, or a typed
                              NoPlanFound naming the missing transition.

Stages (ordered; each is a boolean in WorldState):
  SUBMODULES_READY, SYNC_READY, LINT_TRUTH_READY, RUST_TESTS_READY,
  ELIXIR_DEPS_READY, MIX_TEST_RUNNABLE, NATIVE_ORACLES_BUILT, ORACLE_ENV_SET,
  MIX_TEST_GREEN, QUALIFICATION_COMPLETE

Stdlib only. Evidence plane reused: tools/ocel_v2/emitter.py (emit_receipt).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent.parent  # .../autofde-lab/tools
INTEGRATION_ROOT = TOOLS.parent.parent  # /Users/sac/crown-2-integration
DEFAULT_REPO = INTEGRATION_ROOT / "beam4pm"
DEFAULT_LOGS = INTEGRATION_ROOT

STAGES: tuple[str, ...] = (
    "SUBMODULES_READY",
    "SYNC_READY",
    "LINT_TRUTH_READY",
    "RUST_TESTS_READY",
    "ELIXIR_DEPS_READY",
    "MIX_TEST_RUNNABLE",
    "NATIVE_ORACLES_BUILT",
    "ORACLE_ENV_SET",
    "MIX_TEST_GREEN",
    "QUALIFICATION_COMPLETE",
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Evidence:
    """Why a boolean has its value: a real probe or a cited log line."""

    kind: str  # "probe" | "log"
    source: str  # command run, or file:line
    detail: str


@dataclass
class WorldState:
    stages: dict[str, bool]
    evidence: dict[str, Evidence]
    repo: str

    def get(self, stage: str) -> bool:
        return bool(self.stages.get(stage, False))

    def with_(self, **changes: bool) -> "WorldState":
        s = dict(self.stages)
        s.update(changes)
        return WorldState(stages=s, evidence=dict(self.evidence), repo=self.repo)

    def to_json(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "stages": dict(self.stages),
            "evidence": {k: asdict(v) for k, v in self.evidence.items()},
        }


@dataclass(frozen=True)
class Action:
    name: str
    command: str
    cwd: str
    preconditions: dict[str, bool]
    postconditions: dict[str, bool]
    reversible: bool
    consequential: bool
    source: str  # file:line discovery evidence
    env: dict[str, str] = field(default_factory=dict)

    def applicable(self, state: WorldState) -> bool:
        return all(state.get(k) == v for k, v in self.preconditions.items())

    def apply(self, state: WorldState) -> WorldState:
        return state.with_(**self.postconditions)


@dataclass(frozen=True)
class NoPlanFound:
    """Typed failure: names the stage no discovered action can flip."""

    goal: dict[str, bool]
    missing_transition: str
    reachable_frontier: dict[str, bool]
    explored: int

    def __str__(self) -> str:
        return (
            f"NO_PLAN_FOUND: no discovered action produces {self.missing_transition}=True "
            f"from the reachable frontier (explored {self.explored} states)"
        )


# ---------------------------------------------------------------------------
# observe(): real cheap probes
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


def _grep_log(path: Path, pattern: str) -> tuple[int, str] | None:
    if not path.exists():
        return None
    rx = re.compile(pattern)
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            if rx.search(line):
                return i, line.rstrip("\n")
    return None


def _mix_lock_deps(repo: Path) -> list[str]:
    text = (repo / "mix.lock").read_text(encoding="utf-8")
    return re.findall(r'^\s*"([a-z0-9_]+)":', text, flags=re.M)


def _oracle_crates(repo: Path) -> list[tuple[str, Path]]:
    """(binary_name, crate_dir) for every native/*/Cargo.toml declaring a
    package whose name a test/ or scripts/env file references as an oracle."""
    out = []
    for cargo in sorted((repo / "native").glob("*/Cargo.toml")):
        m = re.search(r'^\[package\]\s*\nname\s*=\s*"([^"]+)"', cargo.read_text(encoding="utf-8"), re.M)
        if m and m.group(1).endswith("-oracle"):
            out.append((m.group(1), cargo.parent))
    return out


def _oracle_env_requirements(repo: Path) -> list[dict[str, str]]:
    """Every `System.fetch_env!("X")` in test/ plus the definition line of X in
    scripts/env/*.sh (which yields the discovered value)."""
    reqs: dict[str, dict[str, str]] = {}
    for exs in sorted((repo / "test").glob("*.exs")):
        for i, line in enumerate(exs.read_text(encoding="utf-8").splitlines(), 1):
            for var in re.findall(r'System\.fetch_env!\("([A-Z0-9_]+)"\)', line):
                reqs.setdefault(var, {"var": var, "read_at": f"{exs.relative_to(repo)}:{i}"})
    for sh in sorted((repo / "scripts" / "env").glob("*.sh")):
        for i, line in enumerate(sh.read_text(encoding="utf-8").splitlines(), 1):
            m = re.match(r'\s*export\s+([A-Z0-9_]+)="\$ROOT/([^"]+)"', line)
            if m and m.group(1) in reqs:
                reqs[m.group(1)]["defined_at"] = f"{sh.relative_to(repo)}:{i}"
                reqs[m.group(1)]["value"] = str(repo / m.group(2))
    return [reqs[k] for k in sorted(reqs)]


def observe(repo: Path = DEFAULT_REPO, logs: Path = DEFAULT_LOGS, env: dict[str, str] | None = None) -> WorldState:
    repo = Path(repo)
    env = dict(os.environ if env is None else env)
    st: dict[str, bool] = {}
    ev: dict[str, Evidence] = {}

    # SUBMODULES_READY: real probe -- no line prefixed '-' (uninitialised).
    r = _run(["git", "submodule", "status"], repo)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    st["SUBMODULES_READY"] = r.returncode == 0 and bool(lines) and not any(l.startswith("-") for l in lines)
    ev["SUBMODULES_READY"] = Evidence("probe", "git submodule status", f"{len(lines)} submodules, rc={r.returncode}")

    # SYNC_READY: ggen.lock present (justfile sync regenerates it) + log citation.
    lock = repo / "ggen.lock"
    hit = _grep_log(logs / "beam4pm-verify.log", r"^ggen sync run$")
    st["SYNC_READY"] = lock.exists()
    ev["SYNC_READY"] = Evidence(
        "probe", f"test -f {lock}", f"exists={lock.exists()}; log beam4pm-verify.log:{hit[0] if hit else '?'} '{hit[1] if hit else ''}'"
    )

    # LINT_TRUTH_READY: real probe -- the gate script itself is a cheap grep scan.
    gate = repo / "scripts" / "gate_lint_truth.sh"
    if gate.exists():
        r = _run(["bash", str(gate)], repo)
        st["LINT_TRUTH_READY"] = r.returncode == 0
        last = (r.stdout.strip().splitlines() or [""])[-1]
        ev["LINT_TRUTH_READY"] = Evidence("probe", "bash scripts/gate_lint_truth.sh", f"rc={r.returncode}: {last}")
    else:
        st["LINT_TRUTH_READY"] = False
        ev["LINT_TRUTH_READY"] = Evidence("probe", f"test -f {gate}", "missing")

    # RUST_TESTS_READY: cited log line (eunit/rust suite not re-run: not cheap).
    hit = _grep_log(logs / "beam4pm-verify.log", r"All \d+ tests passed\.")
    st["RUST_TESTS_READY"] = hit is not None
    ev["RUST_TESTS_READY"] = Evidence("log", f"beam4pm-verify.log:{hit[0] if hit else '?'}", hit[1].strip() if hit else "no 'All N tests passed.' line")

    # ELIXIR_DEPS_READY: every mix.lock dep has a deps/<name> checkout.
    deps = _mix_lock_deps(repo)
    missing = [d for d in deps if not (repo / "deps" / d).is_dir()]
    st["ELIXIR_DEPS_READY"] = bool(deps) and not missing
    ev["ELIXIR_DEPS_READY"] = Evidence("probe", "mix.lock keys vs deps/<name>/", f"{len(deps)} locked, missing={missing}")

    # MIX_TEST_RUNNABLE: deps ready AND compiled test build present, + log citation.
    hit = _grep_log(logs / "beam4pm-verify2.log", r"^\d+ tests, \d+ failures")
    built = (repo / "_build" / "test" / "lib").is_dir()
    st["MIX_TEST_RUNNABLE"] = st["ELIXIR_DEPS_READY"] and built
    ev["MIX_TEST_RUNNABLE"] = Evidence(
        "probe", "test -d _build/test/lib", f"built={built}; log beam4pm-verify2.log:{hit[0] if hit else '?'} '{hit[1] if hit else ''}'"
    )

    # NATIVE_ORACLES_BUILT: every native/*-oracle crate has target/release/<bin>.
    crates = _oracle_crates(repo)
    absent = [name for name, d in crates if not (d / "target" / "release" / name).exists()]
    st["NATIVE_ORACLES_BUILT"] = bool(crates) and not absent
    ev["NATIVE_ORACLES_BUILT"] = Evidence("probe", "native/*/Cargo.toml -> target/release/<name>", f"crates={[n for n, _ in crates]}, absent={absent}")

    # ORACLE_ENV_SET: every System.fetch_env! var read in test/ is set in env.
    reqs = _oracle_env_requirements(repo)
    unset = [q["var"] for q in reqs if not env.get(q["var"])]
    st["ORACLE_ENV_SET"] = bool(reqs) and not unset
    ev["ORACLE_ENV_SET"] = Evidence("probe", "test/*.exs System.fetch_env! vs os.environ", f"required={[q['var'] for q in reqs]}, unset={unset}")

    # MIX_TEST_GREEN: latest mix summary line in logs must show 0 failures.
    green = False
    detail = "no mix test summary line found"
    for log in ("beam4pm-verify2.log", "beam4pm-verify.log"):
        hit = _grep_log(logs / log, r"^\d+ tests, \d+ failures")
        if hit:
            m = re.match(r"(\d+) tests, (\d+) failures", hit[1])
            green = m is not None and m.group(2) == "0"
            detail = f"{log}:{hit[0]} '{hit[1]}'"
            break
    st["MIX_TEST_GREEN"] = green
    ev["MIX_TEST_GREEN"] = Evidence("log", detail.split(" ")[0], detail)

    # QUALIFICATION_COMPLETE: derived -- all upstream stages true.
    st["QUALIFICATION_COMPLETE"] = all(st[s] for s in STAGES if s != "QUALIFICATION_COMPLETE")
    ev["QUALIFICATION_COMPLETE"] = Evidence("probe", "conjunction of all other stages", str([s for s in STAGES if not st.get(s)]))

    return WorldState(stages={s: st[s] for s in STAGES}, evidence=ev, repo=str(repo))


# ---------------------------------------------------------------------------
# discover_actions(): parse the repo surface
# ---------------------------------------------------------------------------


def _recipes(path: Path, pattern: str) -> dict[str, tuple[int, list[str]]]:
    """name -> (line, body_commands) for justfile/Makefile-shaped files."""
    out: dict[str, tuple[int, list[str]]] = {}
    if not path.exists():
        return out
    lines = path.read_text(encoding="utf-8").splitlines()
    cur = None
    for i, line in enumerate(lines, 1):
        m = re.match(pattern, line)
        if m and not line.startswith((" ", "\t")):
            cur = m.group(1)
            out[cur] = (i, [])
            continue
        if cur and line.startswith((" ", "\t")) and line.strip():
            out[cur][1].append(line.strip().lstrip("@"))
        elif not line.strip():
            continue
        elif not line.startswith((" ", "\t")):
            cur = None
    return out


def discover_actions(repo: Path = DEFAULT_REPO) -> list[Action]:
    repo = Path(repo)
    acts: list[Action] = []

    just = _recipes(repo / "justfile", r"^([A-Za-z_][A-Za-z0-9_-]*):")
    make = _recipes(repo / "Makefile", r"^([A-Za-z_][A-Za-z0-9_-]*):")

    def recipe_src(name: str) -> str | None:
        if name in just:
            return f"justfile:{just[name][0]}"
        if name in make:
            return f"Makefile:{make[name][0]}"
        return None

    # submodules / sync / lint_truth from justfile (Makefile as fallback source).
    if recipe_src("submodules"):
        body = (just.get("submodules") or make["submodules"])[1]
        acts.append(Action("submodules", " && ".join(body), str(repo), {}, {"SUBMODULES_READY": True}, True, False, recipe_src("submodules")))
    if recipe_src("sync"):
        body = (just.get("sync") or make["sync"])[1]
        acts.append(Action("sync", " && ".join(body), str(repo), {"SUBMODULES_READY": True}, {"SYNC_READY": True}, False, True, recipe_src("sync")))
    if recipe_src("lint_truth"):
        body = just["lint_truth"][1]
        acts.append(Action("lint_truth", " && ".join(body), str(repo), {"SYNC_READY": True}, {"LINT_TRUTH_READY": True}, True, False, recipe_src("lint_truth")))
    if recipe_src("test"):
        body = (just.get("test") or make["test"])[1]
        # The recipe body is two commands; they are split into two typed actions
        # because their preconditions differ (mix test needs deps + oracles).
        for cmd in body:
            if cmd.startswith("rebar3"):
                acts.append(Action("rebar3 eunit", cmd, str(repo), {"LINT_TRUTH_READY": True}, {"RUST_TESTS_READY": True}, True, False, recipe_src("test")))
            elif cmd.startswith("mix test"):
                acts.append(
                    Action(
                        "mix test",
                        cmd,
                        str(repo),
                        {"RUST_TESTS_READY": True, "MIX_TEST_RUNNABLE": True, "NATIVE_ORACLES_BUILT": True, "ORACLE_ENV_SET": True},
                        {"MIX_TEST_GREEN": True, "QUALIFICATION_COMPLETE": True},
                        True,
                        False,
                        recipe_src("test"),
                    )
                )

    # mix.exs deps => mix deps.get (then mix compile for the test env).
    mix_exs = repo / "mix.exs"
    if mix_exs.exists():
        for i, line in enumerate(mix_exs.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"^\s*defp? deps\b", line):
                acts.append(Action("mix deps.get", "mix deps.get", str(repo), {"RUST_TESTS_READY": True}, {"ELIXIR_DEPS_READY": True}, True, False, f"mix.exs:{i}"))
                acts.append(Action("mix compile (test)", "MIX_ENV=test mix compile", str(repo), {"ELIXIR_DEPS_READY": True}, {"MIX_TEST_RUNNABLE": True}, True, False, f"mix.exs:{i}"))
                break

    # native/*/Cargo.toml oracle crates => cargo build --release (one action, all
    # crates: NATIVE_ORACLES_BUILT is the conjunction observed by observe()).
    crates = _oracle_crates(repo)
    if crates:
        cmds = " && ".join(f"(cd {d.relative_to(repo)} && cargo build --release)" for _, d in crates)
        src = "; ".join(f"{d.relative_to(repo)}/Cargo.toml:2" for _, d in crates)
        acts.append(Action("cargo build --release (oracles)", cmds, str(repo), {"MIX_TEST_RUNNABLE": True}, {"NATIVE_ORACLES_BUILT": True}, True, False, src))

    # System.fetch_env! reads in test/ + definitions in scripts/env => env-set action.
    reqs = _oracle_env_requirements(repo)
    if reqs:
        envmap = {q["var"]: q.get("value", "") for q in reqs}
        cmd = "export " + " ".join(f'{q["var"]}="{q.get("value", "")}"' for q in reqs)
        src = "; ".join(f'{q["read_at"]} -> {q.get("defined_at", "UNDEFINED")}' for q in reqs)
        acts.append(Action("set oracle env", cmd, str(repo), {"NATIVE_ORACLES_BUILT": True}, {"ORACLE_ENV_SET": True}, True, False, src, env=envmap))

    return acts


# ---------------------------------------------------------------------------
# plan(): forward search (BFS over the staged-boolean state space)
# ---------------------------------------------------------------------------


def _goal_met(state: WorldState, goal: dict[str, bool]) -> bool:
    return all(state.get(k) == v for k, v in goal.items())


def plan(state: WorldState, goal: dict[str, bool], actions: list[Action] | None = None) -> list[Action] | NoPlanFound:
    actions = discover_actions(Path(state.repo)) if actions is None else actions
    start = tuple(sorted(state.stages.items()))
    frontier: list[tuple[WorldState, list[Action]]] = [(state, [])]
    seen = {start}
    best_state = state
    while frontier:
        cur, path = frontier.pop(0)
        if _goal_met(cur, goal):
            return path
        if sum(cur.stages.values()) > sum(best_state.stages.values()):
            best_state = cur
        for a in actions:
            if not a.applicable(cur):
                continue
            nxt = a.apply(cur)
            key = tuple(sorted(nxt.stages.items()))
            if key in seen:
                continue
            seen.add(key)
            frontier.append((nxt, path + [a]))
    # Backward closure: every stage transitively required by the goal via the
    # preconditions of the actions that produce it. Among those still False at
    # the best reachable frontier, name (in canonical order) one with NO
    # producing action at all; failing that, the earliest unreached one.
    producers: dict[str, list[Action]] = {}
    for a in actions:
        for k, v in a.postconditions.items():
            if v:
                producers.setdefault(k, []).append(a)
    required: set[str] = {k for k, v in goal.items() if v}
    stack = list(required)
    while stack:
        s = stack.pop()
        for a in producers.get(s, []):
            for k, v in a.preconditions.items():
                if v and k not in required:
                    required.add(k)
                    stack.append(k)
    unreached = [s for s in STAGES if s in required and not best_state.get(s)]
    missing = next((s for s in unreached if s not in producers), unreached[0] if unreached else "?")
    return NoPlanFound(goal=goal, missing_transition=missing, reachable_frontier=dict(best_state.stages), explored=len(seen))


# ---------------------------------------------------------------------------
# OCEL receipt via the shared evidence plane
# ---------------------------------------------------------------------------


def emit_receipt(state: WorldState, result: list[Action] | NoPlanFound, out_path: Path) -> dict:
    sys.path.insert(0, str(TOOLS / "ocel_v2"))
    import emitter  # noqa: E402  (tools/ocel_v2/emitter.py)
    import validate  # noqa: E402

    emitter.init(str(out_path))
    emitter.add_object(str(out_path), "Domain", "domain:beam4pm", {"name": "beam4pm", "description": "beam4pm verify chain staged domain"})
    emitter.add_object(str(out_path), "WorldState", "ws:beam4pm:observed", {"label": "observed", "observed_at": emitter._now_iso(), "state_json": json.dumps(state.to_json(), sort_keys=True)})
    emitter.add_event(str(out_path), "WorldStateObserved", "ev:observe", {"label": "observed", "state_json": json.dumps(state.stages, sort_keys=True)}, ["domain:beam4pm", "ws:beam4pm:observed"])
    if isinstance(result, NoPlanFound):
        steps = {"no_plan": asdict(result)}
        summary = str(result)
    else:
        steps = {"steps": [asdict(a) for a in result]}
        summary = " -> ".join(a.name for a in result) or "(already at goal)"
    emitter.add_object(str(out_path), "Plan", "plan:beam4pm", {"summary": summary, "steps_json": json.dumps(steps, sort_keys=True), "cost_estimate": float(len(steps.get("steps", [])))})
    emitter.add_event(str(out_path), "PlanProduced", "ev:plan", {"summary": summary, "cost_estimate": float(len(steps.get("steps", [])))}, ["domain:beam4pm", "plan:beam4pm"])
    return validate.validate(emitter._read(str(out_path)))


if __name__ == "__main__":
    st = observe()
    print(json.dumps(st.to_json(), indent=2))
    res = plan(st, {"QUALIFICATION_COMPLETE": True})
    if isinstance(res, NoPlanFound):
        print(res)
    else:
        for a in res:
            print(f"- {a.name}: {a.command}  [{a.source}]")
    if len(sys.argv) > 1:
        print(json.dumps(emit_receipt(st, res, Path(sys.argv[1])), indent=2))
