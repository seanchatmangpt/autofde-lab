L3_ROOT := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })

l3-test:
    cd {{L3_ROOT}}/cpsat && .venv/bin/python -m pytest -q tests

l3-diff:
    cd {{L3_ROOT}}/cpsat && .venv/bin/python diff_vs_minizinc.py
