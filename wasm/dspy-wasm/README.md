# DSPy WASM court

This is a bounded compatibility experiment, not a general claim that DSPy works in
WebAssembly.

## Exact subject

- DSPy: `3.4.0`
- Pyodide: `314.0.7` (CPython 3.14 / Emscripten)
- Host: Node.js
- Authority: candidate observation only; no consequential actuation

The admitted WASM profile keeps the exact upstream `dspy==3.4.0` wheel intact
but deliberately excludes ambient provider dependencies. The court:

1. loads Pyodide-native compiled dependencies (`numpy`, `pydantic`, `regex`);
2. installs pure-Python DSPy core dependencies;
3. installs exact `gepa==0.1.4` and `dspy==3.4.0` wheels without expanding
   provider-only dependency closure;
4. projects the three `orjson` options/functions DSPy 3.4.0 hard-imports onto
   stdlib `json`;
5. executes a deterministic real `dspy.Module`; and
6. executes a real `dspy.Predict` through upstream DSPy 3.4's
   `dspy.LM(engine=...)` contract, where the engine can call only the explicit
   `autofde_host.complete` capability.

The host capability returns a receipt with `actuation: none`; the guest has no
LiteLLM/OpenAI provider stack and performs no provider network I/O.

A dependency that has no PyEmscripten/Pyodide-compatible wheel is reported as a typed
`BLOCKED` package-resolution edge. Missing Node/Pyodide host support is `UNSUPPORTED`.
Neither is rewritten or papered over by the court.

## Replay

```bash
cd wasm/dspy-wasm
npm install --ignore-scripts
npm run probe
```

Or through the repo-native Python wrapper:

```bash
python - <<'PY'
from autofde_lab.wasm.dspy import DSPyWasmProbe

result = DSPyWasmProbe().run()
print(result.status)
print(result.receipt)
PY
```

Expected output is exactly one JSON envelope with one of:

- `ALIVE`: exact DSPy import and deterministic module execution observed.
- `BLOCKED`: runtime/package/guest edge was reached and failed with a typed blocker.
- `UNSUPPORTED`: the host lacks Node or the pinned Pyodide package.

## Evidence ceiling

`ALIVE` establishes only this exact import + deterministic-module court. It does **not**
establish `dspy.Predict`, provider networking, optimizers such as GEPA/MIPROv2, tool use,
serialization parity, Ash integration, production readiness, or external standing.
Those become subsequent courts only after this one is admitted.


## Why the WASM profile exists

The first full-dependency court executed on GitHub Actions and reached Pyodide
successfully, then failed package resolution on exactly three non-Pyodide wheels:

```text
fastuuid<1.0,>=0.14.0
tokenizers<1.0,>=0.21.0
aiohttp<4.0,>=3.14.2
```

That failure is preserved as evidence for the boundary: these packages entered
through provider-oriented dependency closure, not the deterministic DSPy module
surface. The profile therefore excludes provider closure instead of porting it
into the guest.

## Capability boundary

```text
dspy.Predict
    ↓
dspy.LM(engine=HostEngine)
    ↓
HostEngine.complete(Request)
    ↓
autofde_host.complete(JSON)
    ↓
receipt { capability: lm.complete, actuation: none }
```

This is SELECT/CONSTRUCT evidence only. A successful court does not grant DO
authority and does not establish production standing.
