# K-L5-repair-r1
Standing: PARTIAL_ALIVE

Edits by this lane: none (test_court_l5.py already passes 11/11; no test defect found in owned file).
helpers_world.py NO_PARENT defect was already fixed on disk by another owner (secondary_client now carries parent).
Command: pytest test_court_l5 test_staged test_court_l1 test_ocel_bridge test_court_l4 (pipeline env, no-cache)
Exit/output: 59 passed, 1 failed (test_staged.py::test_part_replacement_needs_model_tag, r0 rc None, no missing).
Re-run of that test alone x6: 6/6 passed (1.6-2.4s each). Failure seen once during the 84s concurrent run
(other lanes loading the machine; planner rc None) -- flaky under load, not reproduced; UNVERIFIED root cause.
Not covered: ui-jtbd/ui-chicago/ui-vince recipes and ledger-pddl/console cases (other owners' files).
