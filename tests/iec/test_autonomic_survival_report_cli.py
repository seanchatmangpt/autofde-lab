"""Artifact CLI tests for autonomic survival reports."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "autonomic_survival_report.py"


def _module():
    spec = importlib.util.spec_from_file_location("autonomic_survival_report", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def episode(episode_id: str, policy_id: str, failed: bool = False) -> dict:
    do = {
        "step": 2,
        "phase": "DO",
        "authorized": not failed,
        "admitted": True,
        "receipt_id": f"receipt:{episode_id}",
        "replay_verified": True,
        "terminal_ready": True,
    }
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": "subject",
        "workload_id": "workload",
        "policy_id": policy_id,
        "episode_id": episode_id,
        "horizon": 2,
        "events": [{"step": 1, "phase": "OBSERVE"}, do],
    }


def test_load_accepts_object_array_and_jsonl(tmp_path: Path) -> None:
    module = _module()
    one = tmp_path / "one.json"
    one.write_text(json.dumps(episode("one", "formal")), encoding="utf-8")
    array = tmp_path / "array.json"
    array.write_text(
        json.dumps([episode("a", "formal"), episode("b", "formal")]),
        encoding="utf-8",
    )
    jsonl = tmp_path / "rows.jsonl"
    jsonl.write_text(
        "\n".join(
            json.dumps(row)
            for row in (episode("x", "formal"), episode("y", "formal"))
        )
        + "\n",
        encoding="utf-8",
    )

    assert len(module._load(one)) == 1
    assert len(module._load(array)) == 2
    assert len(module._load(jsonl)) == 2


def test_build_compare_groups_declared_policy_ids() -> None:
    module = _module()
    report = module.build_report(
        "compare",
        [
            episode("f", "formal"),
            episode("l", "llm", failed=True),
        ],
    )

    assert {row["policy_id"] for row in report["policies"]} == {"formal", "llm"}
    assert report["observed_pareto_frontier"] == ["formal"]


def test_main_writes_deterministic_report_artifact(tmp_path: Path) -> None:
    module = _module()
    source = tmp_path / "episodes.jsonl"
    source.write_text(
        json.dumps(episode("f1", "formal")) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "reports" / "survival.json"

    exit_code = module.main(
        [
            "--mode",
            "recurrent",
            "--input",
            str(source),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema"] == "autofde-lab.recurrent-survival/1"
    assert report["policy_id"] == "formal"


def test_main_returns_refusal_exit_for_empty_input(tmp_path: Path) -> None:
    module = _module()
    source = tmp_path / "empty.jsonl"
    source.write_text("", encoding="utf-8")

    assert module.main(["--input", str(source)]) == 2
