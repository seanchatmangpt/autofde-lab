# O-stagedalign receipt
Standing: PARTIAL_ALIVE

Edited: pipeline/enterprise_pipeline/{staged,align,pddl}.py. alignment_dispatch.mzn unchanged
(override, expiry, desolate count handled in Python), so spec/ alignment/ copies stay identical.

Implemented: territory_state + NO_PLAN[out_of_coverage]/territory_flag flags, observe_flags,
MISSING_MEDIA at qa-review, DOC_EXPIRED warnings, expiry enforcement via dials switch,
desolate_market_count/is_desolate (dials.param), clock_policy in settle, visits-summed settle
forwarding change_order/override_receipt, margin_cents, align.apply_override (never blacklisted
or missing W-9), plan_wo flags, pddl territory predicates (emitted only when domain declares them).

Gate: test_artifact_sync.py exit 0 (see run); /tmp/o_sa_check.py ad hoc real-ledger run: settle over 2
visits sums ar 25310/ap 6080; override ignored for blacklisted. 
Pre-existing/other-owner failures: spec/servengine_ideal_domain.pddl duplicates action
wo-territory-cleared (planner UPProblemDefinitionError) -> all planner-backed tests fail;
store.py NO_PARENT breaks helpers_world.build (secondary_client without parent).
Not verified: planner-backed test_staged/test_pipeline; dials.py absent at time of run (fallback defaults).
