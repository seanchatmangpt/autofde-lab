# Vendored: `bcinr-cmca` (Chatman Multifractal Consequence Allocation)

| Field | Value |
| :--- | :--- |
| Upstream repository | `https://github.com/seanchatmangpt/bcinr` |
| Pinned commit | `2ae60cf0` — `chore(release): unfence every publishable crate, bump the release set to 26.9.15` |
| Vendored on | 2026-09-15 |
| License | MIT OR Apache-2.0 (upstream `Cargo.toml`); crate is `publish = false` |
| Vendored scope | `crates/bcinr-cmca` (byte-for-byte) and `crates/bcinr-logic` (byte-for-byte, the one path dependency) plus this trimmed workspace `Cargo.toml` |
| Excluded | Upstream's other 11 workspace members, `[patch.crates-io]` for `encode_unicode` (not in bcinr-cmca's dependency graph — verified via `cargo tree`) |

## Why a snapshot instead of a submodule

The commit providing the general-N ranking entry point (`cmca_rank_cli`,
which autofde-lab's bridge calls) was not pushed to any remote branch at
vendoring time, so a submodule pin would be unresolvable for any other
clone. `vendor/gyms/*` precedent (submodule + `update = none`) exists for
large published repositories; this crate is `publish = false` and
operator-owned, so a provenance-recorded snapshot is the honest form. The
crates are copied verbatim; the only authored file is the trimmed workspace
manifest above.

## Why this crate

`bcinr-cmca` is the canonical CMCA implementation in this ecosystem
(`docs/CMCA_EXPLANATION.md` in upstream bcinr: "Chatman Multifractal
**Consequence** Allocation" is the one ecosystem-wide canonical expansion).
autofde-lab's `src/autofde_lab/cmca/cascade.py` previously shipped a local
float-softmax stand-in; it now delegates its allocation *measure* to this
crate's certified, branchless (`CC=1`), Q16.16 fixed-point
`allocator::allocate()` through `cmca_rank_cli`, and keeps the local
softmax only as the explicitly-named `reference-softmax` engine.

## Build

```bash
cargo build --release -p bcinr-cmca
# binary: vendor/bcinr/target/release/cmca_rank_cli
```

Rust toolchain: `rustc 1.97.0` verified; upstream declares `rust-version = 1.70`.

## Refresh procedure

1. In an upstream bcinr checkout, resolve the commit to pin (must contain
   `crates/bcinr-cmca/src/bin/cmca_rank_cli.rs`).
2. `git worktree add /tmp/bcinr-pin <commit>` and verify:
   `cargo build --release -p bcinr-cmca` and the CLI smoke test in
   `tests/cmca/test_bcinr_cmca_chicago.py`.
3. Replace `crates/bcinr-cmca` and `crates/bcinr-logic` here with verbatim
   copies; re-check whether upstream's `[patch.crates-io]` section has
   become required (`cargo tree -p bcinr-cmca`).
4. Update the pinned commit in this table and in
   `src/autofde_lab/cmca/bcinr_bridge.py`'s provenance constant.
