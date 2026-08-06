# CI operating model

The repository uses two verification rails. They answer different questions and must not be collapsed into one workflow.

## Pull request admission: `⚡ Pull request CI`

This is the stable branch-protection rail. It is intentionally small, deterministic, read-only, and change-aware.

| Gate | Runs when | Purpose |
|---|---|---|
| `Deterministic quality` | Every pull request | Executes repository pre-commit hooks over the proposed diff. |
| `Cache verifier` | Cache code, cache tests, or workflow changes | Tests cache semantics on Python 3.10, 3.12, and 3.13. |
| `Python source smoke` | Python source, tests, examples, metadata, or workflow changes | Compiles Python files and rejects merge-conflict markers. |
| `Source package smoke` | Source, native code, packaging metadata, build scripts, or workflow changes | Builds and inspects the source distribution. |
| `CI gate` | Always | Converts selected-job success or intentional skipping into one stable required status. |

Configure branch protection to require **`CI gate`**. Matrix-generated job names are implementation details and must not become branch-protection contracts.

## Full qualification and release: `🧪 Full validation and release`

The full workflow preserves the repository's cross-platform wheel builds, broad solver and scheduling integrations, MiniZinc setup, documentation construction, nightly assets, tagged releases, and package publication machinery. It runs only for:

- pushes to `master`;
- the weekly scheduled qualification;
- manual dispatch;
- version tags.

`Full qualification gate` aggregates repository quality, Linux, macOS, Windows, and documentation evidence into one stable result. Existing publication jobs retain their direct test dependencies; the aggregate gate does not weaken or replace them.

A high-risk branch can be escalated before merge through **Actions → Full validation and release → Run workflow**. Ordinary pull requests do not pay for the release matrix.

## 80/20 ERRC

### Eliminate

- Cross-platform release builds on every pull request.
- Release, nightly, notebook-tagging, and documentation-deployment jobs on pull requests.
- Duplicate cache-only and temporary formatter/export workflows.
- Commit-message switches that silently alter verification scope.
- Multiple unstable matrix contexts in branch protection.

### Reduce

- Pull-request compatibility testing to the supported Python boundary for the changed cache surface.
- Packaging admission to one deterministic source-distribution proof.
- Formatting work to proposed files instead of the entire repository.
- Repeated setup through dependency and pre-commit caches.

### Raise

- Least-privilege permissions and non-persistent checkout credentials.
- Immutable commit pins for every external GitHub Action.
- Explicit job timeouts and cancellation of superseded runs.
- Path-based risk routing.
- One stable pull-request gate and one stable full-qualification gate.
- Default-branch, scheduled, manual, and tag qualification evidence.

### Create

- A fast change-admission control plane.
- A separate release-qualification control plane.
- An explicit escalation path for high-risk changes.
- A branch-protection contract that survives matrix and workflow refactors.

## Security and determinism

- Pull-request workflows use `contents: read` only.
- Checkout credentials are not persisted.
- `pull_request_target` is not used.
- External actions are pinned to immutable commit SHAs.
- Release-write permission is isolated to jobs that update releases, tags, notebooks, or documentation.
- The mutable third-party apt cache action was replaced by explicit package installation.
- Documentation uses the repository lockfile rather than globally installing an unpinned VuePress release.
- Full release jobs remain the authority for Windows, macOS, Linux wheel compatibility and optional solver integrations.

## Failure ownership

| Failure | Required response |
|---|---|
| Deterministic quality | Run `pre-commit run --all-files`, commit deterministic changes, and rerun. |
| Cache verifier | Correct cache semantics or the focused verifier; do not bypass the test. |
| Python source smoke | Repair syntax, conflict markers, or source-tree integrity. |
| Source package | Repair package metadata or source inclusion. |
| Full qualification | Diagnose the specific platform, solver, documentation, or release job before promotion. |

## Change-routing contract

Workflow changes are high risk and exercise every fast-path gate. Manual admission runs also exercise every gate. Jobs not relevant to a pull-request diff are intentionally reported as `skipped`; `CI gate` accepts only `success` or intentional `skipped` results and rejects cancellation or failure.
