# wasm/ — in-process WASM transport for the canonical bcinr-cmca allocator

## What this is

`bcinr-cmca-wasm/` is a `wasm32-wasip1` cdylib shim whose ranking logic is a
line-for-line port of the vendored
`vendor/bcinr/crates/bcinr-cmca/src/bin/cmca_rank_cli.rs` (same JSON wire
contract, phantom padding, factor pinning, flat tree, and
`allocator::allocate` call), with the process boundary replaced by three
`extern "C"` exports (`cmca_alloc`, `cmca_free`, `cmca_rank_json`) that
`src/autofde_lab/cmca/bcinr_wasm.py` calls in-process through `wasmtime`.

It lives **outside** `vendor/bcinr` on purpose: the vendored crates are
byte-for-byte snapshots of upstream commit `2ae60cf0` (see
`vendor/bcinr/VENDORING.md`), and adding a workspace member there would
break the verbatim provenance the Chicago test asserts. The shim
path-depends on the vendored crate, so the artifact and the native
`cmca_rank_cli` are built from the *same* pinned source — which is why
`test_wasm_transport_is_bit_identical_to_vendored_cli` can and does assert
bit-identical JSON across both transports.

`artifacts/bcinr_cmca_wasm.wasm` is the committed prebuilt module so
consumers (and CI) need neither a Rust toolchain nor a subprocess binary —
only `uv sync --extra bcinr-wasm`.

## Build / refresh procedure

```bash
cargo build --release --target wasm32-wasip1 \
  --manifest-path wasm/bcinr-cmca-wasm/Cargo.toml
cp wasm/bcinr-cmca-wasm/target/wasm32-wasip1/release/bcinr_cmca_wasm.wasm \
  wasm/artifacts/
```

Refresh the artifact whenever `VENDORED_BCINR_COMMIT`
(`src/autofde_lab/cmca/bcinr_bridge.py`) moves: vendor the new commit, then
rebuild and re-commit the artifact in the same change, so the two
transports never silently diverge across commits.

## Provenance

| Field | Value |
| :--- | :--- |
| Built from | `vendor/bcinr` @ `2ae60cf0` (see `VENDORING.md`) |
| Target | `wasm32-wasip1`, release profile (fat LTO, 1 codegen unit, `panic = "abort"`, mirroring the vendored workspace) |
| ABI | `cmca_alloc(len) -> ptr`, `cmca_free(ptr, len)`, `cmca_rank_json(ptr, len) -> [u32 LE len][JSON bytes]` |
| Error contract | `{"error": "..."}` envelope in the response payload — same convention as `cmca_rank_cli` |

## Runtime resolution (Python side)

`autofde_lab.cmca.bcinr_bridge.rank_candidates` tries the WASM transport
first (`$BCINR_CMCA_WASM`, then `wasm/artifacts/bcinr_cmca_wasm.wasm`),
falling through to the `cmca_rank_cli` subprocess only on WASM
*unavailability*; `$BCINR_CMCA_TRANSPORT=wasm|cli` forces one, and a
forced-but-absent transport is a typed refusal, never a silent switch.
