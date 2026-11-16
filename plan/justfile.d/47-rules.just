RR_HOME := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })
RR_PY := env_var_or_default("AUTOFDE_REPO", parent_directory(RR_HOME)) + "/.venv/bin/python"
RR_ROOT := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })

# Regenerate docs/jira/v26.11.11/RULES-REPORT.md + rules.json from LAWS.md and code.
rules-report:
    cd {{RR_ROOT}} && {{RR_PY}} pipeline/rules_report.py

# Fail if the committed report differs from a fresh in-memory regeneration.
rules-report-check:
    cd {{RR_ROOT}} && {{RR_PY}} pipeline/rules_report.py --check
