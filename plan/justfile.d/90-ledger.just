LG_HOME := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })
LG_PY := env_var_or_default("AUTOFDE_REPO", parent_directory(LG_HOME)) + "/.venv/bin/python"
LEDGER_ROOT := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })

ledger-test:
    cd {{LEDGER_ROOT}} && {{LG_PY}} -m pytest ledger/tests -q

ledger-settle:
    cd {{LEDGER_ROOT}} && python3 -m ledger settle < ledger/visit_canonical.json
