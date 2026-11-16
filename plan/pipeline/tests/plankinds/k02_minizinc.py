"""K2: MiniZinc alignment eligibility (enterprise_pipeline.align, backend minizinc)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from . import Case, Outcome, Skip
from .k01_aries import build_store, draw_world

KIND = "K2"
TITLE = "MiniZinc alignment eligibility"
BACKEND = "minizinc"

# (id, expect, world params, build_store opts)
ELIG = [
    ("eligible", "PLAN", {}, {}),
    ("blacklisted", "NO_PLAN", {}, {"blacklist": True}),
    ("expired", "NO_PLAN", {"coi_expired": True}, {}),
    ("filtered", "NO_PLAN", {}, {"filtered": True}),
    ("nobody_unapproved_reactive_hire", "NO_PLAN", {}, {"unapproved": True}),
    ("second_provider_rescues", "PLAN", {}, {"providers": 2, "blacklist": True}),
    ("provider_rate_above_client_rate", "NO_PLAN", {}, {"rate_gte_client": True}),
    ("provider_rate_equals_client_rate", "NO_PLAN", {}, {"rate_eq_client": True}),
]


def elig_cases():
    return [Case(i, e, {"w": w, "opts": o}) for i, e, w, o in ELIG]


def build_state(case):
    from enterprise_pipeline import store
    w = draw_world(case.id, **case.payload["w"])
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "events.ndjson"
        ids = build_store(w, sp, stage=1, **case.payload["opts"])
        state = store.reduce(store.read(sp))
    return state, ids["wo"]


def to_outcome(elig, trigger) -> Outcome:
    chosen = sorted(p for p, ok in elig.items() if ok)
    st = "PLAN" if chosen and not trigger else "NO_PLAN"
    return Outcome(st, f"eligible_n={len(chosen)} reactive_hire={trigger}")


def probe():
    if not shutil.which("minizinc"):
        return Skip("minizinc binary absent", "brew install minizinc")
    return None


def cases():
    return elig_cases()


def run_backend(case, backend):
    from enterprise_pipeline import align
    state, wo_id = build_state(case)
    wo = next(x for x in state["work_orders"] if x["id"] == wo_id)
    fn = align.run_minizinc if backend == "minizinc" else align.run_cpsat
    return fn(state, wo)


def run(case) -> Outcome:
    return to_outcome(*run_backend(case, BACKEND))
