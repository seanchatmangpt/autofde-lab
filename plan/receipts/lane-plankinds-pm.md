# Lane plankinds-pm (K4/K5/K6)
Standing: ALIVE

Subject: /Users/sac/plan (no git; no SHA available). Seed: PLAN_TEST_SEED random per run (conftest).

## Files
- pipeline/tests/plankinds/k04_pm_cpsat.py, k05_pm_pddl.py, k06_procure.py
- pipeline/tests/test_plankinds_pm_procure.py

## Command (exit 0)
cd /Users/sac/plan && PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest --with factory-boy
--with faker --with playwright pytest -q -s -p no:cacheprovider pipeline/tests/test_plankinds_pm_procure.py
(`--with playwright` is required: conftest.py imports ui_driver. ortools is fetched inside the
subprocess via `uv run --with ortools`; aries via planner/.venv from planner/run.sh.)

## Output
    K4 feasible PLAN PLAN rc=0 OPTIMAL 3 visits=9
    K4 feasible_short_blackout PLAN PLAN rc=0 OPTIMAL 3 visits=6
    K4 infeasible_capacity INFEASIBLE INFEASIBLE rc=3
    K4 infeasible_blackout_window INFEASIBLE INFEASIBLE rc=3
    K5 feasible PLAN PLAN (SOLVED_SATISFICING)
    K5 feasible_short_blackout PLAN PLAN (SOLVED_SATISFICING)
    K5 infeasible_capacity NO_PLAN NO_PLAN rc=2 (aries TIMEOUT at 60s, not a proof)
    K5 infeasible_blackout_window PLAN PLAN (SOLVED_SATISFICING)
    K6 cpsat_in_nte PLAN path=in_nte | cpsat_change_order PLAN path=change_order
    K6 cpsat_lead_time_exceeds_sla INFEASIBLE | cpsat_no_options INFEASIBLE NO_OPTIONS
    K6 cpsat_missing_fields REFUSED MISSING_FIELDS
    K6 pddl_in_nte PLAN in_nte | pddl_change_order PLAN change_order
    DIFF K4/K5: feasible agree; short_blackout agree; infeasible_capacity agree; blackout_window DIVERGE
    DIFF K6: in_nte cpsat=in_nte pddl=in_nte; change_order cpsat=change_order pddl=change_order
    6 passed in 294.61s

## Registered divergences
- KD-PM-01: pm/gen_problem.py to_pddl drops provider and global blackouts; K4 INFEASIBLE, K5 PLAN
  on the blackout-covers-first-window instance. Close condition: encode blackouts in the PDDL
  (TIL on provider-on-blackout) and re-run the court. Pinned in REGISTERED in the test.

## Notes
- K5 uses planner/run.sh directly (planner_try.py wraps plan.py with relative output paths and a
  poll loop; run.sh is the same entry).
- K5 capacity-0 NO_PLAN is aries hitting its 60s timeout, so "agree" there is unproved infeasibility.
- K6 PDDL request for the differential is built by parsing numbers from the .pddl files.
- Each probe() returns Skip with hint when uv or planner/.venv is missing.
