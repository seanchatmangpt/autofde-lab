"""K3: CP-SAT alignment eligibility (align.run_cpsat) plus differential against K2."""
from __future__ import annotations

from pathlib import Path

from enterprise_pipeline import align

from . import Case, Outcome, Skip
from .k02_minizinc import elig_cases, run_backend, to_outcome
from .k02_minizinc import probe as mzn_probe

KIND = "K3"
TITLE = "CP-SAT alignment eligibility"

# Registered divergences: case id -> reason (KD rows). Anything else that disagrees fails the test.
REGISTERED_DIVERGENCES: dict = {}  # empty: align.py now passes the real client rate (margin fixed)


def probe():
    from enterprise_pipeline import autofde_backend
    py = autofde_backend.backend_python()
    if not Path(py).exists():
        return Skip(f"autofde-lab venv missing at {py}", "create /Users/sac/autofde-lab/.venv")
    return None


def cases():
    return elig_cases()


def run(case) -> Outcome:
    return to_outcome(*run_backend(case, "cpsat"))


def differential():
    """-> [{case, minizinc, cpsat, agree}] on identical inputs (same drawn world, same state)."""
    rows = []
    for c in elig_cases():
        m = to_outcome(*run_backend(c, "minizinc"))
        s = to_outcome(*run_backend(c, "cpsat"))
        rows.append({"case": c.id, "minizinc": (m.status, m.detail), "cpsat": (s.status, s.detail),
                     "agree": m.status == s.status})
    return rows
