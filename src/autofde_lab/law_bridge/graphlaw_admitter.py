"""GraphLaw bridge: SELECT -> ADMIT.

Drives the pinned GraphLaw WASI module (priv/graphlaw.wasm) through wasmtime using the
gl_alloc / gl_call / gl_free JSON ABI. An initial RDF state, an optional rule pack
(n3 / rdfs / owl-rl / datalog-style steps) and a candidate action list are admitted
as one `law` request: ADMITTED carries the terminal state hash and the BLAKE3 receipt
chain; REFUSED names the first step whose precondition is unmet and the unmet triples,
and no later step is admitted.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import wasmtime

DEFAULT_WASM = Path(os.environ.get("GRAPHLAW_WASM", "/Users/sac/graphlaw/priv/graphlaw.wasm"))


class GraphLawUnavailable(RuntimeError):
    """The WASM artifact is missing or cannot be instantiated."""


@dataclass(frozen=True)
class Action:
    """One candidate step; pre/add/del are N-Triples strings."""

    name: str
    pre: str = ""
    add: str = ""
    delete: str = ""
    pre_not: str = ""

    def to_wire(self) -> Dict[str, str]:
        d = {"name": self.name, "pre": self.pre, "add": self.add, "del": self.delete}
        if self.pre_not:
            d["pre_not"] = self.pre_not
        return d


@dataclass(frozen=True)
class Admitted:
    state_id: str
    receipts: Tuple[Dict[str, Any], ...]
    nquads: str
    admitted_actions: Tuple[str, ...]

    status = "ADMITTED"

    @property
    def chain(self) -> List[str]:
        return [r["child"] for r in self.receipts]


@dataclass(frozen=True)
class Refused:
    index: Optional[int]
    action: Optional[str]
    unmet: Tuple[str, ...]
    error: Dict[str, Any] = field(default_factory=dict)
    admitted_actions: Tuple[str, ...] = ()

    status = "REFUSED"


Verdict = Admitted | Refused


class GraphLawAdmitter:
    def __init__(self, wasm_path: Path = DEFAULT_WASM):
        if not Path(wasm_path).is_file():
            raise GraphLawUnavailable(f"missing artifact: {wasm_path}")
        cfg = wasmtime.Config()
        cfg.wasm_exceptions = True
        self._engine = wasmtime.Engine(cfg)
        try:
            self._module = wasmtime.Module.from_file(self._engine, str(wasm_path))
        except Exception as exc:  # noqa: BLE001
            raise GraphLawUnavailable(str(exc)) from exc

    def call(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """One JSON-ABI round trip on a fresh instance (no shared state between calls)."""
        store = wasmtime.Store(self._engine)
        linker = wasmtime.Linker(self._engine)
        linker.define_wasi()
        store.set_wasi(wasmtime.WasiConfig())
        inst = linker.instantiate(store, self._module)
        ex = inst.exports(store)
        mem, alloc, call, free = ex["memory"], ex["gl_alloc"], ex["gl_call"], ex["gl_free"]
        body = json.dumps(request).encode()
        ptr = alloc(store, len(body))
        if not ptr:
            raise GraphLawUnavailable("gl_alloc returned null")
        mem.write(store, body, ptr)
        packed = call(store, ptr, len(body)) & 0xFFFFFFFFFFFFFFFF
        out_ptr, out_len = packed >> 32, packed & 0xFFFFFFFF
        out = bytes(mem.read(store, out_ptr, out_ptr + out_len))
        free(store, out_ptr, out_len)
        return json.loads(out)

    def admit(
        self,
        initial: str,
        actions: Sequence[Action],
        goal: str = "",
        rules: Sequence[Dict[str, Any]] = (),
        dialect: str = "ntriples",
    ) -> Verdict:
        """Admit `actions` over `initial` after applying `rules` (list of law steps, e.g.
        {"step": "n3", "rules": "..."}, {"step": "rdfs"}, {"step": "owl-rl"})."""
        steps: List[Dict[str, Any]] = list(rules)
        steps.append(
            {"step": "plan", "plan": {"actions": [a.to_wire() for a in actions], "goal": goal}}
        )
        resp = self.call(
            {"op": "law", "data": {"text": initial, "dialect": dialect}, "steps": steps,
             "ceiling": "construct", "unverified_lease": True, "now_unix": 0,
             "lease": {"id": "bridge", "holder": "autofde-lab", "ceiling": "construct",
                       "scope": ["admit:plan", "derive:n3", "derive:rdfs", "derive:owl-rl"],
                       "expires_unix": 4102444800}}
        )
        return _verdict(resp, [a.name for a in actions])


def _verdict(resp: Dict[str, Any], names: List[str]) -> Verdict:
    if resp.get("ok"):
        receipts = tuple(resp["receipts"])
        done = tuple(names[r["index"]] for r in receipts if "index" in r)
        return Admitted(resp["states"][-1], receipts, resp.get("nquads", ""), done)
    err = resp.get("error", {})
    det = err.get("details") or {}
    index = det.get("index")
    return Refused(
        index=index,
        action=det.get("action") or (names[index] if isinstance(index, int) and index < len(names) else None),
        unmet=tuple(det.get("unmet") or det.get("missing") or ()),
        error=err,
        admitted_actions=tuple(names[:index]) if isinstance(index, int) else (),
    )
