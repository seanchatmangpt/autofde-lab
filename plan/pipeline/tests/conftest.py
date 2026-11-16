"""Fixtures for the JTBD conformance gate: a real streamlit server and the real UI driver.

pm4pytest registers via its pytest11 entry point (installed into the autofde-lab venv, editable);
no `-p` flag is needed."""
import json
import os
from pathlib import Path

import pytest


@pytest.fixture()
def live_streamlit(tmp_path):
    """Real `streamlit run console.py` on a fresh store; yields (url, store_file, cfg, tmp)."""
    import ui_driver  # lazy: browserless runs must not need playwright
    with ui_driver.live_server(tmp_path) as srv:
        yield srv["url"], srv["store"], ui_driver.CFG, srv["tmp"]


@pytest.fixture()
def drive_ui_journey():
    """The real Playwright driver: clicks the DOM only, never emits trace events."""
    import ui_driver  # lazy: browserless runs must not need playwright
    return ui_driver.drive_ui_journey


def pytest_configure(config):
    """One seed per run, shared by xdist workers through the environment (collection must agree)."""
    os.environ.setdefault("PLAN_TEST_SEED", str(int.from_bytes(os.urandom(4), "big")))


def pytest_report_header(config):
    return f"PLAN_TEST_SEED={os.environ['PLAN_TEST_SEED']} (rerun with it to replay the same plans)"


ROW_KEYS = {"plan", "expected", "gate", "steps_done", "steps_planned",
            "observed_activities", "intended_activities", "completed"}


def pytest_sessionfinish(session, exitstatus):
    """Controller only: merge per-plan result files into scenario_results.json and print the table."""
    if hasattr(session.config, "workerinput"):
        return
    results = Path(os.environ.get("PLAN_RESULTS_DIR") or Path(__file__).resolve().parent / ".results")
    rows = []
    skipped = []
    for p in sorted(results.glob("*.json")) if results.exists() else []:
        if p.name == "scenario_results.json":
            continue
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError) as exc:
            skipped.append(f"{p.name}: unreadable ({type(exc).__name__})")
            continue
        if isinstance(d, dict) and ROW_KEYS <= set(d):
            rows.append(d)
        else:
            skipped.append(f"{p.name}: foreign JSON shape")
    for note in skipped:
        print(f"\n[SKIP] scenario_results merge: {note}")
    if not rows:
        return
    (results / "scenario_results.json").write_text(json.dumps(rows, indent=1))
    print("\nplan                expected  gate                       steps  activities  completed")
    for r in rows:
        print(f"{r['plan']:<19} {r['expected']:<9} {r['gate']:<26} "
              f"{r['steps_done']}/{r['steps_planned']:<4} {r['observed_activities']}/{r['intended_activities']:<8} "
              f"{r['completed']}")
