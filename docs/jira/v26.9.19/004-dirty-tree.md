# autofde-lab: commit or clean uncommitted changes

- Standing: OPEN
- Created: 2026-09-19 (v26.9.19 gh survey wave)
- Source: working tree dirty at survey time
- Evidence: `git status --porcelain` → 7 path(s) (tracked-modified: 7, untracked: 0); sample:  M cpp/sdk/Catch2; M cpp/sdk/backward-cpp; M cpp/sdk/json;

## Work to complete
- Review the 7 tracked-modified path(s); commit them as atomic pieces on a purpose branch, or revert what is transient.
- Note: this survey's ticket files under docs/jira/v26.9.19/ are intentionally uncommitted; include or exclude them deliberately in the commit plan.

## Acceptance
- `git status --porcelain` is clean (except items deliberately deferred and recorded here).

## History
- 2026-09-19 | OPEN | survey found dirty tree | 7 paths (T7/U0) | commit/clean pending
