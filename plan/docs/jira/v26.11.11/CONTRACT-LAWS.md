# CONTRACT-LAWS

Standing: PARTIAL

Frozen interface for L1-L6 + B5 dials. Owners code against this; change only via coordinator.
Defaults = OPEN.md / open_switches.toml (MULTI-AGENT-PROMPT has no "locked defaults" block).
Law ids = LAWS.md rows (L01..L29). Refusals are `store.Refused("<CODE>[detail]")`.
Owner key: S=store.py, G=staged.py+align.py+pddl.py (+alignment_dispatch.mzn, cpsat),
C=console.py, P=spec/*.pddl, LG=ledger/core.py, D=dials.py.

## On-disk baseline (read 2026-11-11)
store.py already multi-entity: `state["entities"]` list, `entity_of`, `slice_state`, `_resolve_entity`,
derived `st["entity"]` iff exactly 1 entity; check() raises MISSING[entity] when none; ENTITY_MISMATCH
for site/territory_client. align.derive/build_dzn/cpsat_input and staged.compile_wo call
`store.slice_state` first. pddl.emit slices when >1 entity. SINGLE_ENTITY_STORE is gone from store.py.
Not yet present: everything marked NEW below.

## L6 / L25 multi-entity (S; consumers G, C)
- event `entity` {name, dba, [dbas:list[str]]} -> `entities[]` item
  `{id, dba, dbas:[dba,...extras], docs:[], templates_bound:bool}`.
- event `entity_dba` NEW {entity, dba}: appends to `entities[i].dbas`.
  Refusals: UNKNOWN[entity:x], MISSING[dba], DUPLICATE[dba] (via `_fresh`). Switch `entity_dba_model`
  (default entity_dba_on_one_entity; alt one_entity_row_per_dba_with_parent_ref: `entity` event takes
  optional `parent_entity`, no entity_dba event).
- events entity_doc/templates_bound/client/provider: optional `entity`; omitted -> sole entity, else
  MISSING[entity]. Every client/site/provider/work_order item carries `entity` (id).
- `store.entity_of(state, wo|wo_id) -> str`; `store.slice_state(state, wo) -> state` (entity-scoped
  clients/sites/providers/work_orders, `state["entity"]` bound, passthrough if no "entities" key).
- derived `state["entity"]` alias present only when len(entities)==1 (absent for 0 or >1).
- Cross-entity refs refuse ENTITY_MISMATCH[site|territory_client|provider|client].
- G consumers: never read `state["entity"]` without slicing first.

## L1 dispatch (S check; G align)
- L01 `provider_filter` {provider, dim, mode inc|exc, values}: dim not in `align.DIMS` ->
  `Refused("BAD_DIM[<dim>]")`; mode else BAD_MODE. Switch `provider_filter_validation`
  (strict default -> refuse; record_then_warn -> store event + `state["warnings"]` item
  `BAD_DIM[<dim>]`). S imports `align.DIMS` lazily or holds a copy pinned by a test (S owns check).
- L02 events NEW:
  - `invoice_left_on_site` {provider, wo} -> reduce: `providers[p].blacklisted=True` (GLOBAL ban,
    all entities/sites). Refusals UNKNOWN[provider], UNKNOWN[work_order:x].
  - `site_manager_clash` {provider, site} -> reduce: append `site` to `providers[p].filters["exc_site"]`
    (site-only exclusion; `blacklisted` unchanged). Refusals UNKNOWN[provider], UNKNOWN[site].
- L04 PDDL action `reactive-hire-handoff` (P) consumes `(reactive-hire-triggered ?wo)`; G emits the
  predicate when `eligibility()` returns trigger True (staged.eligibility `not providers` or MiniZinc
  `trigger_reactive_hire`). Switch `handoff_semantics` (default end_at_handoff: goal satisfied at handoff;
  continue_after_hire: goal continues to dispatch). plan_wo result gains `flags:["reactive_hire_handoff"]`.

## L2 territory (S + G; sales event via S)
- Client `kind`: PRIMARY subtypes vs SECONDARY from `store.subtypes("client")`; a client with
  `parent` is secondary (`contracted_through`).
- L09 `client` event: secondary (has `parent` or kind secondary) requires parent -> else
  `Refused("NO_PARENT[<client>]")`. Optional `quick_add:true` marker permitted only on PRIMARY
  (no parent); on secondary -> `Refused("QUICK_ADD_SECONDARY[<client>]")`. Reduce stores
  `c["quick_add"]=bool`.
- L06 out-of-coverage = `wo.client != site.territory_client` (site not in client territory).
  `staged.compile_wo`: PRIMARY -> still plans, `c.info`/result `flags` += `territory_flag`, emits
  `(territory-flag ?wo)`; SECONDARY -> `c.missing += "NO_PLAN[out_of_coverage]"` unless a
  `territory_waiver` exists for that wo (then plans + flag).
  Switch `secondary_out_of_coverage` (flag_and_plan default: spec says SECONDARY stays NO_PLAN
  unless waiver, so flag_and_plan applies to PRIMARY; `refuse` makes PRIMARY NO_PLAN too).
- Events NEW (S): `territory_flag` {wo, client, site} observation (OBSERVATIONS tuple; once per wo,
  DUPLICATE[territory_flag:wo]); `sales_rep_notified` {wo, client, rep?} observation, requires prior
  territory_flag else MISSING[territory_flag]; `territory_waiver` {wo, authority} (authority non-empty
  else MISSING[authority]). All three: `state["observed"]` tuples (wo, kind); waiver also
  `state["waivers"][wo]=authority`.
- Automatic notification: `staged.observe_plan` returns extra `[("territory_flag",...),
  ("sales_rep_notified",...)]`; new helper `staged.observe_flags(state, wo_id, r) -> list[(kind, payload)]`.
- PDDL (P): action/predicate `territory_flag`, `(sales-rep-notified ?wo)`, `(territory-waived ?wo)`;
  rule `wo-territory-cleared` = in-territory OR flagged-primary OR waived.

## L3 compliance (G align/staged; C UI)
- L10 expiry matrix: record-time accepts past `expiry_date` (store never refuses on date order).
  Enforced `expiry > state["clock"]` (minutes from base): coi_doc, license_doc (align `unexpired`,
  MiniZinc `coi_and_license_unexpired`, CP-SAT, PDDL `provider-doc-valid` omitted when expired);
  w9_doc/contract_doc enforced per switch `document_expiry_enforcement` (default
  veto_dispatch_when_expired: `align._doc_ok` applies expiry; record_and_warn: ignore expiry, warning
  `DOC_EXPIRED[<id>]` in compile info). Undated coi/license -> `staged._provider_gap`
  "has no expiry" (unchanged). `provider_doc` payload optional `expiry_date` ISO.
- L13 events: `required_media` NEW (S) {wo, media_type}: appends to `wo["required_media"]` (list of
  media subtype names; BAD_TYPE otherwise). `missing_media` is DERIVED: `store.missing_media(wo)->list[str]`
  = required_media types absent from `wo["visit"]["media"]` types. Soft prompt (switch
  `media_prompt_mode` soft_only): `media` upload response / console shows prompt listing missing_media;
  hard_refuse: `checkout` refuses `Refused("MISSING_MEDIA[<type,...>]")`.
  Stage-2 hard gate: `staged.compile_wo` for stage qa-review (plan_closed) adds
  `c.missing += "MISSING_MEDIA[<type>]"` while missing_media non-empty, in every mode.
  Console (C) calls `store.missing_media`; owner S.

## L14 clock (S reduce; LG; G settle)
- `state["clock"]` = minutes(PLAN_CLOCK_NOW or now, base); CLAMP NEW: `clock = max(clock,
  minutes(last_event_ts, base))` (never earlier than last event; replay with pinned PLAN_CLOCK_NOW
  older than events clamps up).
- Quote vs reality: external clock = `visit.external_min` (client_attest/quote), internal =
  `staged.internal_minutes(visit)` (checkin/checkout). Switch `clock_policy`:
  strict_internal (default: AP from internal, AR from external, as today) | quoted_safe_harbor
  (AP minutes = external when internal absent) | auto_gpm_density (waive per `clock_policy_auto` keys
  `desolate_market_provider_threshold`, `gpm_safe_harbor_bps`, `low_rate_safe_harbor_cents`).
  Function `dials.clock_policy() -> str`; `staged.settle` reads it. No PM cap by default
  (`pm_daily_minutes_cap` uncapped).

## L4 lineage / visits / money (S; G; LG; P)
- `work_order` event optional `link_kind` (change_order|recall|None) + `parent_wo`. Rules (L21):
  link_kind set requires parent_wo else MISSING[parent_wo]; parent must exist UNKNOWN[work_order:x];
  same entity/client/site else `Refused("BAD_LINK[<field>]")`; only recall may link a settled parent
  (`(parent, "ledger_settled") in observed`), change_order on settled parent -> BAD_LINK[parent_settled];
  kind change_order_wo <-> link_kind change_order, recall_wo <-> recall (BAD_LINK[kind]).
  Item fields `link_kind`, `parent_wo`. Switch `change_order_parent_wait` (independent default;
  wait_for_parent: child dispatch refuses `STAGE[parent not settled]`).
- L19 visits: `wo["visits"]` = list of visit dicts `{id, provider, geofence, media, checkin_ts,
  checkout_ts, quoted_min, external_min}`; `wo["visit"]` stays an ALIAS of `visits[-1]` (current visit).
  Events `dispatch/checkin/checkout/media/...` act on current visit. NEW event `visit_open` {wo}
  appends a fresh visit (requires current visit checked out, else STAGE[visit open]); multi-provider:
  each visit carries its own provider. Ids `<wo>_visit` (first), `<wo>_visit<N>` (N>=2); register in
  `_names`.
- Events NEW: `change_order_approved` {wo, new_nte_cents, authority} -> `wo["change_order"] =
  {approved:True, new_nte_limit_cents}`; requires link_kind change_order wo? no: any wo; RANGE[new_nte_cents>nte]
  else Refused. `nte_override_receipt` {wo, id, reason} -> `wo["override_receipt"]={id,reason}`
  (both non-empty else MISSING[...]). `dispatch_override` {wo, provider, authority, reason} permits a
  dispatch of a provider the eligibility court rejects; stored `wo["dispatch_override"]`;
  one per wo, DUPLICATE[dispatch_override:wo].
- NTE cap switch `change_order_nte_cap` (own_nte default: child cap = own nte_limit; parent_nte: child
  AR checked against parent nte_limit).
- LG: `settle(visit)` input keys unchanged plus `change_order` {approved,new_nte_limit_cents},
  `override_receipt` {id,reason}; staged.settle forwards `wo["change_order"]`/`wo["override_receipt"]`.
  `ledger_settled` payload carries `ar_cents`,`ap_cents` (ints; required when ledger JSON parseable,
  already from observe_settle) plus optional `margin_cents`. Visits aggregate: AR/AP sum over visits.
- PDDL (P): predicate `(wo-linked ?wo ?parent ?kind)`, action change-order wait guarded by dial.

## L5 roles (S events; C UI; D flag)
- Events NEW: `person` {name, [display]} -> `state["people"]=[{id, roles:[]}]` (fresh name);
  `role_grant` {person, role, [entity], [client]} role in {super_user, entity_lead, team_lead,
  coordinator, provider_ops}; super_user needs no scope; entity_lead requires entity; team_lead
  requires client (UNKNOWN[client:x]); multiple grants per person allowed (L23).
  Refusals UNKNOWN[person:x], BAD_ROLE[<role>], MISSING[entity|client].
- `store.can(state, person, action, entity=None, client=None) -> bool`: super_user -> True;
  entity_lead -> entity match (all that entity's clients); team_lead -> client match only.
- Enforcement behind env `PLAN_AUTHZ` (off by default; truthy "1"). When on, `store.append` with
  avatar not a person raises `Refused("AUTHZ[<avatar>,<kind>]")` unless can(); off -> no check.
  Avatar roster pipeline/tests/avatar_roster.toml (owner: tests lane) keys persons/roles.

## B5 dials (D)
- File `pipeline/policy_dials.toml` (generated-safe, hand-edited by humans only): one table per
  open_switches.toml switch with `value = "<option>"`; unset -> switch default. Extra table
  `[clock_policy_auto]` numeric keys as in open_switches.toml; `[pm_daily_minutes_cap]` `value`,
  `pm_daily_minutes_cap` int.
- Module `pipeline/enterprise_pipeline/dials.py`:
  `load(path=None) -> dict` (env `PLAN_POLICY_DIALS` overrides path; cached by mtime/sha);
  `get(switch: str) -> str` (validates against `options` in docs/jira/v26.11.11/open_switches.toml,
  raises `ValueError("BAD_DIAL[<switch>=<v>]")`); `param(switch, key) -> int|str`;
  `clock_policy() -> str`; `entity_dba_model()`, `secondary_out_of_coverage()`, `handoff_semantics()`,
  `document_expiry_enforcement()`, `provider_filter_validation()`, `media_prompt_mode()`,
  `change_order_parent_wait()`, `change_order_nte_cap()`, `pm_daily_minutes_cap() -> int|None`;
  `defaults() -> dict[str,str]` (the OPEN.md defaults). Callers use these, never literals.
- Switch keys read per owner: S: provider_filter_validation, entity_dba_model, media_prompt_mode,
  change_order_parent_wait; G: secondary_out_of_coverage, document_expiry_enforcement,
  handoff_semantics, change_order_nte_cap, clock_policy, clock_policy_auto; C: media_prompt_mode;
  LG: pm_daily_minutes_cap (staged forwards), clock_policy.

## Event index (NEW kinds, all S-owned in store.check/reduce; add to `_names` where they mint ids)
entity_dba, invoice_left_on_site, site_manager_clash, territory_flag, sales_rep_notified,
territory_waiver, required_media, visit_open, change_order_approved, nte_override_receipt,
dispatch_override, person, role_grant. `OBSERVATIONS` extended with territory_flag,
sales_rep_notified. Unknown kinds keep `UNKNOWN_KIND[<k>]`.

## Cross-owner dependency map
S -> G: DIMS (BAD_DIM); G -> S: slice_state/entity_of/missing_media; G -> D: switches; C -> S: can,
missing_media, new event forms; LG <- G: change_order/override_receipt forwarding; P <- G: predicates
territory-flag, sales-rep-notified, territory-waived, reactive-hire-triggered, wo-linked.

## UI deltas (console.py, lane O-console)
- Sidebar: new selectbox "Acting as" (people from store); when set, record() uses it as avatar
  (except person/role_grant). New view "G. Policy dials" (NEW[6]). Existing views/buttons unchanged.
- Admin (A): entity gains optional `dbas`; new forms entity_dba, person, role_grant; optional
  `entity` select on entity_doc/templates_bound/client/provider; client gains `quick_add`.
- Coordinator (C): work_order gains `link_kind`,`parent_wo`; new forms visit_open, required_media,
  territory_flag, sales_rep_notified, territory_waiver, change_order_approved,
  nte_override_receipt, dispatch_override. Field (D): "Media prompt (missing required media)".
- Compile view: shows "Flags:" line; calls staged.observe_flags if present.
- All new forms use the shared "Record event" submit button; unexecuted panels render NOT EXECUTED.
