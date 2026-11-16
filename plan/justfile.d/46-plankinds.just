PK_HOME := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })
PK_PY := env_var_or_default("AUTOFDE_REPO", parent_directory(PK_HOME)) + "/.venv/bin/python"
PK_ROOT := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })

# Full plan-kind matrix (K1..K17): fails loudly on any missing kind or divergent case.
ui-plan-matrix:
    cd {{PK_ROOT}} && PYTHONPATH=pipeline:pipeline/tests {{PK_PY}} -m pytest -q -p no:cacheprovider -W ignore -s pipeline/tests/test_plankinds_matrix.py
