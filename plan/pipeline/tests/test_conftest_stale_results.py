"""conftest sessionfinish must survive stale/foreign JSON in PLAN_RESULTS_DIR (real nested pytest run)."""
import json
import os
import subprocess
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
PLAN = TESTS.parents[1]


def _run(results: Path, tmp_path: Path):
    t = tmp_path / "test_tiny.py"
    t.write_text("def test_ok():\n    assert True\n")
    env = {**os.environ, "PLAN_RESULTS_DIR": str(results), "PYTHONPATH": f"{PLAN/'pipeline'}:{TESTS}"}
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(t), "-q", "-p", "no:cacheprovider", "-c", "/dev/null",
         "--rootdir", str(tmp_path), "--confcutdir", str(TESTS), "-p", "conftest"],
        cwd=TESTS, env=env, capture_output=True, text=True, timeout=120)


def test_stale_foreign_results_do_not_crash_sessionfinish(tmp_path):
    results = tmp_path / "res"
    results.mkdir()
    (results / "stale_list.json").write_text(json.dumps([1, 2, 3]))
    (results / "stale_partial.json").write_text(json.dumps({"plan": "p1", "expected": "pass", "gate": "g", "steps_done": 1}))
    (results / "stale_garbage.json").write_text("{not json")
    (results / "good.json").write_text(json.dumps(
        {"plan": "p", "expected": "pass", "gate": "g", "steps_done": 1, "steps_planned": 1,
         "observed_activities": 1, "intended_activities": 1, "completed": True}))
    r = _run(results, tmp_path)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "KeyError" not in out and "INTERNALERROR" not in out, out
    assert "[SKIP] scenario_results merge: stale_garbage.json" in out, out
    merged = json.loads((results / "scenario_results.json").read_text())
    assert [row["plan"] for row in merged] == ["p"]
