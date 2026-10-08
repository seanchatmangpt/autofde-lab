# CI operating model

The repository uses two verification rails. They answer different questions and must not be collapsed into one workflow.

## Pull request admission: `⚡ Pull request CI`

This is the stable branch-protection rail. It is intentionally small, deterministic, read-only, and change-aware.

| Gate | Runs when | Purpose |
|---|---|---|
| `Classify change` | Every pull request | Routes the diff to cache, Python, and packaging authorities. |
| `Deterministic quality` | Every pull request | Executes repository pre-commit hooks over the proposed files. |
| `Cache verifier` | Cache code, cache tests, or workflow changes | Tests cache semantics on Python 3.10, 3.12, and 3.13. |
| `Python source smoke` | Python source, tests, examples, metadata, or workflow changes | Compiles Python files and rejects merge-conflict markers. |
| `Source package smoke` | Source, native code, packaging metadata, build scripts, or workflow changes | Builds and inspects the source distribution. |
| `CI gate` | Always | Converts selected-job success or intentional skipping into one stable required status. |

Configure branch protection to require **`CI gate`**. Matrix-generated job names are implementation details and must not become branch-protection contracts.

## Full qualification and release: `🧪 Full qualification and release`

The full rail runs only for pushes to `master`, weekly scheduled qualification, manual dispatch, and version tags. It contains the expensive evidence intentionally removed from ordinary pull requests:

- deterministic repository-wide quality checks;
- cache qualification on Python 3.10, 3.12, and 3.13;
- wheel construction on Linux, macOS, and Windows for Python 3.10 and 3.12;
- one Linux integration authority with MiniZinc, optional solver dependencies, scheduling tests, Python solver tests, domain+solver pipeline (`tests/e2e`) evidence, and native tests;
- source-distribution inspection;
- documentation construction;
- tagged GitHub and PyPI publication when credentials are configured;
- documentation deployment only after the full gate succeeds.

`Full qualification gate` aggregates quality, cache, wheel, source, integration, and documentation evidence into one stable result. Release and documentation jobs remain downstream of that authority.

A high-risk branch can be escalated through **Actions → Full qualification and release → Run workflow**. Ordinary pull requests do not pay for the cross-platform release matrix.

## Standing courts (per-capability, non-gating)

In addition to the two rails, per-capability courts run path-scoped evidence where a capability lives. They answer a different question — is this capability's own admission court green — and are not branch-protection requirements:

- `aloop-court.yml` — path-filtered `pull_request` on `src/autofde_lab/aloop/**`, `src/autofde_lab/ocel/**`, `tests/aloop/**`, `schemas/aloop/**`, and the ALOOP RFC (`docs/rfcs/RFC-ALOOP-v26.9.25.md`, `docs/rfcs/aloop/**`), plus manual dispatch; runs the exact-head ALOOP-001 court with mutants and real trace replay.
- `dspy-wasm-court.yml` — `pull_request` (and `push` on its feature branch) filtered to `src/autofde_lab/wasm/dspy.py`, `tests/wasm/test_dspy_wasm.py`, and `wasm/dspy-wasm/**`.
- `tlc-court.yml` — path-filtered `pull_request`/`push` on `src/autofde_lab/iec/**`, `tests/iec/**`, `tools/tla/**`, and `scripts/fetch_tla2tools.sh`, plus manual dispatch; fetches and digest-verifies the pinned tla2tools 1.7.4, then runs the real TLC court tests with `AUTOFDE_TLC_REQUIRED=1` and the court CLI per model (BRCE reference plus its mutants) on JDK 21.
- `collective-skill-court.yml` — path-filtered `pull_request` on `src/autofde_lab/sa2a/collective_skill/**`, `tests/sa2a/collective_skill/**`, the collective-skill RFC and docs, plus manual dispatch; runs the exact-head Oracle/NOP/mutation + SA2A court.

Branch protection continues to require only **`CI gate`**.

## 80/20 ERRC

### Eliminate

- Cross-platform release builds on every pull request.
- Release and documentation-deployment side effects on pull requests.
- Duplicate cache-only and temporary formatter/export workflows.
- Commit-message switches that silently alter verification scope.
- Multiple unstable matrix contexts in branch protection.
- Automatic nightly-release mutation unrelated to change admission.

### Reduce

- Pull-request compatibility testing to the supported Python boundary for the changed cache surface.
- Cross-platform builds from twelve wheel jobs to six boundary jobs.
- Broad integration from every operating-system/version pair to one Linux authority after wheel construction.
- Packaging admission to one deterministic source-distribution proof.
- Formatting work to proposed files instead of the entire repository.
- Repeated setup through dependency, Boost, uv, and pre-commit caches.

### Raise

- Least-privilege permissions and non-persistent checkout credentials.
- Immutable commit pins for every external GitHub Action.
- Explicit job timeouts and cancellation of superseded runs.
- Path-based risk routing.
- One stable pull-request gate and one stable full-qualification gate.
- Default-branch, scheduled, manual, and tag qualification evidence.
- Release authority: artifacts publish only after all qualification dependencies succeed.

### Create

- A fast change-admission control plane.
- A separate cross-platform qualification control plane.
- An explicit escalation path for high-risk changes.
- A branch-protection contract that survives matrix and workflow refactors.
- A single Linux integration authority for expensive solver and scheduling evidence.

## Security and determinism

- Pull-request workflows use `contents: read` only.
- Checkout credentials are not persisted.
- `pull_request_target` is not used.
- External actions are pinned to immutable commit SHAs.
- Release-write permission is isolated to tagged publication and qualified documentation deployment.
- Mutable third-party apt-cache actions were replaced by explicit package installation.
- Tool versions, Boost, CMake, MiniZinc, uv, and Python boundaries are explicit.
- Documentation uses the repository lockfile rather than globally installing an unpinned VuePress release.

## Failure ownership

| Failure | Required response |
|---|---|
| Deterministic quality | Run `pre-commit run --all-files`, commit deterministic changes, and rerun. |
| Cache verifier | Correct cache semantics or the focused verifier; do not bypass the test. |
| Python source smoke | Repair syntax, conflict markers, or source-tree integrity. |
| Source package | Repair package metadata or source inclusion. |
| Wheel matrix | Repair the specific operating-system/Python build boundary. |
| Linux integration | Repair solver, scheduling, MiniZinc, native, optional-dependency, or domain+solver pipeline (`tests/e2e`) integration. |
| Documentation | Repair the locked documentation build before deployment. |
| Full qualification | Diagnose the failed authority before promotion or release. |

## Change-routing contract

Workflow changes are high risk and exercise every fast-path gate. Manual admission runs also exercise every gate. Jobs not relevant to a pull-request diff are intentionally reported as `skipped`; `CI gate` accepts only `success` or intentional `skipped` results and rejects cancellation or failure.
