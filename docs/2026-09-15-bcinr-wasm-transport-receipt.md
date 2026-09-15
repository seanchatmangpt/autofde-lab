# Receipt: bcinr-cmca in-process WASM transport (Python + BEAM)

**Date:** 2026-09-15
**Repo/base:** `seanchatmangpt/autofde-lab`, branch `feat/semantic-model-manufacturing`
**Commits:** `465616a3` (feat(cmca): WASM transport) + this receipt commit
**Standing:** `ALIVE` — observed execution against the exact admitted subjects, this session.

## Subject

The default `bcinr` CMCA engine (`autofde_lab.cmca.cascade.MultifractalCascadeAllocator`,
engine `"bcinr"`) previously reached the vendored Rust allocator only through the
`cmca_rank_cli` subprocess. This change adds a second transport compiled from the
*same vendored snapshot* (`2ae60cf0`, per `vendor/bcinr/VENDORING.md`) and makes it
the default first hop in both host languages:

- **Python:** `autofde_lab.cmca.bcinr_wasm` loads the prebuilt
  `wasm/artifacts/bcinr_cmca_wasm.wasm` (`wasm32-wasip1` cdylib, source at
  `wasm/bcinr-cmca-wasm/`, a line-for-line port of the vendored
  `cmca_rank_cli.rs` ranking entry point to an `extern "C"` ABI) via `wasmtime`
  in-process. `bcinr_bridge.rank_candidates` dispatches wasm-first, falling
  through to the CLI subprocess only on wasm *unavailability*; a wasm protocol
  fault raises. `$BCINR_CMCA_TRANSPORT=wasm|cli` forces a transport;
  forced-but-absent, unknown values, and a mis-pointed `$BCINR_CMCA_WASM` are
  typed refusals, never silent switches.
- **BEAM:** `ash_autofde` (new sibling project, initial commit `11e0559`,
  local `main`) hosts the *same artifact* in-VM via `wasmex` 0.15.1 as
  `AshAutofde.WasmCmca` — one named engine, same linear-memory JSON ABI,
  trap-restart semantics copied from beam4pm's `Rust4PM` engine.

## Verification ladder (commands and exit codes, all observed this session)

| Gate | Command | Result |
|---|---|---|
| WASM build | `cargo build --release --target wasm32-wasip1 --manifest-path wasm/bcinr-cmca-wasm/Cargo.toml` | exit 0; compiled against `vendor/bcinr` (pinned snapshot, not `~/bcinr`) |
| Module shape | wasmtime `Module.imports/exports` over the artifact | exports exactly `memory`, `cmca_alloc`, `cmca_free`, `cmca_rank_json`; WASI imports only |
| Cross-transport identity | identical canonical request through wasm and vendored-CLI | **bit-identical JSON payloads** (`test_wasm_transport_is_bit_identical_to_vendored_cli`) |
| Default engine e2e | `MultifractalCascadeAllocator().allocate` over prime budgets | 104726 ≤ 104729 ticks (floor residual ≤ active branches); conserved |
| Python suites | `pytest tests/cmca/ tests/beam/` | 42 passed |
| Consumers | `pytest tests/agent/test_autodev_loop_chicago.py`, `pytest tests/ecosystem/test_gymact_cmca_semantic_runtime_ocel_chicago.py` | 2 + 2 passed |
| BEAM suite | `mix test` in `~/ash_autofde` | 1 doctest, 10 tests, 0 failures |
| Cross-host identity | golden fixture captured via Python/wasmtime, pinned in `AshAutofde.WasmCmcaTest` | exact-equal Q16.16 shares (they are exact binary fractions) |
| Lock | `uv lock` | resolved 436 packages, added `wasmtime 48.0.0` (opt-in `bcinr-wasm` extra) |

## Falsifiers attempted / law changes

- New Chicago test `test_forced_wasm_with_missing_artifact_refuses_not_falls_back`
  **failed against the first implementation**: a mis-pointed `$BCINR_CMCA_WASM`
  silently fell through to the repo artifact. Fixed — the env var is now
  authoritative; a set-but-missing path refuses.
- `test_bcinr_cmca_chicago.py::test_missing_binary_is_typed_refusal_not_silent_fallback`
  broke by design: CLI-absence no longer refuses when wasm serves. Updated to
  `test_all_transports_unavailable_...` — the law (never silently degrade to
  `reference-softmax`) is unchanged, now enforced across both transports; the
  suite's skip-gate admits either transport.
- `ash_autofde`'s PortBridge test failed on arrival (pre-dating this change):
  the resource always sent `tau`, which the bcinr engine refuses since
  upstream commit `39d244a9` made it the default. Fixed by removing the dead
  `tau` argument from the Elixir allocate action and port payload (the Python
  port already maps absent tau → `None`, the lawful no-tau call).

## Scoping / what this receipt does NOT claim

- The wasm and CLI transports agree because both are built from vendored
  `2ae60cf0`. `~/bcinr` HEAD (`c37ef2dc`) has drifted past the pin with
  uncommitted test edits; agreement is asserted only against the vendored build
  (`_vendored_cli/0` skips otherwise).
- `cmca/__init__.py` carries pre-existing RUF022 lint debt; left untouched
  (no unrelated refactors on a changed production path).
- `ash_autofde` has no git remote; `11e0559` is local-only until a remote is
  created. In autofde-lab, the concurrent `autodev_*.py` working-tree edits and
  `docs/jira/v26.9.15/` remain uncommitted by their author and untouched here.
