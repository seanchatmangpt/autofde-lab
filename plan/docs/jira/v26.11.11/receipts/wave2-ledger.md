# Wave 2 Lane Ledger

Standing: PARTIAL

Source: /Users/sac/plan/receipts/lane-*.md, Standing lines re-read from disk 2026-11-11.
Subject: /Users/sac/plan (not a git repo, SHA none). No lane-ferroplan or lane-exec receipt exists.

| lane | Standing (as written) | command and result line | KD rows |
|---|---|---|---|
| lane-cov-oracle | `Standing: PASS` | `pytest ... pipeline/tests/test_coverage_oracle.py` -> `9 passed in 426.38s (0:07:06)` | KD-COV-1, KD-COV-2, KD-COV-3, KD-COV-4 |
| lane-plankinds-core | `Standing: PARTIAL` | `pytest ... pipeline/tests/test_plankinds_core.py` (PLAN_TEST_SEED=11) -> `11 passed in 204.74s (0:03:24)`; pypict build failed, allpairspy substituted | none (REGISTERED_DIVERGENCES = {}) |
| lane-plankinds-pm | `Standing: ALIVE` | `pytest ... pipeline/tests/test_plankinds_pm_procure.py` (exit 0) -> `6 passed in 294.61s` | KD-PM-01 |
| lane-plankinds-matrix | `Standing: PARTIAL` | `pytest -q -k "not full_matrix" pipeline/tests/test_plankinds_matrix.py` -> `5 passed, 1 deselected in 1.96s`; full K1..K17 matrix UNVERIFIED | none |
| lane-plankinds-autofde-gymact | `Standing: PARTIAL` | `pytest ... pipeline/tests/test_plankinds_autofde_gymact.py` -> `4 passed in 13.14s`; K16 SKIP (no endpoint) | none |

## Consolidated KD table

| id | lane | surface | divergence | close condition |
|---|---|---|---|---|
| KD-COV-1 | cov-oracle | provider_filter | `dim` arbitrary, accepted | store validates dim in align.DIMS |
| KD-COV-2 | cov-oracle | client | secondary_client without parent accepted | store requires parent for secondary |
| KD-COV-3 | cov-oracle | provider_doc | past expiry_date accepted at record time | store refuses or flags expired docs |
| KD-COV-4 | cov-oracle | work_order/checkout | part replacement without model tag photo accepted at store; refusal only in stage-2 | store enforces tag before checkout |
| KD-PM-01 | plankinds-pm | pm/gen_problem.py to_pddl | drops provider and global blackouts; K4 INFEASIBLE, K5 PLAN on blackout-window instance | encode blackouts in PDDL (TIL) and re-run court |

## Non-KD caveats recorded in lane receipts

- autofde-gymact: pddl-unsolvable exits rc=1 via uncaught AttributeError in autofde-lab engine; RCPSP/MDP/POWL benchmarks/HDDL not wired.
- pm: K5 infeasible_capacity NO_PLAN is an aries 60s timeout, not a proof.
- matrix: K1-K9, K11-K16 were MISSING at time of that run.
