# UI-TESTING

Standing UI test discipline for the plan pipeline. Recipes: `justfile.d/45-ui.just`.

## Stack

Real Chromium click -> Streamlit -> store -> MiniZinc -> aries -> ledger.
Every layer is real; the test drives the top and asserts on the bottom.

## Recipes

- `just ui-install` - checks `~/Library/Caches/ms-playwright` for chromium; exit 2 with the
  install command if absent. Never downloads silently.
- `just ui-chicago` - Playwright visual suite (`test_visual_chicago.py`).
- `just ui-jtbd` - pm4pytest judged suite (conformance, OCEL bridge, JTBD specs).
- `just ui-live-check <sqlite> "<fsm>"` - judge a live session file.

A missing prerequisite prints `[SKIP] <reason>` and exits 2; it never passes silently.

## Chicago-school rules

- No mocks; real collaborators (Streamlit server, store, solvers).
- State oracles: assert on store/ledger state, not on call counts.
- No fixed sleeps; wait on observables with deadlines.
- Seeds are printed on failure so any run replays.

## pm4pytest judging

Sessions are projected to OCEL and judged by `ConformanceSpec` (alignment fitness against an
FSM). Gotchas:

1. Token replay is blind to unmodeled activities. Use `allowed_transitions` so an
   unexpected activity is a violation.
2. A UI click is not an admitted event. Project events from the store, not from clicks.

## Watching and tracing

- Headed: `HEADED=1 just ui-chicago`.
- Traces: `playwright show-trace <trace.zip>` (via `uv run --with playwright`).

## Judging a live demo session

The demo writes an OCEL sqlite session file. Run:

`just ui-live-check /path/to/session.sqlite "step1,step2,step3"`

Exit 0 with TAP `ok` means fitness met `--min-fitness` (default 1.0).

## See Also

- `docs/JTBD.md`
- `justfile.d/40-pipeline.just`
- `scripts/check.py`

## Factory-generated JTBD plans

`pipeline/tests/jtbd_factories.py` (factory_boy + Faker) builds 8 plans from one `ScenarioFactory`
with a Trait per plan. `ui_plan.run_plan` executes each through real Chromium;
`test_jtbd_scenarios.py` replays the store into pm4pytest. Four plans conform (fitness 1.0); four
are refused by a real gate and marked `expected_conformance_violation`:

| plan | gate | verdict |
|---|---|---|
| part_with_tag, no_part, refuse_then_flip, two_providers | none / recoverable | pass |
| withhold_tag | stage-2 plan NO PLAN | fail |
| attest_mismatch | stage-2 plan, dual clock | fail |
| expired_coi | stage-1 plan + dispatch refused | fail |
| nte_below_charge | ledger exit 2 | fail |

Run: `just ui-jtbd-scenarios`. The seed prints in the pytest header; set `PLAN_TEST_SEED` to
replay. Per-plan results land in `pipeline/tests/.results/` (`scenario_results.json` merged).
