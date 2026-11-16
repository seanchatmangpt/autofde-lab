# LAWS

<!-- schema: laws-v1 -->

| id | law | quote | line | check | pddl | test | scenario | expect | status |
|---|---|---|---|---|---|---|---|---|---|
| L01 | provider_filter dim must be in align.DIMS else Refused BAD_DIM | by a brand, a client, an entity, a priority, a project coordinator, a site, a state, a sub-trade | 1019 | BAD_DIM | - | pipeline/tests/test_laws.py::test_l01_bad_dim | cvs_project | refused | LOCKED |
| L02 | invoice left on site = global provider_blacklist; site-manager clash = exc_site only | that's an immediate ban | 567 | - | provider_blacklist | pipeline/tests/test_laws.py::test_l02_ban_scopes | cvs_repair | settled | LOCKED |
| L03 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L04 | zero eligible providers -> reactive-hire-handoff action | unless no one is accepting it and we're reactively hiring someone | 1047 | - | reactive-hire-handoff | pipeline/tests/test_laws.py::test_l04_handoff | - | planned+flag | LOCKED |
| L05 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L06 | PRIMARY client out-of-coverage plans and emits territory_flag; SECONDARY stays NO_PLAN unless territory_waiver | I'm not saying reject it, but I'm saying flag it. | 273 | - | territory_flag | pipeline/tests/test_laws.py::test_l06_primary_flag_secondary_noplan | cvs_out_of_coverage | planned+flag | LOCKED |
| L07 | PRIMARY out-of-coverage emits sales_rep_notified event | so my sales rep can jump immediately and call this guy | 274 | - | sales_rep_notified | pipeline/tests/test_laws.py::test_l07_sales_rep_notified | cvs_out_of_coverage | planned+flag | LOCKED |
| L08 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L09 | secondary client requires primary parent; quick_add only on primary | Secondary means I'm working with a company that is contracted with Starbucks. | 271 | NO_PARENT | - | pipeline/tests/test_laws.py::test_l09_secondary_parent | cvs_sub_sole_provider | settled | LOCKED |
| L10 | past expiry accepted at record time; coi/license enforced expiry>clock in align/MiniZinc/CP-SAT/PDDL; w9/contract non-expiring | Licenses and certificates. | 384 | - | doc_valid | pipeline/tests/test_laws.py::test_l10_expiry_clock | - | refused | LOCKED |
| L11 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L12 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L13 | required_media/missing_media soft prompt on upload; Stage-2 hard gate | upload a new fucking picture for the model tag | 476 | - | missing_media | pipeline/tests/test_laws.py::test_l13_media_gate | nestle_untagged | refused | LOCKED |
| L14 | external clock = quote, internal clock = reality; clock_policy default strict_internal | Internal check-in and check-out is the reality of how long our service provider spent on site. | 408 | - | clock_policy | pipeline/tests/test_laws.py::test_l14_clock_policy | - | - | LOCKED |
| L15 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L16 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L17 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L18 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L19 | visits list with visit alias | Visits is the most important piece of the work order. | 1045 | - | visit | pipeline/tests/test_laws.py::test_l19_visits_list | - | - | LOCKED |
| L20 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L21 | link_kind+parent_wo same entity/client/site; recalls may link settled parents | she would link it to an original work order. | 1028 | BAD_LINK | link_kind | pipeline/tests/test_laws.py::test_l21_lineage | nestle_recall_nte | - | LOCKED |
| L22 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L23 | person + role_grant (multiple roles per person) | Team leads are people who are responsible for one or more clients within an entity. | 523 | - | role_grant | pipeline/tests/test_laws.py::test_l23_role_grant | - | - | LOCKED |
| L24 | super user all; entity lead per client; PLAN_AUTHZ off by default | Where I can see all entities, all work orders, everything. | 518 | - | - | pipeline/tests/test_laws.py::test_l24_authz | - | - | LOCKED |
| L25 | entities list + entity_dba; derived entity alias only when exactly one | every entity might have one and many DBAs | 270 | - | entity_dba | pipeline/tests/test_laws.py::test_l25_multi_entity | - | - | LOCKED |
| L26 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L27 | open threshold (brief gives no text) | UNVERIFIED | 0 | - | - | - | - | - | OPEN |
| L28 | generated rules report | here's what I think the rules should be. | 1055 | - | - | pipeline/tests/test_laws.py::test_l28_rules_report | - | - | LOCKED |
| L29 | flow Entity->Client->Vendor->Work Order->Dispatch | has clients, has service providers, and has suppliers | 127 | - | - | pipeline/tests/test_laws.py::test_l29_flow_order | - | - | LOCKED |
