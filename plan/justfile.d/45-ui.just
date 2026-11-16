UI_HOME := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })
UI_PY := env_var_or_default("AUTOFDE_REPO", parent_directory(UI_HOME)) + "/.venv/bin/python"
UI_ROOT := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })

# Succeed if playwright chromium is cached; else print install command, exit 2.
ui-install:
    #!/usr/bin/env bash
    set -u
    if ls "$HOME/Library/Caches/ms-playwright" 2>/dev/null | grep -q '^chromium'; then
        echo "[OK] playwright chromium present in ~/Library/Caches/ms-playwright"
        exit 0
    fi
    echo "[SKIP] playwright chromium missing. Run: {{UI_PY}} -m playwright install chromium"
    exit 2

# Playwright visual suite (real Chromium -> Streamlit -> store).
ui-chicago: ui-install
    #!/usr/bin/env bash
    set -eu
    f="{{UI_ROOT}}/pipeline/tests/test_visual_chicago.py"
    [ -f "$f" ] || { echo "[SKIP] missing $f"; exit 2; }
    PYTHONPATH=pipeline {{UI_PY}} -m pytest -q pipeline/tests/test_visual_chicago.py

# pm4pytest judged suite (conformance + OCEL bridge + JTBD specs).
ui-jtbd:
    #!/usr/bin/env bash
    set -eu
    {{UI_PY}} -c "import pm4pytest" || { echo "[SKIP] pm4pytest not importable"; exit 2; }
    files=""
    for t in test_jtbd_conformance test_ocel_bridge test_jtbd_specs; do
        f="pipeline/tests/$t.py"
        [ -f "{{UI_ROOT}}/$f" ] || { echo "[SKIP] missing $f"; exit 2; }
        files="$files $f"
    done
    PYTHONPATH=pipeline {{UI_PY}} -m pytest -q $files

# Judge a live demo session: just ui-live-check <sqlite> "a,b,c"
ui-live-check sqlite fsm:
    #!/usr/bin/env bash
    set -eu
    [ -f "{{sqlite}}" ] || { echo "[SKIP] sqlite session file not found: {{sqlite}}"; exit 2; }
    {{UI_PY}} -c "import pm4pytest" || { echo "[SKIP] pm4pytest not importable"; exit 2; }
    "$(dirname {{UI_PY}})/pm4pytest" check-conformance --log "{{sqlite}}" --fsm "{{fsm}}"

# 8 factory-generated JTBD plans through real Chromium (4 pass, 4 refused by real gates); PLAN_TEST_SEED replays
ui-jtbd-scenarios:
    PYTHONPATH=pipeline:pipeline/tests {{UI_PY}} -m pytest -q -p no:cacheprovider -n 4 pipeline/tests/test_jtbd_scenarios.py -W ignore

# Vince continuum mega court (real Chromium -> Streamlit -> store).
ui-vince-continuum: ui-install
    #!/usr/bin/env bash
    set -eu
    PYTHONPATH=pipeline:pipeline/tests {{UI_PY}} -m pytest -q pipeline/tests/test_vince_continuum_mega.py
