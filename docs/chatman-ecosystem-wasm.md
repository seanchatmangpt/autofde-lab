# Chatman ecosystem WebAssembly federation

`skdecide.wasm` makes `scikit-decide` the canonical Python control surface for
the reusable Chatman ecosystem layer. It admits sixteen exact source revisions,
maps each source to one deterministic `.wasm` artifact identity, exposes typed
Python bindings, and requires every invocation to return a receipt-bound JSON
response.

## Python binding

```python
from skdecide.wasm import ChatmanEcosystem

ecosystem = ChatmanEcosystem("build/chatman-wasm")
result = ecosystem.ggen.invoke(
    "render",
    {"graph": "urn:example"},
    authority={"actuation": "none"},
)
assert result.status == "ALIVE"
```

Bindings are available as attributes such as `ggen`, `wasm4pm`, `lsp_max`,
`star_toml`, `mfact`, `powl`, `fgn`, `mfw`, `mmdio`, `cargo_cicd`, and
`ferroplan`. The MU sources are exposed as `mu_mcpp` and `mu_truex`, with
compatibility aliases `mcpp` and `truex`.

The default Wasmtime backend instantiates core-Wasm modules with **zero
imports**. A module that requests filesystem, network, clock, randomness, or
process capabilities is refused. Future WASI/component-model authority must be
introduced through an explicit host policy rather than ambient inheritance.

## Guest ABI

The embedded WIT contract is available as `skdecide.wasm.WIT`. The currently
executed core-Wasm transport exports:

- `memory`
- `chatman_alloc(i32) -> i32`
- `chatman_invoke(i32, i32) -> i64`
- optional `chatman_dealloc(i32, i32)`

`chatman_invoke` receives canonical UTF-8 JSON. Its `i64` result packs the
response pointer in the high 32 bits and response length in the low 32 bits.
The response must use `chatman.ecosystem.response.v1`, contain an explicit
standing state, and bind its receipt to the component name and exact source
revision.

## Manufacturing artifacts

Generated `.wasm` files are projections and are not committed. The package
emits the exact registry and WIT contract with:

```bash
python -m skdecide.wasm.build --emit-contract
```

For a complete build, materialize every exact source revision beneath
`.chatman/sources/<repository-name>` and run:

```bash
python -m skdecide.wasm.build \
  --source-root .chatman/sources \
  --output build/chatman-wasm
```

Each source repository owns `.chatman/wasm-build.py`. The central builder
refuses to invent semantics for a library that has no source-owned adapter,
refuses a source tree whose `HEAD` differs from the registry pin, captures the
adapter command and exit code, hashes the produced artifact, and emits
`build-report.json`.

A successful adapter build is only `PARTIAL_ALIVE`; the component reaches
`ALIVE` after the exact artifact is invoked through the Python binding and its
receipt is replayed. Missing sources, missing adapters, source drift, failed
builds, and invalid guest responses remain typed blockers rather than being
collapsed into success.
