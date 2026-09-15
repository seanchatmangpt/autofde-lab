"""In-process WASM transport for the canonical bcinr-cmca allocator.

Loads the prebuilt ``wasm/artifacts/bcinr_cmca_wasm.wasm`` module (a
``wasm32-wasip1`` cdylib built from the *vendored* ``vendor/bcinr`` snapshot
at the commit recorded in
:mod:`autofde_lab.cmca.bcinr_bridge`'s ``VENDORED_BCINR_COMMIT`` -- see
``wasm/README.md`` for the build and provenance procedure) into the
``wasmtime`` runtime, and evaluates candidate rankings through the same
JSON wire contract as ``cmca_rank_cli``:

    request  {"candidates": [{"name": ..., "measures": [m0..m3]}]}
    response {"ranking": [{"name": ..., "share": ...}]}
    refusal  {"error": "..."}

This module never reimplements any allocator mathematics: request building,
measure axes, cardinality refusal, and response parsing all live in
:mod:`autofde_lab.cmca.bcinr_bridge`, shared by both transports. Its only
job is the ABI plumbing (allocate request buffer, call ``cmca_rank_json``,
read the ``[u32 LE len][bytes]`` result, free both buffers) and typed
refusals when the runtime or artifact is absent:

- :class:`BcinrWasmUnavailable` -- the ``wasmtime`` package is not installed
  (install the ``bcinr-wasm`` extra: ``uv sync --extra bcinr-wasm``).
- :class:`BcinrWasmModuleMissing` -- no ``.wasm`` artifact resolves (checked
  ``$BCINR_CMCA_WASM`` then ``wasm/artifacts/bcinr_cmca_wasm.wasm``);
  rebuild per ``wasm/README.md``.
- :class:`BcinrWasmProtocolError` -- the module answered with an error
  envelope or trapped. Never silently falls back to another transport: a
  protocol fault is a real defect to surface, not an availability gap.

Determinism matches the CLI transport: the artifact is built from the same
vendored source, the allocator is Q16.16 fixed-point, and one module
instance with a lock-serialized call path serves every request, so repeated
calls with identical requests yield bit-identical rankings.
"""

from __future__ import annotations

import json
import os
import struct
import threading
from functools import cache
from pathlib import Path

try:  # guarded exactly like the ocel-ecosystem bridge modules: absent
    # runtime is an availability gap (typed refusal), not an import crash.
    import wasmtime  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised only without the extra
    wasmtime = None  # type: ignore[assignment]

#: Whether the ``wasmtime`` runtime package is importable in this
#: environment. Availability of the *artifact* is checked separately by
#: :func:`find_bcinr_wasm` -- the two fail for different operator reasons
#: (missing extra vs. missing build) and refuse with different types.
AVAILABLE = wasmtime is not None

_ARTIFACT_BASENAME = "bcinr_cmca_wasm.wasm"


class BcinrWasmUnavailable(RuntimeError):
    """The ``wasmtime`` package is not installed (typed UNSUPPORTED refusal)."""


class BcinrWasmModuleMissing(RuntimeError):
    """No prebuilt ``bcinr_cmca_wasm.wasm`` artifact found (typed UNSUPPORTED
    refusal). Build it per ``wasm/README.md``; do not silently fall back."""


class BcinrWasmProtocolError(RuntimeError):
    """The WASM module answered with an error envelope or trapped."""


def find_bcinr_wasm() -> Path | None:
    """Locate the prebuilt WASM artifact, or ``None``.

    ``$BCINR_CMCA_WASM`` is authoritative when set: if it names a missing
    file, that is a misconfiguration to *refuse* (raising
    :class:`BcinrWasmModuleMissing`) -- an operator who points explicitly at
    an artifact must not silently get a different one. Unset, it resolves to
    this repo's ``wasm/artifacts/bcinr_cmca_wasm.wasm``, or ``None`` when
    that is absent.
    """
    env_path = os.environ.get("BCINR_CMCA_WASM")
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path
        raise BcinrWasmModuleMissing(
            f"$BCINR_CMCA_WASM names a missing file ({env_path}); refusing "
            "rather than silently using a different artifact"
        )

    vendored = (
        Path(__file__).resolve().parents[3] / "wasm" / "artifacts" / _ARTIFACT_BASENAME
    )
    if vendored.is_file():
        return vendored
    return None


