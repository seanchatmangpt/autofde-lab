# WAVE-RECEIPT — P9 registry pin bump (b4p-p9-registry-pin-bump)

Date: 2026-09-18 · Agent: P9 (v26.9.18 autofde-lab parity wave)
Worktree: `/Users/sac/autofde-lab-wt/p9` · Branch: `chore/registry-pin-e90928d`
Base: autofde-lab master `fe81a552` · No push (law).

## Standing

**ALIVE** — pin bump landed in the worktree; every receipt below was observed
executing in this session against the exact new subject.

## SHAs

| what | value |
|---|---|
| lab base (master) | `fe81a552` |
| new registry pin | `e90928d7b0687a959831553c4eacca3d75ca6c88` (= ferroplan `origin/main`, reconciled post-wave-6 head, per b4p-f5-05 History) |
| old registry pin | `282fae46a7cf4f71ab473e33b5f3fdb4d73433c9` (2026-08-05, `#38`) |
| drift | old pin IS an ancestor of e90928d; **431 commits behind** (`git rev-list --count 282fae46..e90928d` = 431, run in `~/ferroplan`) |

## Pin diff

`src/autofde_lab/wasm/_registry.py:172`:
`revision="282fae46a7cf4f71ab473e33b5f3fdb4d73433c9"` →
`revision="e90928d7b0687a959831553c4eacca3d75ca6c88"` (only the ferroplan
component; the other 15 components untouched).

Binding mechanics recorded (why a pin bump forces an artifact rebuild):

- `src/autofde_lab/wasm/_model.py:154` — `Invocation.envelope()` sends
  `source_revision: component.revision` in every request.
- `src/autofde_lab/wasm/_model.py:202-205` — `InvocationResult.from_bytes`
  REFUSES any guest receipt whose `subject.source_revision != component.revision`
  ("receipt source revision does not match the registry pin"). The served stub
  embeds the pin at build time (`build.py` `_C_TEMPLATE` `__REVISION__`), so
  pin and artifact must move atomically.
- `src/autofde_lab/wasm/_runtime.py` `ArtifactImage.from_descriptor` +
  `_artifacts.py` `PackagedArtifact.bytes()` — digest+size gates between the
  registry, the packaged zips, and the rebuild recipe (`build.py rebuild_verify`).

## Artifact

