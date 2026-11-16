# K-L6 multi-entity court receipt
Standing: PARTIAL

Owned: pipeline/tests/test_court_l6.py (6 tests, own vertical factory, primary_client per L09).
Command: PYTHONPATH=pipeline:pipeline/tests PLAN_SEARCH_TIMEOUT_S=5 uv run ... pytest pipeline/tests/test_court_l6.py -q
Result: 5 passed, 1 failed (real-planner dispatch test).
Passing: second-vertical settle; first vertical compile byte-identical after second entity; entity-omitted MISSING[entity];
templates_bound/doc withheld refuses; ENTITY_MISMATCH[territory_client].
Blocked by: spec/servengine_ideal_domain.pddl:53 (predicate) and :114 (durative-action) both named
wo-territory-cleared; UP reader raises "Name wo-territory-cleared already defined" so plan_wo rc!=0
for any WO (pre-existing, owner P). Also helpers_world.build uses secondary_client without parent
(NO_PARENT, L09) - owner of helpers_world.
