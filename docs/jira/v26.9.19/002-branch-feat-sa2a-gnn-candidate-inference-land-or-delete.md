# autofde-lab: land or delete remote branch `feat/sa2a-gnn-candidate-inference`

- Standing: OPEN
- Created: 2026-09-19 (v26.9.19 gh survey wave)
- Source: remote branch `feat/sa2a-gnn-candidate-inference` — not merged into `master`, no open PR
- Evidence: `git branch -r --no-merged origin/master` lists it; absent from `gh pr list` heads

## Work to complete
- Decide: open a PR (`gh pr create -R seanchatmangpt/autofde-lab --head feat/sa2a-gnn-candidate-inference`) or delete (`git push origin --delete feat/sa2a-gnn-candidate-inference`).
- If superseded, delete; otherwise land through review.

## Acceptance
- After `git fetch --prune`, `git branch -r --no-merged origin/master` no longer lists `feat/sa2a-gnn-candidate-inference`.

## History
- 2026-09-19 | OPEN | survey found PR-less unmerged branch | feat/sa2a-gnn-candidate-inference | decision pending

## History (continued)
- 2026-09-22 | DONE (delete path) | v26.9.22 wave L4 | the 5 unique subjects of feat/sa2a-gnn-candidate-inference (1ef76f7f) were confirmed rebased into #159 feat/sa2a-gnn-candidate-inference-v2 (e2909db1); #159 merged to master (a0a79f01); the superseded v1 remote branch deleted (`git push origin --delete feat/sa2a-gnn-candidate-inference`, ls-remote count 0)
