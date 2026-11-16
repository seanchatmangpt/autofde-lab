# gate-continuum receipt
Standing: PARTIAL

## Commands and exits
1. `just --justfile justfile.d/45-ui.just ui-vince-continuum` -> exit 1:
   `error: justfile does not contain recipe 'ui-vince-continuum'`. The recipe is absent from
   justfile.d/45-ui.just. Only ui-install, ui-chicago, ui-jtbd, ui-live-check and
   ui-jtbd-scenarios are defined. Owner: TEST (recipe missing; no owner lane has added it).
2. Fallback, the same test run directly (no streamlit dep, so it never started):
   `pytest pipeline/tests/test_vince_continuum_mega.py` without `--with streamlit` -> exit 1.
   The streamlit port poll timed out after 60s. Cause: invocation, not repo code. Discarded.
3. Full invocation (log: /tmp/continuum3.log), with `--with playwright --with streamlit
   --with plotly --with pandas --with /Users/sac/pm4pytest` and PLAN_SEARCH_TIMEOUT_S=5,
   real Chromium + Streamlit -> exit 1, 3 errors in 328s.

## Outcome table (mega world, 8 plans, from log)
| plan | expected | gate | steps | activities | completed |
|---|---|---|---|---|---|
| attest_mismatch | fail | stage2_plan_dual_clock | 33/33 | 32/35 | False |
| expired_coi | fail | stage1_plan_and_dispatch | 25/25 | 23/35 | False |
| no_part | pass | none | 34/34 | 34/34 | True |
| nte_below_charge | fail | ledger | 35/35 | 34/35 | False |
| part_with_tag | pass | none | 35/35 | 35/35 | True |
| refuse_then_flip | pass | stage2_plan_then_pass | 36/36 | 35/35 | True |
| two_providers | pass | dispatch_eligibility | 36/36 | 36/36 | True |
| withhold_tag | fail | stage2_plan | 33/33 | 32/35 | False |

## Test results
- ERROR test_vince_continuum_mega
- ERROR test_avatar_roster_coverage
- ERROR test_vince_continuum_twin_must_violate
All 3 are the same fixture error at pipeline/tests/ui_plan.py:98. After clicking "Compile and
plan" on an expected-refusal step, `page.get_by_text("NO PLAN")` (ui_envelopes.toml:52
no_plan_marker) is never visible. The page shows: Planner exit code "not called", "Goal:
closed", alert "MISSING[model_tag_photo]: part replacement requires the model-tag photo", and a
Ledger section with exit 0.

## Failure classification
| failure | owner | basis |
|---|---|---|
| Refused plan step never shows "NO PLAN"; console shows MISSING[model_tag_photo] with rc None | O-console (primary) | console.py:456 renders "not called" when rc is None; the marker is not emitted on the pre-planner gate path |
| Alternative reading of the same failure: the marker contract is stale | TEST (ui_envelopes.toml no_plan_marker) | only one side needs to change; the coordinator picks which |
| Ledger section rendered with exit 0 and AR 128070 after the refused plan | O-ledger-pddl (secondary) | UI may be reading a stale or previous ledger; not isolated |
| Missing `ui-vince-continuum` recipe | TEST | justfile.d/45-ui.just |
No O-store, O-stagedalign or O-dials failure was observed in this run.

## Pre-existing vs introduced
Not separable: there is no baseline run. The step counts (e.g. 33/33) show the UI flow itself
completes. The failing assertion is the refusal marker only.

## Not run
No retry loop and no code edits (RUN-ONLY lane). Only this receipt was written.
