# autofde-lab: triage 12 local-only branches

- Standing: OPEN
- Created: 2026-09-19 (v26.9.19 gh survey wave)
- Source: local branches with commits not on `origin/master` and no upstream
- Evidence: `git rev-list --count origin/master..<branch>` > 0 for each: chore/registry-pin-e90928d:1 crown-2/autofde-compose:3 crown-2/orthogonal-ws:15 feat/gall-swf-v26.9.18:1 worktree-agent-a1fd74601d7042bba:1 worktree-agent-aa33ed4cebf48ceaf:1 worktree-agent-addc1ce9bba43aa87:1 worktree-agent-af85dbacf84d13ea6:1 worktree-wf_078da058-98e-7:1 worktree-wf_5ae4d4d8-070-6:1 worktree-wf_7d6e68be-690-4:2 worktree-wf_ee0eb33e-c9c-1:1

## Work to complete
- Triage each branch: push (`git push -u origin <branch>`) or delete after confirming the commits are obsolete/recoverable. Batch the work; record decisions in History.

## Acceptance
- Every listed branch is pushed or deleted; no local-only branch with unique commits remains.

## History
- 2026-09-19 | OPEN | survey found 12 local-only branches | full list above | triage pending
