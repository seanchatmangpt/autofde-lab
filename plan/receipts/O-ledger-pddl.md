# O-ledger-pddl
Standing: PARTIAL_ALIVE

Commands (cwd /Users/sac/plan):
- `just ontology` -> triples 675, conforms True; `cmp` of regenerated ttl vs ontology/servengine.ttl: identical.
- `just ledger-test` -> 18 passed (rc 0). `just executor-test` -> Ran 6 tests, OK.
- `just gate-root` -> 44 receipts, 0 failing (rc 0).
- pipeline test_pipeline.py (real aries planner), test_court_l2/l3/b5/artifact_sync -> pass.

Changes: spec/servengine_ideal_domain.pddl (copied byte-identical to executor/fixtures/): types link_kind +
constants lk_change_order/lk_recall; predicates wo-linked, territory-flag, sales-rep-notified, territory-waived,
wo-territory-cleared, reactive-hire-handed-off, visit-follow-up, provider-pay-duration-set, quoted-pay-elected;
function provider-pay-duration; triage precondition = in-territory OR flag OR waiver; actions
derive-wo-territory-cleared, reactive-hire-handoff (closes WO = end_at_handoff), hold/release-linked-wo,
open-follow-up-visit, record-provider-pay-duration, settle-provider-ap-payout-quoted (needs quoted-pay-elected,
unset by default). ledger/core.py: `visits` list aggregates AR/AP; tests added.

Finding: reading an uninitialised function (provider-pay-duration) in an action makes aries return
INTERNAL_ERROR; quoted payout therefore multiplies proposal-quoted-duration.

Pre-existing/other-owner failures (not introduced here): test_court_l1 (BAD_DIM, NO_PARENT[...] from store.py),
test_court_l4 dispatch_override (store). Full pipeline suite exceeds a single 10-min call; not run to completion.
