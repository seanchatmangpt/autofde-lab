FAST_HOME := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })
FAST_PY := env_var_or_default("AUTOFDE_REPO", parent_directory(FAST_HOME)) + "/.venv/bin/python"
FAST_ROOT := FAST_HOME + "/pipeline"

# Browserless fast tier (<=5s target). Runs on the autofde-lab venv,
# single process (xdist startup costs more than the tests), planner-calling and subprocess-heavy tests live in `fast-slow`.
# Switch: PLAN_SEARCH_TIMEOUT_S env default 2 (read by planner/plan.py), e.g. `PLAN_SEARCH_TIMEOUT_S=3 just fast`.
fast:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{FAST_ROOT}}
    export PLAN_SEARCH_TIMEOUT_S="${PLAN_SEARCH_TIMEOUT_S:-2}" HYPOTHESIS_PROFILE=fast PYTHONPATH=.:tests
    exec "{{FAST_PY}}" -m pytest -q -p no:cacheprovider \
      tests/test_pipeline.py tests/test_staged.py tests/test_store_cli.py tests/test_ocel_bridge.py tests/test_jtbd_factories.py \
      \
      --deselect tests/test_pipeline.py::test_cpsat_matches_minizinc \
      --deselect tests/test_staged.py::test_stage_one_has_no_prebaked_future_and_plans_dispatch \
      --deselect tests/test_pipeline.py::test_real_plan_canonical \
      --deselect tests/test_pipeline.py::test_expired_coi_reactive_branch_has_no_plan \
      --deselect tests/test_staged.py::test_terminal_events_only_on_success_once \
      --deselect tests/test_staged.py::test_full_flow_refusal_flips_and_money_matches_ledger \
      --deselect tests/test_staged.py::test_part_replacement_needs_model_tag \
      --deselect tests/test_pipeline.py::test_blacklist_and_nte_and_exclusion \
      --deselect tests/test_ocel_bridge.py::test_sqlite_roundtrips_through_pm4pytest_cli \
      --deselect tests/test_pipeline.py::test_cli_end_to_end_subprocess \
      --deselect tests/test_store_cli.py::test_end_to_end_dispatch_plan_settle_over_cli

# Slow tier of the same files: planner/solver/subprocess tests, original xdist form, default planner timeout.
fast-slow:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{FAST_ROOT}}
    PYTHONPATH=.:tests exec "{{FAST_PY}}" -m pytest -q -p no:cacheprovider -n auto \
      tests/test_pipeline.py tests/test_staged.py tests/test_store_cli.py tests/test_ocel_bridge.py
