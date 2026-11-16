# L1 Repairs

Standing: PASS

Subject: spec/servengine_ideal_domain.pddl, spec/problem_enterprise_ops.pddl.
Toolchain: unified-planning + up-aries (Python 3.12 venv in planner/.venv, macOS arm64).
pytamer (up-tamer) has no arm64 macOS wheel; aries is the installed temporal planner;
validation is unified-planning `up_time_triggered_validator` on the ORIGINAL problem.

## Domain/problem edits

1. `wo-complete-sla` was declared and initialised but never used. Added condition
   `(at start (<= (external-client-duration ?v) (wo-complete-sla ?wo)))` to
   `emit-and-deliver-client-invoice`. Strengthens, never weakens; no precondition removed.

## Findings left unchanged (parse and validate as-is)

2. Types: no duplicate or undeclared parents found under the UP parser; the hierarchy is kept.
3. `doc_ent_w9` and `doc_prov_w9` are both `w9_doc`, so `certify-provider-alignment`
   has an unreachable grounding with the entity W9 as the provider W9
   (`provider-doc-valid` holds only for `doc_prov_w9`). Semantics preserved; planner picks the lawful one.
4. Goal inv_9001/pay_9001: bound by the `?inv`/`?pay` action parameters; only one object of
   each type exists, so the goal grounds with no change.
5. `:duration (= ?duration (internal-actual-duration ?v))` (fluent duration): static fluent,
   resolved to 3 on grounding; kept in the domain.

## Planner-side adaptations (plan.py, not spec edits)

6. aries rejects Real types: the search copy of the problem maps `number` fluents to bounded
   Int (0..10,000,000). Validation uses the original Real-typed problem.
7. aries rejects `up:times`: the UP grounder folds static-fluent products
   (invoice-amount = 4*14500 = 58000, due = 0+45*1440 = 64800) before search.
8. aries stalls (timeout) with the TIL at t=525600. For SEARCH only, TILs later than
   HORIZON=10000 are deferred; the plan is then validated against the full original problem
   including the TIL, and plan.py asserts plan end < HORIZON. TIL semantics are preserved in validation.
9. Timed actions are separated by epsilon 0.1 by aries (start 1.1 after the 1-unit activate).
