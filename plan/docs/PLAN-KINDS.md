# PLAN-KINDS

Plan-kind adapters: one module per kind under `pipeline/tests/plankinds/`, aggregated by
`pipeline/tests/plan_matrix.py` into a fail-closed matrix.

## Kinds

| id | module | what it exercises |
|---|---|---|
| K1 | k01_aries | temporal PDDL 2.1 (aries) |
| K2 | k02_minizinc | MiniZinc model |
| K3 | k03_cpsat | CP-SAT |
| K4 | k04_pm_cpsat | process-mining + CP-SAT |
| K5 | k05_pm_pddl | process-mining + PDDL |
| K6 | k06_procure | procurement plan |
| K7 | k07_ledger | ledger |
| K8 | k08_executor | executor |
| K9 | k09_courts | courts |
| K10 | k10_pm4pytest | pm4pytest FSM conformance, OCPQ rules, TemporalSLA |
| K11-K16 | other lanes | see `plankinds/` for what has landed |
| K17 | k17_stateful | Hypothesis state machine over real `store.append` |

The authoritative list is the module set; a kind with no module shows as `MISSING` and fails
`check()`.

## Statuses

`PLAN`, `NO_PLAN`, `REFUSED`, `INFEASIBLE`, `SKIP`, `UNSUPPORTED`. A case passes when its
outcome equals `Case.expect`. `SKIP` (probe failed) and `UNSUPPORTED` rows count as present and
are reported; `MISSING` and `ERROR` rows fail the gate.

## Add an adapter

1. Create `pipeline/tests/plankinds/kNN_name.py` exporting `KIND`, `TITLE`, `probe()`,
   `cases()`, `run(case)` (contract: `plankinds/__init__.py`).
2. `probe()` returns `Skip(reason, hint)` when the real tool is absent, else `None`.
3. `cases()` is deterministic and small; `run()` uses real subprocesses or solvers, no mocks,
   no sleeps.
4. Run `just ui-plan-matrix` (needs `import? 'justfile.d/46-plankinds.just'` in the root
   justfile). Results land in `pipeline/tests/.results/plankind_matrix.json`.

## See Also

- `pipeline/tests/plankinds/__init__.py`
- `pipeline/tests/plan_matrix.py`
- `justfile.d/46-plankinds.just`
- `receipts/lane-plankinds-matrix.md`
