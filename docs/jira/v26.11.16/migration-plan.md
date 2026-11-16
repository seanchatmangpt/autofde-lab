# autofde-lab migration plan v26.11.16

Standing: UNVERIFIED

## Identity
- Path: /Users/sac/autofde-lab
- Remote: https://github.com/seanchatmangpt/autofde-lab.git
- Branch: vince-os-solver-fixes@64a318c9 (no upstream tracking)
- Last commit: 2026-11-13; commits: 2952; size: 17,609 MB (.git alone 12 GB)
- Languages/build: Python (pyproject.toml, uv.lock, Justfile), package.json, C++ (cpp/),
  ggen.toml, k8s/, infra/
- Nested repos: none (census); git submodules present — see below

## Observed state
- Dirty: 26 — 11 M (src/autofde_lab/coprocessor/kinds_{pddl,planning,rl,search}.py,
  tests/sa2a/test_v26_9_17_concurrency_stress_chicago.py, uv.lock, optuna-journal.log,
  docs/jira/v26.9.17/benchmarks/concurrency-stress-findings.md, vendor/gyms/{enterprisebench,
  sregym} submodule pointers); 15 D (rddl_movies/test-sb3/*.gif)
- Untracked: 265 — plan/ (bulk), src/autofde_lab/law_bridge/pddl_encoding.py
- Ahead/behind: untrackable (branch has no upstream)
- Stash: 1926 (census) — extremely large stash stack
- Unpushed local branches: 45 (afde-26922-*, closure/*, crown-2/*, court-details, chore/*...)
- Build/dep dirs: .venv 76K (empty shell), vendor/ 1.5G, archive/ 263M
- Submodules: cpp/sdk/Catch2, cpp/sdk/PEGTL, cpp/sdk/backward-cpp, vendor/gyms/* (modified)

## What it is
Fork of Airbus scikit-decide, renamed autofde-lab: the planning/decision control plane of the
Chatman Ecosystem "Forward Deployment OS". Computes candidate plans, never actuates.

## Classification
ACTIVE (census agrees; commits 3 days ago, heavy branch activity).

## Migration risk
- Uncommitted source edits (coprocessor kinds, law_bridge/pddl_encoding.py, test fixes).
- 45 unpushed branches and 1926 stashes — unrecoverable if the directory is dropped.
- Current branch has no upstream at all.
- Local-only data: .env (secrets, do not print), optuna-journal.log, logs/, openevolve_output/,
  plan/ (untracked), rddl_movies/.
- 12 GB .git suggests large blobs in history; vendor/ is 1.5 GB.
Rate: HIGH

## Recommended action
COMMIT-PUSH
1. `cd /Users/sac/autofde-lab && git status --porcelain | head -40` — confirm nothing surprising.
2. `git add src/autofde_lab tests/sa2a uv.lock docs/jira plan/` (explicit paths, never -A)
3. `git commit -m "wip(v26.11.16): carry coprocessor/law_bridge edits to migration"`
4. `git push -u origin vince-os-solver-fixes`; verify with
   `git ls-remote origin | grep $(git rev-parse HEAD)`.
5. `git push origin --all` (45 branches) — DECISION: prune obviously-dead afde-26922-* first?
6. Stashes cannot be pushed: `git bundle create /Volumes/ARCHIVE/autofde-lab-full.bundle --all`
   does NOT include stashes either. DECISION: either rsync the whole dir (17.6 GB) or accept
   loss of 1926 stashes after sampling `git stash list | head` for anything named.
7. Copy .env, optuna-journal.log, logs/, openevolve_output/ by rsync separately if wanted.
8. `rm -rf .venv` before any copy; leave vendor/ (submodule checkouts re-fetch).
9. Submodules: `git submodule status` on new machine, then `git submodule update --init`.

## First commands on the new machine
`git clone --recurse-submodules https://github.com/seanchatmangpt/autofde-lab.git`
`uv sync && just check` (or `uv run pytest -x -q`) — stated, not run.

## See Also
- ../v26.9.23/
- /Users/sac/docs/jira/v26.11.16/README.md
