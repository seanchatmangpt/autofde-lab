# F7-diataxis-verifier-skeleton
Standing: PARTIAL_ALIVE

Base: /Users/sac/plan, no git repo (coordinator owns git). Docs dir has only _GAPS.md.

Owned: scripts/verify_diataxis.py, justfile.d/95-diataxis.just, 1 import line in Justfile.

- `just diataxis-selfcheck` rc=0: baseline passes; 3 mutations (dial rename, marker break, TODO) each
  flip FAIL; sha256 restore byte-exact; restore-detection non-vacuous; `[check5] PASS`.
- Same via `just --justfile /Users/sac/plan/Justfile diataxis-selfcheck` from /tmp: rc=0.
- `just diataxis-check` rc=1 (fail-closed: MISSING 01..04 docs, pipeline/tests/diataxis). Expected
  until later lanes land docs/tests; pytest and runnable-block paths are not exercised on real docs
  (UNVERIFIED).
- Deviation: `parent_directory(justfile_directory())` resolved to /Users/sac (just 1.56 imports
  report the root dir), so the recipe uses `justfile_directory()`. 90-ledger.just has the same
  pattern and likely the same defect (not my file, untouched).
- Dial source assumed pipeline/policy_dials.toml (absent today; dials set empty).
