# gate-diataxis-tests
Standing: PARTIAL
Subject: /Users/sac/plan pipeline/tests/diataxis/ (no git SHA; not a git repo). No files edited except this receipt.

## Commands
1. `PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest --with factory-boy --with faker --with hypothesis --with allpairspy --with playwright --with /Users/sac/pm4pytest pytest pipeline/tests/diataxis/ -rsfE -q`
   -> `1 failed, 11 passed, 3 skipped, 3 errors in 206.61s` (3 errors = my invocation lacked `--with streamlit`; invalid run for UI file)
2. Same plus `--with streamlit`, `test_ui_diataxis_smoke.py` only -> `3 failed in 100.87s` (rc non-zero)

## Failures
| test | owner | evidence |
|---|---|---|
| test_howto_playbooks.py::test_howto_executive_override_and_over_nte_change_order (line 561) | O-stagedalign | `align.run_minizinc` returns `pmap[provider]` True for a provider with `provider_blacklist` + `dispatch_override`; test expects banned stays ineligible and trigger True (assert `not pmap[w.p.id] and trigger is True`). Override-vs-ban precedence in eligibility (O-ledger-pddl if the rule lives in the PDDL/MiniZinc model) |
| test_ui_diataxis_smoke.py::test_every_documented_view_is_navigable | O-console | `Locator.click` timeout 30s waiting for sidebar text "A. Super Admin" (console.py:201 lists it); streamlit starts fine standalone (port opens) but sidebar item not found in the rendered page; root cause UNVERIFIED (render exception or radio not rendered) |
| test_documented_ui_labels_exist_in_live_console | O-console | same sidebar-click timeout |
| test_tutorial_journey_refusal_then_plan_then_ledger | O-console | same sidebar-click timeout |

Probe attempt to dump page body failed due to my script misusing `live_server` yield (not a string URL); not pursued.

## Typed UNSUPPORTED skips (not failures)
- test_howto_playbooks.py:495 UNSUPPORTED[media visibility + prompt: no client-visibility field in store (O09)]
- test_howto_playbooks.py:594 UNSUPPORTED[no recruiter_call event kind: recruiter outreach queue (O05)]
- test_howto_playbooks.py:607 UNSUPPORTED[handoff_semantics=continue_after_hire does not alter the compiled plan]

## Passing
11 passed (tutorial walkthrough, howto playbooks other than above). Pre-existing vs introduced: UNVERIFIED (no baseline; other lanes editing concurrently).
Counts as of this run; re-run to refresh.
