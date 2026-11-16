# CP-SAT Dispatch JSON Schema

Input (stdin of `python -m servengine_cpsat`):

```json
{
  "work_order": {"brand": "b1", "client": "c1", "entity": "e1", "priority": "p1",
    "coordinator": "k1", "site": "s1", "state": "TX", "sub_trade": "st1", "trade": "hvac",
    "wo_type": "reactive", "nte_cents": 50000, "client_billable_rate_cents": 9000},
  "providers": [{"id": "P1", "blacklisted": false, "entity_aligned": true,
    "trade_and_rate_approved": true, "coi_and_license_unexpired": true,
    "trade_rank": 3, "rate_cents": 7500,
    "inc": {"brand": ["b1"]}, "exc": {"site": ["s9"]}}]
}
```

- `inc`/`exc` keys: brand, client, entity, priority, coordinator, site, state, sub_trade,
  trade, wo_type (all optional; each a list of strings). Dimension allowed iff value not in
  exc AND (inc empty OR value in inc).
- Vetoes (all must hold): not blacklisted, entity_aligned, trade_and_rate_approved,
  coi_and_license_unexpired, rate_cents <= nte_cents, rate_cents < client_billable_rate_cents
  (positive margin; NOT present in baseline .mzn, which declares the rate but never uses it).
- `trade_rank` in 1..20; `rate_cents` non-negative int; provider ids unique.
- Objective: minimize rank*100000 + rate_cents; ties broken by input order.

Output:

```json
{"selected_provider": "P1" | null, "trigger_reactive_hire": false,
 "eligible": ["P1"], "objective_score": 307500, "vetoes": {"P2": ["blacklist"]}}
```

No eligible provider: `selected_provider` null, `trigger_reactive_hire` true,
`objective_score` 99999999. Invalid input: `{"error": ...}` on stdout, exit 2.
