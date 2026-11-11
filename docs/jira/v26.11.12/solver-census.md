# Solver Census: tests/solvers/python

Standing: PARTIAL

Subject: working tree of /Users/sac/autofde-lab on 2026-11-11 (run while other lanes had
uncommitted edits, including `src/autofde_lab/hub/solver/ray_rllib/ray_rllib.py`).
Interpreter: `.venv/bin/python` (Python 3.13). Each row is a separate invocation:
`timeout 600 python -m pytest <target> -p no:cacheprovider -rsx -q`.

The pytest configuration suppresses the final summary line under `-q`, so counts were derived
from the per-test progress characters in each log (`.` pass, `s` skip, `F` fail, `E` error,
`x` xfail). Raw logs: `/tmp/census/*.log`, timings: `/tmp/census/summary.txt`.

## Per-file results

| Target | Pass | Skip | Fail | Error | Collection errors | Duration | Exit |
|---|---|---|---|---|---|---|---|
| autoregressive/ | 7 | 0 | 0 | 0 | 0 | 47 s | 0 |
| openevolve/ | 30 | 0 | 0 | 0 | 0 | 25 s | 0 |
| test_classic_solvers_stub_closure_l6_chicago.py | 17 | 0 | 0 | 0 | 0 | 6 s | 0 |
| test_gnn_ray_rllib_space_utils.py | 4 | 0 | 0 | 0 | 0 | 8 s | 0 |
| test_gnn_ray_rllib.py | 0 | 0 | 1 (of 2 params shown failing: test_ppo False/True) | 0 | 0 | 260 s | 1 |
| test_gnn_sb3.py | 36 | 0 | 0 | 0 | 0 | 43 s | 0 |
| test_gnn_utils.py | 16 | 0 | 0 | 0 | 0 | 8 s | 0 |
| test_misc_solvers_stub_closure_l16_chicago.py | 68 | 0 | 0 | 0 | 0 | 72 s | 0 |
| test_optuna_rayrllib.py | 1 | 0 | 0 | 0 | 0 | 27 s | 0 |
| test_pddl_determinization.py | 29 | 0 | 0 | 0 | 0 | 10 s | 0 |
| test_pddl_ff.py | 12 | 0 | 0 | 0 | 0 | 11 s | 0 |
| test_pomcp.py | 1 | 0 | 0 | 0 | 0 | 17 s | 0 |
| test_pyrddlgym_solvers.py | 3 | 0 | 0 | 0 | 0 | 20 s | 0 |
| test_python_solvers.py | 8 | 0 | 0 | 0 | 0 | 33 s | 0 |
| test_ray_rllib.py | 4 | 0 | 1 (test_ray_rllib_solver) | 0 | 0 | 89 s | 1 |
| test_rl_misc_stub_closure_l8_chicago.py | 5 | 0 | 0 | 0 | 0 | 17 s | 0 |
| test_simple_greedy_gym_procedure_chicago.py | 3 | 0 | 0 | 0 | 0 | 13 s | 0 |
| test_ssp_determinization.py | 13 | 0 | 0 | 0 | 0 | 12 s | 0 |
| test_stable_baselines_stub_closure_l7_chicago.py | 11 | 0 | 0 | 0 | 0 | 12 s | 0 |
| test_stubsites_g5_chicago.py | 10 | 0 | 0 | 0 | 0 | 9 s | 0 |
| test_up_bridge_solver.py | 3 | 0 | 0 | 0 | 0 | 14 s | 0 |

Notes on the test_gnn_ray_rllib.py row: the progress line recorded one `F` character, but the
log carries two failure sections (`test_ppo[/unmasked_graph_maze_domain_factory-False]` and
`...-True`), so the run ended with at least 2 failures and the `F` count under-reports (workers
emitted interleaved output). Treat the exact failure count for that file as 2 (from section
headers), pass count 0.

Totals across the 21 targets: 0 skips, 0 collection errors, 19 targets exit 0, 2 targets exit 1.
No target hit the 600 s timeout; the longest was test_gnn_ray_rllib.py at 260 s, and the
sum of durations is about 13 minutes, which explains the earlier 900 s whole-directory timeout.

## Failures

1. `test_gnn_ray_rllib.py::test_ppo[...-False]` and `[...-True]`: Ray raises
   `IndexError: list index out of range` at
   `.venv/lib/python3.13/site-packages/ray/rllib/env/env_runner_group.py:319` (24 occurrences)
   after `Graph2NodeRolloutWorker.__init__` dies on its creation task; call path is
   `src/autofde_lab/hub/solver/ray_rllib/ray_rllib.py:684` (`_init_algo`).
2. `test_ray_rllib.py::test_ray_rllib_solver`: `AttributeError: 'NoneType' object has no
   attribute 'enable_env_runner_and_connector_v2'` via
   `src/autofde_lab/builders/solver/restorability.py:41` into
   `src/autofde_lab/hub/solver/ray_rllib/ray_rllib.py:438` (`_load`, checkpoint restore).

## Pre-existing vs session-introduced

- Test files `tests/solvers/python/test_gnn_ray_rllib.py` and `test_ray_rllib.py` are clean
  against HEAD (`git status` shows no change under tests/solvers).
- `src/autofde_lab/hub/solver/ray_rllib/ray_rllib.py` is modified in the working tree by another
  lane (diff vs HEAD: `_OldStackDQN` replay-buffer shim, `build_class` selection at the
  `_init_algo` site, algorithm-config callback propagation). The file changed between v26.10.8
  and HEAD as well (+20/-1 lines in that file).
- Both failures originate in Ray (>= 2.5x, new env-runner/connector API) rather than in the
  census-visible test code. Whether they are pre-existing or introduced by the in-flight edit
  was not established: the HEAD copy was saved to `/tmp/census/ray_rllib_HEAD.py` but a
  HEAD-substituted run was not executed (no safe way to swap the file in the shared tree
  without touching another lane's file). Attribution: UNVERIFIED.
- The 19 passing targets are unaffected by that question except test_optuna_rayrllib.py, which
  passed against the working tree.

## Falsifiers

- Re-run the two failing files with the HEAD copy of ray_rllib.py on `PYTHONPATH`; same
  tracebacks means pre-existing, different means introduced by the in-flight edit.
