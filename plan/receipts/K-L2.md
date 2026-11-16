# K-L2 territory court
Standing: PARTIAL

Command: PLAN_SEARCH_TIMEOUT_S=5 PYTHONPATH=pipeline:pipeline/tests uv run ... pytest pipeline/tests/test_court_l2.py -q
Exit: nonzero. Output: `2 failed, 5 passed` (stable over 4 polls, ~2 min).

Passing: secondary out-of-coverage NO_PLAN + in-coverage twin; waiver plans with flag + empty
authority refused; L09 NO_PARENT / QUICK_ADD_SECONDARY / quick_add primary stored; flag observation
laws (MISSING[territory_flag], DUPLICATE, observed tuples).

Failing (cross-owner defect, not in owned files): test_primary_out_of_coverage_plans_flags_and_notifies
and test_twin_in_coverage_primary_has_no_flag. Planner rc=1: unified_planning
UPProblemDefinitionError "Name wo-territory-cleared already defined" because
spec/servengine_ideal_domain.pddl:53 (predicate) and :114 (durative-action) share the name
(owner P: rename action). Plan-time paths for any wo fail until fixed.

Owned edits: pipeline/tests/test_court_l2.py (new), mega_factories.py CVS row (primary out-of-coverage
now plans, settles, gate territory_flag), test_vince_continuum_mega.py (asserts territory_flag and
sales_rep_notified for that wo). test_vince_continuum_mega NOT run (needs Chromium + working planner): UNVERIFIED.
