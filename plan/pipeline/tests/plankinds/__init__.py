"""Plan-kind adapter contract. One module per kind (k01_aries.py ...), each exposing:

    KIND   = "K1"                        # id from the approved plan
    TITLE  = "temporal PDDL 2.1 (aries)"
    def probe() -> Skip | None           # None = runnable now; Skip carries the reason + install hint
    def cases() -> list[Case]            # deterministic, small; built from files/solvers, no literals
    def run(case) -> Outcome             # real subprocess/solver only, never a mock

Every kind ends up as a row in the matrix; nothing is silently skipped."""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field

STATUS = ("PLAN", "NO_PLAN", "REFUSED", "INFEASIBLE", "SKIP", "UNSUPPORTED")


@dataclass(frozen=True)
class Skip:
    reason: str                  # e.g. "no cargo build of ferroplan"
    hint: str = ""               # command that would make it runnable


@dataclass(frozen=True)
class Case:
    id: str
    expect: str                  # one of STATUS (what the case is built to produce)
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Outcome:
    status: str                  # one of STATUS
    detail: str = ""             # exit code / refusal class / solver status line
    artifact: str = ""           # path or sha of what the real tool produced


def registry() -> dict:
    """{KIND: module} for every plankinds.kNN_* module present."""
    out = {}
    for m in pkgutil.iter_modules(__path__):
        if m.name.startswith("k"):
            mod = importlib.import_module(f"{__name__}.{m.name}")
            out[mod.KIND] = mod
    return dict(sorted(out.items(), key=lambda kv: int(kv[0][1:])))


def run_kind(mod) -> list[dict]:
    """Rows for the matrix: one per case, or one SKIP row when the kind is not runnable."""
    sk = mod.probe()
    if sk:
        return [{"kind": mod.KIND, "title": mod.TITLE, "case": "-", "expect": "-",
                 "status": "SKIP", "detail": f"{sk.reason} | {sk.hint}"}]
    rows = []
    for c in mod.cases():
        o = mod.run(c)
        rows.append({"kind": mod.KIND, "title": mod.TITLE, "case": c.id, "expect": c.expect,
                     "status": o.status, "detail": o.detail, "ok": o.status == c.expect})
    return rows
