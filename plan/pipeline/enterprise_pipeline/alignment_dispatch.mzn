% 10-D alignment, ranking, margin-safe dispatch (baseline from operator spec; lanes repair+validate)
enum PROVIDER; enum BRAND; enum CLIENT; enum ENTITY; enum PRIORITY; enum COORDINATOR;
enum SITE; enum STATE_JURISDICTION; enum SUB_TRADE; enum TRADE; enum WO_TYPE;
BRAND: wo_brand; CLIENT: wo_client; ENTITY: wo_entity; PRIORITY: wo_priority;
COORDINATOR: wo_coord; SITE: wo_site; STATE_JURISDICTION: wo_state; SUB_TRADE: wo_sub_trade;
TRADE: wo_trade; WO_TYPE: wo_type; int: wo_nte_cents; int: client_billable_rate_cents;
array[PROVIDER] of bool: is_blacklisted; array[PROVIDER] of bool: is_entity_aligned;
array[PROVIDER] of bool: trade_and_rate_approved; array[PROVIDER] of bool: coi_and_license_unexpired;
array[PROVIDER] of 1..20: provider_trade_rank; array[PROVIDER] of int: provider_rate_cents;
array[PROVIDER] of set of BRAND: inc_brand;   array[PROVIDER] of set of BRAND: exc_brand;
array[PROVIDER] of set of CLIENT: inc_client; array[PROVIDER] of set of CLIENT: exc_client;
array[PROVIDER] of set of ENTITY: inc_entity; array[PROVIDER] of set of ENTITY: exc_entity;
array[PROVIDER] of set of PRIORITY: inc_prio; array[PROVIDER] of set of PRIORITY: exc_prio;
array[PROVIDER] of set of COORDINATOR: inc_coord; array[PROVIDER] of set of COORDINATOR: exc_coord;
array[PROVIDER] of set of SITE: inc_site; array[PROVIDER] of set of SITE: exc_site;
array[PROVIDER] of set of STATE_JURISDICTION: inc_state; array[PROVIDER] of set of STATE_JURISDICTION: exc_state;
array[PROVIDER] of set of SUB_TRADE: inc_sub; array[PROVIDER] of set of SUB_TRADE: exc_sub;
array[PROVIDER] of set of TRADE: inc_trade; array[PROVIDER] of set of TRADE: exc_trade;
array[PROVIDER] of set of WO_TYPE: inc_wotype; array[PROVIDER] of set of WO_TYPE: exc_wotype;
% exclusion beats inclusion; empty inclusion = unconstrained
test dim_allowed(int: val, set of int: inc_set, set of int: exc_set) =
  (not (val in exc_set)) /\ (card(inc_set) == 0 \/ (val in inc_set));
array[PROVIDER] of var bool: eligible;
var bool: trigger_reactive_hire;
constraint forall(p in PROVIDER) (eligible[p] <-> (
  not is_blacklisted[p] /\ is_entity_aligned[p] /\ trade_and_rate_approved[p] /\
  coi_and_license_unexpired[p] /\ provider_rate_cents[p] <= wo_nte_cents /\
  provider_rate_cents[p] < client_billable_rate_cents /\
  dim_allowed(wo_brand, inc_brand[p], exc_brand[p]) /\ dim_allowed(wo_client, inc_client[p], exc_client[p]) /\
  dim_allowed(wo_entity, inc_entity[p], exc_entity[p]) /\ dim_allowed(wo_priority, inc_prio[p], exc_prio[p]) /\
  dim_allowed(wo_coord, inc_coord[p], exc_coord[p]) /\ dim_allowed(wo_site, inc_site[p], exc_site[p]) /\
  dim_allowed(wo_state, inc_state[p], exc_state[p]) /\ dim_allowed(wo_sub_trade, inc_sub[p], exc_sub[p]) /\
  dim_allowed(wo_trade, inc_trade[p], exc_trade[p]) /\ dim_allowed(wo_type, inc_wotype[p], exc_wotype[p])));
% selected_idx: 0 = none, else enum index (avoids opt-enum deopt pitfalls)
var 0..card(PROVIDER): selected_idx;
var opt PROVIDER: selected_provider;
constraint if exists(p in PROVIDER)(eligible[p]) then
    selected_idx >= 1 /\ eligible[to_enum(PROVIDER, selected_idx)] /\ not trigger_reactive_hire
  else selected_idx == 0 /\ trigger_reactive_hire endif;
constraint if selected_idx == 0 then absent(selected_provider)
  else occurs(selected_provider) /\ deopt(selected_provider) == to_enum(PROVIDER, selected_idx) endif;
% Deterministic total order: rank, then rate, then enum index (unique optimum).
var int: objective_score = if selected_idx == 0 then 999999999 else
    provider_trade_rank[to_enum(PROVIDER, selected_idx)] * 10000000 +
    provider_rate_cents[to_enum(PROVIDER, selected_idx)] * 100 + selected_idx endif;
solve minimize objective_score;
output [ "{\"selected\": ", if fix(selected_idx) == 0 then "null" else "\"" ++ show(to_enum(PROVIDER, fix(selected_idx))) ++ "\"" endif,
  ", \"trigger_reactive_hire\": ", show(fix(trigger_reactive_hire)), "}\n" ];
