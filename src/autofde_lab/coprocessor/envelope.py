"""Coprocessor envelope: typed request/response, canonical JSON, kind registry.

Registry contract (for lanes B2/B3/B4, which own kinds_search, kinds_planning,
kinds_rl respectively):

1. A kind handler is ``Callable[[Envelope], Result]``. It must never raise for
   expected conditions; return a Result with the appropriate status instead.
   Unexpected exceptions are mapped to REFUSED by ``dispatch``.
2. Register at import time from your own module with the decorator::

       from autofde_lab.coprocessor.envelope import register_kind, Envelope, Result, Status

       @register_kind("my_kind", module="kinds_search")
       def _my_kind(env: Envelope) -> Result: ...

3. ``__main__`` lazily imports kinds_pddl, kinds_search, kinds_planning and
   kinds_rl via ``load_kind_modules``. A module that is absent
   (ModuleNotFoundError on that module itself) is recorded in ``ABSENT_MODULES``;
   a kind requested while its module is absent yields BLOCKED:<module>.
4. A missing third-party dependency inside a handler is reported by returning
   ``blocked("<dep>")`` (status BLOCKED, diagnostics ``blocked_on``).
5. Wire format. Request (stdin, JSON object)::

       {"kind": str (optional; argv wins), "payload": {...}, "options": {...}}

   Response (stdout, canonical JSON: sorted keys, separators (",", ":"))::

       {"actions": [...], "cost": number|null, "diagnostics": {...},
        "kind": str, "solver": str, "status": Status}

   Exit codes: 0 PLAN, 2 NO_PLAN/INFEASIBLE/REFUSED, 3 BLOCKED.
6. Zero in-tree writes: use ``scratch_dir()`` (AUTOFDE_WORK, default TMPDIR)
   and ``subprocess_env()`` (sets PYTHONDONTWRITEBYTECODE=1).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

PLAN = "PLAN"
NO_PLAN = "NO_PLAN"
INFEASIBLE = "INFEASIBLE"
REFUSED = "REFUSED"
BLOCKED = "BLOCKED"


class Status:
    PLAN = PLAN
    NO_PLAN = NO_PLAN
    INFEASIBLE = INFEASIBLE
    REFUSED = REFUSED
    BLOCKED = BLOCKED
    ALL = (PLAN, NO_PLAN, INFEASIBLE, REFUSED, BLOCKED)


EXIT_CODES = {
    PLAN: 0,
    NO_PLAN: 2,
    INFEASIBLE: 2,
    REFUSED: 2,
    BLOCKED: 3,
}

KIND_MODULES = ("kinds_pddl", "kinds_search", "kinds_planning", "kinds_rl")


@dataclass(frozen=True)
class Envelope:
    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_json(text: str) -> "Envelope":
        obj = json.loads(text)
        if not isinstance(obj, dict):
            raise ValueError("envelope must be a JSON object")
        if not isinstance(obj.get("kind", ""), str):
            raise ValueError("'kind' must be a string")
        payload = obj.get("payload", {})
        options = obj.get("options", {})
        if not isinstance(payload, dict) or not isinstance(options, dict):
            raise ValueError("'payload' and 'options' must be JSON objects")
        return Envelope(kind=obj.get("kind", ""), payload=payload, options=options)


@dataclass
class Result:
    status: str
    kind: str = ""
    actions: List[Any] = field(default_factory=list)
    cost: Optional[float] = None
    solver: str = ""
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        if self.status not in Status.ALL:
            raise ValueError(f"unknown status {self.status!r}")
        return {
            "actions": list(self.actions),
            "cost": self.cost,
            "diagnostics": dict(self.diagnostics),
            "kind": self.kind,
            "solver": self.solver,
            "status": self.status,
        }

    def exit_code(self) -> int:
        return EXIT_CODES[self.status]


def canonical_json(obj: Any) -> str:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def blocked(dep: str, kind: str = "", solver: str = "") -> Result:
    return Result(
        BLOCKED,
        kind=kind,
        solver=solver,
        diagnostics={"blocked_on": dep, "reason": f"BLOCKED:{dep}"},
    )


def refused(reason: str, kind: str = "", solver: str = "", **diag: Any) -> Result:
    return Result(
        REFUSED, kind=kind, solver=solver, diagnostics={"reason": reason, **diag}
    )


Handler = Callable[[Envelope], Result]
REGISTRY: Dict[str, Handler] = {}
KIND_MODULE: Dict[str, str] = {}
ABSENT_MODULES: List[str] = []


def register_kind(name: str, module: str = "") -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        REGISTRY[name] = fn
        KIND_MODULE[name] = module
        return fn

    return deco


def load_kind_modules() -> None:
    """Import every kinds_* module; record the absent ones."""
    import importlib

    ABSENT_MODULES.clear()
    for mod in KIND_MODULES:
        full = f"autofde_lab.coprocessor.{mod}"
        try:
            importlib.import_module(full)
        except ModuleNotFoundError as exc:
            if exc.name == full:
                ABSENT_MODULES.append(mod)
            else:
                raise


def scratch_dir() -> str:
    base = os.environ.get("AUTOFDE_WORK") or tempfile.gettempdir()
    os.makedirs(base, exist_ok=True)
    return base


def subprocess_env() -> Dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def dispatch(env: Envelope) -> Result:
    handler = REGISTRY.get(env.kind)
    if handler is None:
        absent = [m for m in ABSENT_MODULES]
        if absent:
            return blocked(absent[0], kind=env.kind)
        return refused(f"unknown kind {env.kind!r}", kind=env.kind,
                       known=sorted(REGISTRY))
    try:
        res = handler(env)
    except Exception as exc:  # noqa: BLE001
        return refused(f"{type(exc).__name__}: {exc}", kind=env.kind)
    if not res.kind:
        res.kind = env.kind
    return res
