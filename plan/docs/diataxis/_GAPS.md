# Diataxis Gap Map (Wave 1)

Standing: PARTIAL

Source: Wave 1 lanes D0-D5, static read of the tree on disk (no tests run, `just check` not re-run).
Prompt: `docs/jira/v26.11.11/DIATAXIS-MULTI-AGENT-PROMPT.md`.

## Behavior status

| B | Behavior | Status | Missing hook | Existing twin refusal | Label if not built |
|---|---|---|---|---|---|
| B1 | Completed Barrel (new vertical) | partial | `entities[]` state; entity refs on client/site/provider/WO | `MISSING[entity templates_bound]`, `MISSING[entity doc ss4_doc/w9_doc]` (`staged.py:69-73`) | `UNSUPPORTED[multi-entity: SINGLE_ENTITY_STORE]` (`store.py:155`) |
| B2 | Global ban vs site exclusion | partial | `invoice_left_on_site`, `site_manager_clash` events; `BAD_DIM`; payout ban; site-leak test | `REFUSED[not eligible]` (console), compile-level tests `test_pipeline.py:38-57` | build events as thin writers of `provider_blacklist` / `provider_filter` |
| B3 | Ranked zero-touch dispatch | mostly exists | recruiter-outreach event | `MarginGuardError`, expired COI gives reactive hire | `UNSUPPORTED[no recruiter_call event kind]` unless built; hand-off semantics stays OPEN (O05) |
| B4 | Internal Photo Vault | partial | client-visibility store event; upload-time missing-media prompt; sha-vs-bytes check | planner rc=2 on missing model tag (`test_staged.py:140`), no `MISSING[...]` from `compile_wo` | `UNSUPPORTED[media visibility + prompt]` (O09 open) |
| B5 | Two clocks, GPM, desolate market | partial, no dials | `pipeline/policy_dials.toml` + `tomllib` reads in `staged.settle` and `align.derive` | none | thresholds OPEN (O01, O02, O10); key names differ from `open_switches.toml` |
| B6 | Primary vs secondary territory | partial | `territory_flag`, `sales_rep_notified`, `territory_waiver`; PDDL triage relax; primary/secondary split | oracle model only, planner rc=2 | OPEN O11 `secondary_out_of_coverage` |
| B7 | Baton overrides, over-NTE | ledger only | `nte_override_receipt`, `change_order_approved`, `dispatch_override` kinds; wire into `staged.settle` (`staged.py:299-302`) | `NteCapError`, `MarginGuardError` (`ledger/core.py:12-16`) | OPEN O03, O04 |

## Laws landed (D5)

0 of 14 relevant laws fully implemented, 4 partial (L02, L04, L09, L10, L19, L21 partial by file evidence), rest missing.
`pipeline/tests/test_laws.py` does not exist; LAWS.md `test` ids are proposals.

## Defects found

- `provider_filter` never validates `dim` against `align.DIMS` (`store.py:234-238`); `BAD_DIM` absent.
- `ledger_settled` stores only `ledger_sha256`, no amounts.
- `staged.settle` never passes `change_order` / `override_receipt` to the ledger.
- No `tomllib` use anywhere in `pipeline/`.

## Test-capital notes

- Promote `build/run_visit/nm` from `pipeline/tests/test_staged.py` to a shared module for `pipeline/tests/diataxis/`.
- Three tests cost about 61s each (aries search timeout, `planner/plan.py:27`); expected-refusal plans run the full budget. `PLAN_SEARCH_TIMEOUT_S` lowers it.
- Result rows in `.results` need keys {plan, expected, gate, steps_done} to be merged by conftest; diataxis writer must use a distinct shape.
- Console has no override, change-order or dial forms; territory is only the `territory_client` select on the site form.

## Hardcoded thresholds that become dials (D1)

Margin floor 0 bps (`ledger/core.py:108-110`); NTE cap 100% (`ledger/core.py:98-105`);
dispatch rate floor and NTE gate (`alignment_dispatch.mzn`); rank weight 100000; wall-clock default (`store.py:313`).
