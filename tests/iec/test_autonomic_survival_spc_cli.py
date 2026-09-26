"""CLI tests for survival SPC release-series monitoring."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "autonomic_survival_spc.py"


def _module():
    spec = importlib.util.spec_from_file_location("autonomic_survival_spc", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def episode(batch: str, index: int, *, failed: bool) -> dict:
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": f"git:repo@{batch}",
        "workload_id": "workload",
        "policy_id": "formal",
        "episode_id": f"{batch}-{index}",
        "horizon": 3,
        "events": [
            {"step": 1, "phase": "OBSERVE"},
            {
                "step": 2 if failed else 3,
                "phase": "DO",
                "authorized": not failed,
                "admitted": True,
                "receipt_id": f"receipt:{batch}:{index}",
                "replay_verified": True,
            },
        ],
    }


def write_batch(path: Path, batch: str, failures: int, total: int = 4) -> None:
    rows = [
        episode(batch, index, failed=index < failures)
        for index in range(total)
    ]
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_spc_cli_reads_ordered_batches_and_writes_signal(tmp_path: Path) -> None:
    module = _module()
    paths = []
    for label, failures in (("a", 1), ("b", 2), ("c", 2), ("d", 2)):
        path = tmp_path / f"{label}.jsonl"
        write_batch(path, label, failures)
        paths.append((label, path))
    output = tmp_path / "spc.json"

    argv = [
        "--series-id",
        "formal-series",
        "--metric",
        "failure_probability_observed",
        "--target",
        "0.25",
        "--allowance",
        "0.05",
        "--decision-interval",
        "0.4",
        "--output",
        str(output),
    ]
    for label, path in paths:
        argv.extend(["--batch", f"{label}={path}"])

    assert module.main(argv) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["first_positive_alarm"] == "d"
    assert [point["batch"] for point in report["points"]] == ["a", "b", "c", "d"]


def test_spc_cli_returns_refusal_for_bad_batch_syntax() -> None:
    module = _module()

    try:
        module.main(["--batch", "not-a-pair"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("argparse should reject malformed --batch")


def test_spc_cli_returns_refusal_for_missing_episode_file(tmp_path: Path) -> None:
    module = _module()

    exit_code = module.main(
        [
            "--batch",
            f"a={tmp_path / 'missing.jsonl'}",
            "--series-id",
            "series",
            "--metric",
            "rmst_steps",
            "--target",
            "3",
            "--allowance",
            "0.1",
            "--decision-interval",
            "1",
        ]
    )

    assert exit_code == 2
