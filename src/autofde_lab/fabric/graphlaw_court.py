"""Independent plan-admission court backed by the published ``graphlaw`` WASI module.

ABI (UTF-8 JSON in/out): exports ``gl_alloc(len)->ptr``, ``gl_call(ptr,len)->i64``
packed ``(out_ptr<<32)|out_len`` (consumes the request buffer), ``gl_free(ptr,len)``
and ``memory``. Typed refusals, never a silent fallback:

- :class:`GraphlawUnavailable` -- ``wasmtime`` is not installed.
- :class:`GraphlawModuleMissing` -- no module resolves (``$GRAPHLAW_WASM`` then
  the default graphlaw build path).
- :class:`GraphlawProtocolError` -- trap, null buffer, or unparseable response.
- :class:`PlanRefused` -- the court answered ``ok:false`` for the plan.
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

try:
    import wasmtime  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    wasmtime = None  # type: ignore[assignment]

AVAILABLE = wasmtime is not None

DEFAULT_WASM = Path(
    "/Users/sac/graphlaw/target/wasm-abi/wasm32-wasip1/wasm/graphlaw_wasm.wasm"
)

Triple = tuple[str, str, str]


class GraphlawUnavailable(RuntimeError):
    """The ``wasmtime`` package is not installed."""


class GraphlawModuleMissing(RuntimeError):
    """No graphlaw WASM module found."""


class GraphlawProtocolError(RuntimeError):
    """Module trapped or answered outside the wire contract."""


class PlanRefused(RuntimeError):
    """The graphlaw court refused the plan."""

    court_refusal = True

    def __init__(
        self,
        index: int | None,
        action: str | None,
        message: str,
        *,
        unmet: Sequence[str] = (),
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.index = index
        self.action = action
        self.message = message
        #: N-Quads lines the failing step required but the state lacked.
        self.unmet: tuple[str, ...] = tuple(unmet)
        #: The graphlaw ``error.details`` object (``code``, ``index``, ...), if any.
        self.details = details


@dataclass(frozen=True, slots=True)
class AdmittedPlan:
    receipts: tuple[Mapping[str, Any], ...]
    states: tuple[Any, ...]


def find_graphlaw_wasm() -> Path:
    env = os.environ.get("GRAPHLAW_WASM")
    if env:
        p = Path(env)
        if p.is_file():
            return p
        raise GraphlawModuleMissing(f"$GRAPHLAW_WASM names a missing file ({env})")
    if DEFAULT_WASM.is_file():
        return DEFAULT_WASM
    raise GraphlawModuleMissing(
        f"no graphlaw module (checked $GRAPHLAW_WASM and {DEFAULT_WASM})"
    )


class _Runtime:
    def __init__(self, artifact: Path) -> None:
        if wasmtime is None:
            raise GraphlawUnavailable(
                "the 'wasmtime' package is not installed (bcinr-wasm extra)"
            )
        self._lock = threading.Lock()
        engine = wasmtime.Engine()
        module = wasmtime.Module.from_file(engine, str(artifact))
        linker = wasmtime.Linker(engine)
        linker.define_wasi()
        store = wasmtime.Store(engine)
        store.set_wasi(wasmtime.WasiConfig())
        exports: Any = linker.instantiate(store, module).exports(store)
        self._store = store
        self._memory = exports["memory"]
        self._alloc = exports["gl_alloc"]
        self._call = exports["gl_call"]
        self._free = exports["gl_free"]

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        wire = json.dumps(request, sort_keys=True).encode("utf-8")
        with self._lock:
            ptr = self._alloc(self._store, len(wire))
            if ptr == 0:
                raise GraphlawProtocolError("gl_alloc returned null")
            self._memory.write(self._store, wire, ptr)
            try:
                packed = self._call(self._store, ptr, len(wire))
            except Exception as exc:
                raise GraphlawProtocolError(f"wasm trap in gl_call: {exc}") from exc
            packed &= 0xFFFFFFFFFFFFFFFF
            out_ptr, out_len = packed >> 32, packed & 0xFFFFFFFF
            if out_ptr == 0:
                raise GraphlawProtocolError("gl_call returned null")
            raw = self._memory.read(self._store, out_ptr, out_ptr + out_len)
            self._free(self._store, out_ptr, out_len)
        if len(raw) != out_len:
            raise GraphlawProtocolError("result buffer truncated")
        try:
            payload = json.loads(bytes(raw).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise GraphlawProtocolError(f"unparseable output: {bytes(raw)[:200]!r}") from exc
        if not isinstance(payload, dict):
            raise GraphlawProtocolError(f"response not a JSON object: {payload!r}")
        return payload


@cache
def _runtime(artifact: str) -> _Runtime:
    return _Runtime(Path(artifact))


def _nt(triple: Triple) -> str:
    s, p, o = triple
    return f"<{s}> <{p}> <{o}> ."


def _nt_block(triples: Sequence[Triple]) -> str:
    return "\n".join(_nt(t) for t in triples)


def _nt_list(triples: Sequence[Triple]) -> list[str]:
    return [_nt(t) for t in triples]


def build_request(
    state_triples: Sequence[Triple],
    actions: Sequence[Mapping[str, Any]],
    goal_triples: Sequence[Triple],
) -> dict[str, Any]:
    """Build the ``law``/``plan`` request. Action ``pre``/``add``/``del`` are
    sequences of (s,p,o) IRI tuples, encoded as N-Triples strings."""
    return {
        "op": "law",
        "data": {"text": _nt_block(state_triples), "dialect": "ntriples"},
        "steps": [
            {
                "step": "plan",
                "plan": {
                    "actions": [
                        {
                            "name": a["name"],
                            "pre": _nt_block(a.get("pre", ())),
                            "add": _nt_block(a.get("add", ())),
                            "del": _nt_block(a.get("del", ())),
                        }
                        for a in actions
                    ],
                    "goal": _nt_block(goal_triples),
                },
            }
        ],
    }


_STEP_RE = re.compile(r"plan refused at step (\d+)")


def admit_plan(
    state_triples: Sequence[Triple],
    actions: Sequence[Mapping[str, Any]],
    goal_triples: Sequence[Triple],
    *,
    wasm_path: str | None = None,
) -> AdmittedPlan:
    artifact = Path(wasm_path) if wasm_path else find_graphlaw_wasm()
    response = _runtime(str(artifact)).call(
        build_request(state_triples, actions, goal_triples)
    )
    if response.get("ok") is not True:
        err = response.get("error")
        message = str(err.get("message", err)) if isinstance(err, dict) else str(err)
        details = err.get("details") if isinstance(err, dict) else None
        if isinstance(details, dict) and details.get("code") == "PlanRefused":
            index = int(details["index"])
            name = str(details["action"]) if details.get("action") is not None else None
            raise PlanRefused(
                index,
                name,
                message,
                unmet=tuple(str(u) for u in details.get("unmet", ())),
                details=details,
            )
        # A module built before structured details existed: fall back to the
        # message text. Refusals other than a plan refusal keep no index.
        m = _STEP_RE.match(message)
        index = int(m.group(1)) if m else None
        name = (
            str(actions[index]["name"])
            if index is not None and index < len(actions)
            else None
        )
        raise PlanRefused(
            index,
            name,
            message,
            details=details if isinstance(details, dict) else None,
        )
    return AdmittedPlan(
        receipts=tuple(response.get("receipts", ())),
        states=tuple(response.get("states", ())),
    )
