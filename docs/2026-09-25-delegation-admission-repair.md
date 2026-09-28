# Delegation/admission repair planner

Once admission debt is observed, repeated LLM reasoning is unnecessary for the
numeric scope case.

For delegated scope `D` and evidence scopes `s_i`, the unique minimum additive
repair in scope units is:

`increment_i = max(0, D - s_i)`

With declared per-unit costs `c_i`:

`minimum_cost = sum(c_i * increment_i)`

The planner emits these actions deterministically and content-addresses the plan.

It deliberately refuses to translate semantic defects into numeric scope. Missing
provenance, verifier independence, changed-requirement evidence, authority,
consequence, receipt, replay, or standing returns
`UNSUPPORTED:NON_CAPACITY_EVIDENCE_REPAIR_REQUIRED`. The planner cannot manufacture
those facts.

The plan has zero actuation authority; evidence acquisition remains external.
