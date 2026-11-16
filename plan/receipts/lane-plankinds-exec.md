# lane-plankinds-exec
Standing: PASS

Subject: K8 (plan-replay executor) and K9 (L8 mutation courts) plan-kind adapters.
Files: pipeline/tests/plankinds/k08_executor.py, k09_courts.py, pipeline/tests/test_plankinds_exec_courts.py.

## Command

    cd /Users/sac/plan && PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest \
      --with factory-boy --with faker pytest -q -p no:cacheprovider \
      pipeline/tests/test_plankinds_exec_courts.py

Output: `2 passed in 64.82s (0:01:04)`

## K8 (55 mutants + baseline, seeded via PLAN_TEST_SEED)

- unchanged -> PLAN (rc 0, ledger AR 58000 / AP 25500 / margin 32500).
- reorder (non-simultaneous pairs), drop, swap-args -> REFUSED (rc 2 precondition / type-mismatch;
  drop-8 rc 1 goal/ledger mismatch).
- Same-timestamp body swaps are skipped: they yield the identical plan, not a mutation.

## K9 (12 mutations x {aries, reach} + differential + baselines)

- Baselines aries/reach/differential -> PLAN (SOLVED).
- Every M01..M12 -> UNSOLVABLE on both aries and reach -> INFEASIBLE; differential agrees.
- aries takes ~61s per unsolvable mutant; solves run concurrently once and are memoized.
- Aries/reach divergences: none (K9 DIVERGENCES == []).

## Registered divergence rows

| id | surface | divergence | evidence | close condition |
|---|---|---|---|---|
| KD-K8-DUP | executor dup-{0,1,5,6,7,8} | duplicated action accepted (rc 0, receipts=10, ledger unchanged) because its effects are idempotent | `K8 dup-0 REFUSED PLAN rc=0 receipts=10 refused=None goal=True ledger={'AR': 58000, 'AP': 25500, 'margin': 32500}` | executor rejects re-execution of already-applied actions |

dup-2, dup-3, dup-4 are REFUSED (rc 2). Test tolerates dup-* PLAN only with the unmutated ledger.
