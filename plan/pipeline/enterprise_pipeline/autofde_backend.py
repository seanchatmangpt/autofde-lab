"""Backend seam: run an autofde-lab coprocessor kind as a real subprocess.

``solve(kind, payload, options=..., timeout=...)`` pipes a JSON envelope to
``python -m autofde_lab.coprocessor <kind>`` and parses the canonical JSON
reply into a typed ``BackendResult``.

Exit codes: 0 PLAN, 2 NO_PLAN/INFEASIBLE/REFUSED, 3 BLOCKED:<dep>.
A timeout never hangs: it yields status REFUSED with diagnostics
``{"reason": "TIMEOUT", "timeout": ...}``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PLAN = "PLAN"
NO_PLAN = "NO_PLAN"
INFEASIBLE = "INFEASIBLE"
REFUSED = "REFUSED"
BLOCKED = "BLOCKED"
STATUSES = (PLAN, NO_PLAN, INFEASIBLE, REFUSED, BLOCKED)

AUTOFDE_ROOT = "/Users/sac/autofde-lab"
AUTOFDE_VENV_PYTHON = os.path.join(AUTOFDE_ROOT, ".venv", "bin", "python")
DEFAULT_TIMEOUT = 300.0


@dataclass
class BackendResult:
    status: str
    actions: List[Any] = field(default_factory=list)
    cost: Optional[float] = None
    solver: str = ""
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    kind: str = ""
    exit_code: Optional[int] = None

    @property
    def ok(self) -> bool:
        return self.status == PLAN


def backend_python() -> str:
    """sys.executable when it is already the autofde-lab venv, else the venv python."""
    venv = os.path.realpath(os.path.join(AUTOFDE_ROOT, ".venv"))
    if os.path.realpath(sys.prefix) == venv:
        return sys.executable
    return AUTOFDE_VENV_PYTHON


def _fail(kind: str, status: str, reason: str, **diag: Any) -> BackendResult:
    d = {"reason": reason, **diag}
    return BackendResult(status=status, kind=kind, solver="", diagnostics=d, raw={})


def solve(
    kind: str,
    payload: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    python: Optional[str] = None,
) -> BackendResult:
    py = python or backend_python()
    envelope = json.dumps(
        {"kind": kind, "payload": payload, "options": options or {}},
        sort_keys=True,
        separators=(",", ":"),
    )
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AUTOFDE_WORK", tempfile.gettempdir())
    # Isolate the child from the caller's PYTHONPATH (plan/pipeline etc).
    env.pop("PYTHONPATH", None)
    try:
        proc = subprocess.run(
            [py, "-m", "autofde_lab.coprocessor", kind],
            input=envelope,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=tempfile.gettempdir(),
        )
    except subprocess.TimeoutExpired:
        return _fail(kind, REFUSED, "TIMEOUT", timeout=timeout)
    except OSError as exc:
        return _fail(kind, BLOCKED, f"BLOCKED:{type(exc).__name__}", error=str(exc))

    out = (proc.stdout or "").strip()
    try:
        raw = json.loads(out.splitlines()[-1]) if out else None
    except (ValueError, IndexError):
        raw = None
    if not isinstance(raw, dict) or raw.get("status") not in STATUSES:
        return _fail(
            kind,
            REFUSED,
            "UNPARSEABLE_BACKEND_OUTPUT",
            exit_code=proc.returncode,
            stderr_tail=(proc.stderr or "")[-2000:],
            stdout_tail=out[-500:],
        )
    return BackendResult(
        status=raw["status"],
        actions=list(raw.get("actions") or []),
        cost=raw.get("cost"),
        solver=raw.get("solver", ""),
        diagnostics=dict(raw.get("diagnostics") or {}),
        raw=raw,
        kind=raw.get("kind", kind),
        exit_code=proc.returncode,
    )
