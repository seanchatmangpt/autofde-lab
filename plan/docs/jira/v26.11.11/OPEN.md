# OPEN

Standing: UNVERIFIED

<!-- schema: open-v1 -->

| id | question | option_a | option_b | default | owner | switch | transcript_line |
|---|---|---|---|---|---|---|---|
| O01 | AP pay when the internal clock is ignored: which clock_policy | strict_internal | quoted_safe_harbor | strict_internal | Tony | clock_policy | 408 |
| O02 | AP pay when the internal clock is ignored, auto policy: when does GPM density waive enforcement | auto_gpm_density | strict_internal | strict_internal | Vince | clock_policy_auto | 450 |
| O03 | Change order waits for its parent work order? | wait_for_parent | independent | independent | Tony | change_order_parent_wait | 1028 |
| O04 | Whose NTE caps a change order | own_nte | parent_nte | own_nte | Tony | change_order_nte_cap | 1032 |
| O05 | Hand-off after no eligible provider | end_at_handoff | continue_after_hire | end_at_handoff | Tony | handoff_semantics | 1047 |
| O06 | Many DBAs per entity: model | entity_dba_on_one_entity | one_entity_row_per_dba_with_parent_ref | entity_dba_on_one_entity | Tony | entity_dba_model | 270 |
| O07 | W9/contract expiry enforcement | veto_dispatch_when_expired | record_and_warn | veto_dispatch_when_expired | Tony | document_expiry_enforcement | 380 |
| O08 | provider_filter value-universe validation | strict | record_then_warn | strict | Tony | provider_filter_validation | 1019 |
| O09 | Media prompt at upload | soft_only | hard_refuse | soft_only | Tony | media_prompt_mode | 475 |
| O10 | PM daily minutes cap | capped | uncapped | uncapped | Vince | pm_daily_minutes_cap | UNVERIFIED |
| O11 | Secondary client work order outside coverage | flag_and_plan | refuse | flag_and_plan | Vince | secondary_out_of_coverage | 275 |