class _WasmRuntime:
    """One wasmtime Engine/Module/Store/Instance, lock-serialized.

    A single instance keeps calls deterministic and cheap; the lock keeps
    the shared linear-memory ABI safe if a caller ever goes multi-threaded
    (today every caller is synchronous, like the CLI transport).
    """

    def __init__(self, artifact: Path) -> None:
        if wasmtime is None:
            raise BcinrWasmUnavailable(
                "the 'wasmtime' package is not installed; install the "
                "bcinr-wasm extra (uv sync --extra bcinr-wasm) or force the "
                "CLI transport with BCINR_CMCA_TRANSPORT=cli"
            )
        self._lock = threading.Lock()
        engine = wasmtime.Engine()
        module = wasmtime.Module.from_file(engine, str(artifact))
        linker = wasmtime.Linker(engine)
        # Defensive: the cdylib's dependency closure needs no WASI imports,
        # but defining them costs nothing and keeps instantiation working if
        # a future std path pulls one in.
        linker.define_wasi()
        store = wasmtime.Store(engine)
        store.set_wasi(wasmtime.WasiConfig())
        instance = linker.instantiate(store, module)
        exports = instance.exports(store)
        self._store = store
        self._memory = exports["memory"]
        self._alloc = exports["cmca_alloc"]
        self._free = exports["cmca_free"]
        self._rank = exports["cmca_rank_json"]

    def call_rank_json(self, request: dict) -> dict:
        """Serialize ``request``, call the module, parse the JSON response."""
        wire = json.dumps(request).encode("utf-8")
        with self._lock:
            req_ptr = self._alloc(self._store, len(wire))
            if req_ptr == 0:
                raise BcinrWasmProtocolError("cmca_alloc returned null")
            self._memory.write(self._store, wire, req_ptr)
            try:
                res_ptr = self._rank(self._store, req_ptr, len(wire))
            except Exception as exc:  # wasmtime trap -- never mask it
                self._free(self._store, req_ptr, len(wire))
                raise BcinrWasmProtocolError(
                    f"wasm trap in cmca_rank_json: {exc}"
                ) from exc
            self._free(self._store, req_ptr, len(wire))
            if res_ptr == 0:
                raise BcinrWasmProtocolError("cmca_rank_json returned null")

            prefix = self._memory.read(self._store, res_ptr, res_ptr + 4)
            if prefix is None or len(prefix) != 4:
                raise BcinrWasmProtocolError("missing 4-byte length prefix on result")
            (out_len,) = struct.unpack("<I", prefix)
            raw = self._memory.read(self._store, res_ptr + 4, res_ptr + 4 + out_len)
            self._free(self._store, res_ptr, 4 + out_len)

        if raw is None or len(raw) != out_len:
            raise BcinrWasmProtocolError(
                f"result buffer truncated: expected {out_len} bytes"
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BcinrWasmProtocolError(
                f"bcinr_cmca_wasm produced unparseable output: {raw[:200]!r}"
            ) from exc
        if not isinstance(payload, dict):
            raise BcinrWasmProtocolError(
                f"bcinr_cmca_wasm response is not a JSON object: {payload!r}"
            )
        return payload


@cache
def _runtime(artifact: str) -> _WasmRuntime:
    """Cached runtime per artifact path (rebuild picks up a new mtime-less
    path change only via a *different* path or process restart -- same
    freshness story as an already-resolved CLI binary path)."""
    return _WasmRuntime(Path(artifact))


def call_rank(request: dict, *, wasm_path: str | None = None) -> dict:
    """Evaluate one ranking request through the in-process WASM module.

    Returns the parsed response envelope (``{"ranking": ...}`` or
    ``{"error": ...}``); interpreting it is :mod:`bcinr_bridge`'s job, so
    both transports share one response-validation path.
    """
    artifact = Path(wasm_path) if wasm_path else find_bcinr_wasm()
    if artifact is None:
        raise BcinrWasmModuleMissing(
            "no prebuilt 'bcinr_cmca_wasm.wasm' found (checked "
            "$BCINR_CMCA_WASM and wasm/artifacts/bcinr_cmca_wasm.wasm) -- "
            "build it per wasm/README.md, or force the CLI transport with "
            "BCINR_CMCA_TRANSPORT=cli"
        )
    return _runtime(str(artifact)).call_rank_json(request)
