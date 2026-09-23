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

## History (continued)
- 2026-09-22 | RESOLVED (recorded treatment) | v26.9.22 wave L4 | 7 submodules' local modifications committed to per-submodule branches `preserve/v26922-local-mods` and worktrees restored to the recorded SHAs. cpp/sdk/* dirt was formatting churn (import reorder, workflow yaml) in vendored upstream code — preserved, not committed upstream. vendor/gyms/sregym carried a real local integration config (autofde_lab_planner agent registration in agents.yaml) — preserved byte-exact on its branch. DEFERRED as environment artifacts: (a) vendor/gyms/enterprisebench assets/images/workflow.png shows perpetually modified on this case-insensitive macOS checkout (case-collision with recorded Workflow.png; content preserved on the branch); (b) vendor/gyms/sregym's nested SREGym-applications submodule carries generated thrift (socialNetwork/gen-py) and nested-gitlink churn — vendor-runtime noise, preserved one level up only. docs/jira/v26.9.19/ itself committed this pass.
