PP_HOME := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })
PP_PY := env_var_or_default("AUTOFDE_REPO", parent_directory(PP_HOME)) + "/.venv/bin/python"
PROCUREPASS_ROOT := parent_directory(justfile_directory()) + "/procurepass"

procurepass-test:
    cd {{PROCUREPASS_ROOT}} && {{PP_PY}} -m pytest -q test_procurepass.py

procurepass-solve:
    cd {{PROCUREPASS_ROOT}} && {{PP_PY}} supplier_cpsat.py scenario_compressor.json
