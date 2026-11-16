# Enterprise State Schema

Input to `enterprise_pipeline`. See `examples/canonical.json` (reproduces
`spec/problem_enterprise_ops.pddl`).

## Top level

- `problem_name`, `domain_name`: strings.
- `clock`: int minutes; provider docs with `expiry <= clock` are expired.
- `entity`: `{id, dba, docs[{id,type}], templates_bound}` (docs are verified entity docs).
- `clients[]`: `{id, kind, contracted_through?, delivery_mode?, labor_rates{trade:cents},
  payment_terms_days?}`; `kind` is `primary_client` or `secondary_client`.
- `states[]`, `trades[]`, `sub_trades[]`, `priorities[]`: id strings (PDDL objects).
- `coordinators[]`: `{id, active_load}`.
- `sites[]`: `{id, client, state, territory_client, assets[]}`.
- `providers[]`: `{id, kind, device_attested, docs[{id,type,valid,expiry?,expiry_event?}],
  trade_approvals[{trade,sub_trade}], rate_approved[trade], rates{trade:cents},
  dispatch_rank{trade:int 1..20}, blacklisted, filters{}}`. `filters` keys
  `inc_<dim>` / `exc_<dim>` (lists) for dims brand, client, entity, prio, coord, site, state,
  sub, trade, wotype.
- `work_orders[]`: `{id, kind, wo_type, client, site, trade, sub_trade, priority, coordinator,
  requires_part_replacement?, nte_limit, onsite_sla, complete_sla, proposal, invoice, payout,
  visit{id, geofence_provider, media[{id,type,captured?}], internal_actual_duration,
  proposal_quoted_duration, external_client_duration}}`.

## Derived alignment inputs (per provider, work order)

`is_entity_aligned` = onboarded to the entity with valid `w9_doc` and `contract_doc`;
`trade_and_rate_approved` = trade/sub-trade approval and rate approval for the WO trade;
`coi_and_license_unexpired` = valid `coi_doc` and `license_doc`, each `expiry` unset or
`> clock`; `provider_rate_cents` = `rates[trade]` (missing -> 2^30, never eligible).

## Pipeline

state JSON -> per-WO MiniZinc solve (eligibility) -> PDDL problem (`eligible-for-wo` facts,
or `reactive-hire-triggered` when none) -> `planner/run.sh` (typed `[SKIP]` if absent) ->
parsed plan (`time: (action args) [duration]`).

`expiry_event: true` additionally emits a timed `(at <expiry> (not (provider-doc-valid ...)))`.