Served artifact is the federation stub `ferroplan.wasm` packaged in
`src/autofde_lab/wasm/artifacts/chatman-ecosystem-wasm.zip` — NOT the cargo
`ferroplan-wasm` module (the ticket's cargo-build assumption does not apply to
the lab's serving path; beam4pm's cargo wasm rebuild at e90928d was already
witnessed in b4p-f5-05 and is not this repo's artifact).

- new `ferroplan.wasm`: sha256 `c94569b5227e2674ab2b2db45f798627404b27431880a7c1b73a30b5db91aa16`, size **5601**
- rebuild recipe (discovered): `autofde_lab.wasm.build.rebuild_verify` —
  `_C_TEMPLATE` rendered per component (name, revision, capability), compiled
  `clang --target=wasm32 -O2 -nostdlib -Wl,--no-entry -Wl,--export-memory
  -Wl,--export=chatman_alloc -Wl,--export=chatman_dealloc
  -Wl,--export=chatman_invoke -Wl,--initial-memory=196608
  -Wl,--max-memory=196608 -Wl,--strip-all`
- toolchain: `/opt/homebrew/opt/llvm@17/bin/clang` (Homebrew clang 17.0.6 — the
  only wasm32-capable clang on this machine; Apple clang 17 has no wasm32
  target, llvm@21 ships no wasm lld). Determinism proven: two independent
  rebuilds byte-identical for all 16 components.
- zips repacked deterministically (fixed 1980 epoch ZipInfo, deflate):
  base = 14 entries (incl. `wasm4pm-compat.wasm`; interop owns
  `mfw.wasm`+`wasm4pm.wasm`), interop = 2 entries; 16/16 entries verified
  zip-bytes == rebuild-bytes == registered digest.

## FINDINGS (pre-existing, observed 2026-09-18 — repaired here, not papered over)

1. **Committed packaging corrupt since creation.**
   `chatman-ecosystem-wasm.zip` was committed truncated at `3672d3fc`
   (2026-08-05, "feat: package and execute all Chatman WASM adapters"):
   10320 bytes, 4 local file headers, **0 central-directory records, 0 EOCD** —
   `zipfile` refuses it, so EVERY base-archive read raised
   `ValueError: packaged Chatman Wasm archive is invalid`. Observed directly:
   `pytest tests/test_chatman_wasm.py` FAILED at source on the untouched pin
   (exit 1, `test_registry_is_complete_exact_and_artifact_bound`). All 7
   machine copies checked (main checkout, 5 worktrees, vendored copies) are the
   same blob. Redemption evidence: 3 of the 4 truncated entries decompress and
   byte-match their registered digests (cargo-cicd `910efc26…`, old ferroplan
   `24bd821f…`, fgn `82ab0cc5…`) — the digest registry was genuine; only the
   container was corrupt.
2. **Legacy digests unreproducible locally.** llvm@17 rebuilds the old-pin
   ferroplan stub at 5600 bytes vs the registered 6131 (code section 5004 vs
   5524) — the original builder (LLVM version unknown, no producers section) is
   not on this machine. 11 of 14 base entries were therefore unrecoverable
   bytes. Repair: full 16-stub rebuild with llvm@17, digests re-registered from
   `rebuild-report.json`, making the exact-SHA contract locally enforceable
   again (`rebuild_verify` now gates ALIVE end-to-end).
3. **Process hazard witnessed (and hit).** The shared venv's editable install
   (`ScikitBuildRedirectingFinder`) intercepts `import autofde_lab` BEFORE
   `PYTHONPATH`, silently redirecting to `~/autofde-lab/src`. A first rebuild
   harvest embedded the OLD pin (ferroplan `28762fc5…`/5600) — caught because
   it byte-matched the old-revision falsification build, redone with the
   worktree `conftest.py` redirect. pytest is guarded by conftest; any
   standalone runner must replicate the redirect.

## Receipts re-earned (command + true exit, this session)

| gate | command | result |
|---|---|---|
| pin-bound test file | `PYTHONPATH=src ~/autofde-lab/.venv/bin/python3 -m pytest tests/test_chatman_wasm.py -q` | **12 passed, exit 0** |
| rebuild recipe ALIVE | `rebuild_verify(compiler=llvm@17)` (worktree-redirected) | **ALIVE 16/16, exit 0** |
| pin-bound invocation | `ChatmanEcosystem().ferroplan.describe()/admit(...)` via NodeBackend | **ALIVE/ALIVE; receipt.subject = {component: ferroplan, source_revision: e90928d7b0687a959831553c4eacca3d75ca6c88}** |
| negative falsifier | forged guest receipt carrying OLD pin → `InvocationResult.from_bytes` | **refused: "receipt source revision does not match the registry pin"** |
| adapter probe (pin-adjacent) | `pytest tests/adapters/test_adapters.py -q` | 9 passed (probe only; no pin binding) |

Baseline (pre-change) observation: the same test file FAILED at source with the
truncated zip on the old pin — the receipts could not be earned at all before
the packaging repair; they are earned green on the new pin.

## Old-code-name sweep

`grep -rn "FP_HDDL_TIMEOUT|FP_HDDL_WORKER_PANIC|FP_HDDL_ROOT_MISMATCH|FP_TIMEOUT|FP_WORKER_PANICKED" src/ tests/` → **0 hits**
(also 0 for `FP_HDDL*` across the whole worktree outside `.git`). The lab has
no ferroplan error-code mapping — its federation stub surface is
operation-level (self_test/describe/admit) and never surfaces FP_* codes. No
mappings to update, no assertions to re-derive, no flips filed.

## Files changed (this branch)

- `src/autofde_lab/wasm/_registry.py` — pin 282fae46… → e90928d… (1 line)
- `src/autofde_lab/wasm/_artifacts.py` — 16 digest+size pairs re-registered from rebuild output (32 lines)
- `src/autofde_lab/wasm/artifacts/chatman-ecosystem-wasm.zip` — rebuilt, valid, 14 entries (26,732 B)
- `src/autofde_lab/wasm/artifacts/chatman-interop-wasm.zip` — rebuilt, valid, 2 entries
- `WAVE-RECEIPT.md` — this receipt

## 比 (honest)

Delivered code lines: 33 (1 + 32). All VALUES are machine-produced
(`rebuild-report.json` from the observed rebuild) and transcribed by hand — no
marketplace pack or generator renders `_registry.py`/`_artifacts.py`. Strict
DfCM ratio: **0% pack-rendered / 100% hand-carried**, with zero
judgment-authored content (every digest/size/pin is receipt-echoed; one
transcription error — a 63-char digest — was caught by the registry's own
validation and corrected against the receipt file). The packaging repair was
scripted, not hand-crafted. Filing this honestly per the fail-closed 比 law.

## Falsifiers attempted

1. Old-pin receipt acceptance → falsified (typed refusal, observed).
2. Legacy-digest reproducibility with local toolchains → falsified (drove re-registration).
3. First rebuild's provenance → falsified (finder redirect had embedded old pin; redone redirected).
4. Zip validity across machine copies → base zip invalid everywhere (no intact original exists).
5. wasm4pm-compat packaging omission → falsified by tests ("packaged artifact is missing"), repack corrected.

## Remaining

- Branch `chore/registry-pin-e90928d` NOT merged and NOT pushed (law) — merge is the tree owner's cut.
- Ticket History row appended in beam4pm `docs/jira/v26.9.18/b4p-p9-registry-pin-bump.md`.
- Lab-side FP_* parity: N/A (no mappings exist; nothing to flip).
- `llvm@17` provenance for the re-registered digests should eventually be
  recorded upstream in `docs/chatman-ecosystem-wasm.md` (out of P9 scope; noted
  for the lab owners).
