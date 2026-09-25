# DSPy WASM court

This is a bounded compatibility experiment, not a general claim that DSPy works in
WebAssembly.

## Exact subject

- DSPy: `3.4.0`
- Pyodide: `314.0.7` (CPython 3.14 / Emscripten)
- Host: Node.js
- Authority: candidate observation only; no consequential actuation

The first court attempts two things in order:

1. Install and import the unmodified `dspy==3.4.0` wheel and dependency closure in Pyodide.
2. Execute a real deterministic `dspy.Module` whose `forward()` returns a
   `dspy.Prediction`, with zero LM calls.

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
