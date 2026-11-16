# F1-fast-tier
Standing: PARTIAL

Files: justfile.d/48-fast.just (rewritten; `fast` + new `fast-slow`). No git (coordinator owns).

Cause of the 12.4s: `uv run --with /Users/sac/pm4pytest` rebuilds the local package every run (~3s), xdist
startup under 18 tests costs more than it saves, and 8 planner/solver tests are 1-2.5s each.
Change: cached venv ~/.cache/plan-fast-venv (created lazily, PLAN_FAST_VENV overrides), single process,
11 planner/solver/subprocess tests deselected from `fast` and run by `just fast-slow` (original xdist form).
Switch kept: PLAN_SEARCH_TIMEOUT_S default 2 (TOML-free env default, no policy value chosen).

Measured (host load average ~62 from concurrent lanes, so an upper bound):
- `just fast`, 2 runs: wall 5.50s and 5.62s (`/usr/bin/time -p`), pytest 2.93s/3.08s. Previous: 12.4s.
- Both exit 1: 18 passed, 6 failed, 11 deselected.
Failures (introduced by another lane, not this one): test_events_refuse_bad_references, test_parity_reduce_cli_vs_direct,
test_events_equal_appended_sequence, 3 in test_ocel_bridge: all `Refused: NO_PARENT[...]` from
pipeline/enterprise_pipeline/store.py:291 (R2 multi-entity edit, mtime 12:26:51). These 6 passed in my first run
(26 passed earlier, before the edit). Not touched.
Target <=5s: not demonstrably met under load (5.5s wall; pytest 3s); fast gate not green due to the R2 store edit.
`fast-slow` not run to completion.
