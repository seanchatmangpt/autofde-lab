PL_HOME := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })
PL_PY := env_var_or_default("AUTOFDE_REPO", parent_directory(PL_HOME)) + "/.venv/bin/python"
PIPELINE_ROOT := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) }) + "/pipeline"

# Core gate: fast kernel tests. Browser, coverage, matrix and plan-kind suites run via ui-*, ui-plan-matrix recipes.
pipeline-test:
    cd {{PIPELINE_ROOT}} && PYTHONPATH=.:tests {{PL_PY}} -m pytest -q -p no:cacheprovider tests/test_pipeline.py tests/test_staged.py tests/test_ocel_bridge.py tests/test_jtbd_factories.py

pipeline-run:
    cd {{PIPELINE_ROOT}} && python3 -m enterprise_pipeline.cli examples/canonical.json --out /tmp/pipeline_problem.pddl --plan
