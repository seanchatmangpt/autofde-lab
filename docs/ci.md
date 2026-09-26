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
| `GALL-005 typed composition court` | Python source or workflow changes (Python 3.12) | Runs the exact-head typed composition court (sa2a composition courts, rdflib/pyshacl). |
| `Execute Crown kernel` / `Fortune-5 runtime court` | Python source or workflow changes (Python 3.12) | Crown-kernel execution and Fortune-5 runtime verification. |
| `Source package smoke` | Source, native code, packaging metadata, build scripts, or workflow changes | Builds and inspects the source distribution. |
| `CI gate` | Always | Converts selected-job success or intentional skipping into one stable required status. |
| `gall-005-exact-head` | Pull requests to `master` touching GALL composition surfaces (manual dispatch) | Exact-head typed GALL-001..004 SA2A composition crown. |
| `gall-005-hosted-chain` | Pull requests on `gall/checkpoint-005-composition-crown` touching the exact-manifest/chain paths (manual dispatch) | Hosted exact-chain crown: builds the exact manifest and re-verifies the composition on the checked-out subject. |
| `gall-009-feedback` | Pull requests on `gall/v26.9.18-final-specs` touching autonomics feedback paths (manual dispatch) | GALL-009 feedback-admission court at the exact head. |
| `gall-015-030-process-spine` | Pushes to `gall/dfcm-integrate-015-030-process-spine` and path-matched pull requests (manual dispatch) | GALL-015..030 process-spine court at the exact head. |
| `sa2a-graph-learning-crown` | Pull requests to `master` touching graph-learning surfaces (manual dispatch) | Exact-head GraphSAGE candidate/admission crown. |
| `fortune5-sa2a-production-crown` | Pull requests to `master` touching the production simulation (manual dispatch) | Exact-head Fortune-5 production simulation court. |
| `phase-h-trigger` | Scheduled only — daily cron at 03:17 UTC (manual dispatch; no pull-request trigger) | Fires the unattended Phase H tick. |
| `wd-fa-court` | Pull requests touching `wd_fa` source, tests, or web app (manual dispatch) | Exact-head OCEL → POWL → TPOT candidate court. |
| `wd-fa-ggen-contract` | Pull requests touching the wd-fa ggen contract packs (manual dispatch) | Exact-head marketplace manufacture of the `wd-fa-zod-contract` projections. |
| `wd-fa-fullstack-factory` | Pull requests touching the wd-fa pack or source (manual dispatch) | Semantic full-stack manufacture from the pinned producer SHA. |
| `tlc-court` | Pull requests and pushes to `master` touching `src/autofde_lab/iec/**`, `tests/iec/**`, `tools/tla/**`, or the fetch script (manual dispatch), JDK 21 | Runs `python -m autofde_lab.iec tlc-court` over the IEC TLA+ projections with the real toolchain: SANY, then TLC per property, on sha256-pinned tla2tools 1.7.4 (`JAR_DIGEST_MISMATCH` refusal), issuing per-property verdict receipts and projecting counterexamples to OCEL 2.0; four BRCE mutants run as anti-vacuity witnesses and `AUTOFDE_TLC_REQUIRED=1` turns a skip into failure. |
| `collective-skill-court` | Pull requests to `master` touching `src/autofde_lab/sa2a/collective_skill/**` (manual dispatch) | Exact-head Oracle/NOP/mutation + SA2A court over the fail-closed collective-skill compiler: pinned marketplace subject `seanchatmangpt/ggen-marketplace` + `collective-skill-court-pack`, authority ceiling `OBSERVE\|SELECT\|CONSTRUCT`, refusing on receipt-not-bound-to-CourtSpec, refused-court-cannot-become-candidate, and marketplace revision drift. |
| `planning-formalism-court` | Pull requests to `master`, pushes to `master` (manual dispatch) | Exact-head court split into FOND, HDDL, and FRONTIER legs with per-artifact named uploads (`planning-fond-<sha>`, `planning-hddl-<sha>`, `planning-frontier-<sha>`); the push trigger runs the producers on the merge subject. |
| `powl-runner` | Pull requests to `master` and pushes to `master` touching `src/autofde_lab/powl/**`, `tests/powl/**`, or `benchmarks/powl_runner.py` (manual dispatch) | POWL runner qualification (Python 3.12/3.13) with the named artifact `powl-runner-py<version>-<sha>`; the push trigger runs the producer on the merge subject. |
| `aloop-court` | Pull requests to `master` touching `src/autofde_lab/aloop/**`, `src/autofde_lab/ocel/**`, `tests/aloop/**`, `schemas/aloop/**`, `docs/rfcs/RFC-ALOOP-v26.9.25.md`, `docs/rfcs/aloop/**`, or the workflow itself (manual dispatch) | Exact-head ALOOP-001 autonomous closed-loop court over OCEL 2.0 (`3cb94f60`): asserts checkout identity against the head SHA, runs the court with its committed mutants, and replays the committed chatman root-crown receipt; court exits `0` qualified, `3` not qualified (typed), `2` refused, with the expected typed exit 3 captured explicitly under the runner's `bash -e` (`001b5b82`). |

Configure branch protection to require **`CI gate`**. Matrix-generated job names are implementation details and must not become branch-protection contracts. The rows below `CI gate` are standalone domain and crown workflows under `.github/workflows/`, cataloged here with their triggers; they are not `CI gate` jobs.

## Full qualification and release: `🧪 Full qualification and release`

The full rail runs only for pushes to `master`, weekly scheduled qualification, manual dispatch, and version tags. It contains the expensive evidence intentionally removed from ordinary pull requests:

- deterministic repository-wide quality checks;
- cache qualification on Python 3.12 and 3.13 (the Python floor was raised to 3.12 on 2026-09-18 — `requires-python >= 3.12`, `d5ac60ff`; the PR rail below still runs cache verification on 3.10/3.12/3.13);
- wheel construction on Linux, macOS, and Windows for Python 3.12 only;
- one Linux integration authority with MiniZinc, optional solver dependencies, scheduling tests, Python solver tests, domain+solver pipeline (`tests/e2e`) evidence, and native tests;
- source-distribution inspection;
- documentation construction;
- tagged GitHub and PyPI publication when credentials are configured;
- documentation deployment only after the full gate succeeds.

`Full qualification gate` aggregates quality, cache, wheel, source, integration, and documentation evidence into one stable result. Release and documentation jobs remain downstream of that authority.

A high-risk branch can be escalated through **Actions → Full qualification and release → Run workflow**. Ordinary pull requests do not pay for the cross-platform release matrix.

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
- Cross-platform builds from twelve wheel jobs to six boundary jobs (now three: Linux, macOS, and Windows on Python 3.12 only, after the 3.12 floor bump).
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
