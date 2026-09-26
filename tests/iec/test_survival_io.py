"""Shared survival artifact I/O tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autofde_lab.iec.crowns.survival_io import (
    load_episode_file,
    load_episode_files,
    render_report_json,
    write_report_json,
)


def test_loader_accepts_object_array_and_jsonl(tmp_path: Path) -> None:
    one = tmp_path / "one.json"
    one.write_text('{"episode_id":"a"}', encoding="utf-8")
    array = tmp_path / "array.json"
    array.write_text('[{"episode_id":"b"},{"episode_id":"c"}]', encoding="utf-8")
    jsonl = tmp_path / "rows.jsonl"
    jsonl.write_text(
        '{"episode_id":"d"}\n{"episode_id":"e"}\n',
        encoding="utf-8",
    )

    assert [row["episode_id"] for row in load_episode_file(one)] == ["a"]
    assert [row["episode_id"] for row in load_episode_file(array)] == ["b", "c"]
    assert [row["episode_id"] for row in load_episode_file(jsonl)] == ["d", "e"]
    assert len(load_episode_files((one, array, jsonl))) == 5


def test_loader_refuses_scalar_or_invalid_jsonl(tmp_path: Path) -> None:
    scalar = tmp_path / "scalar.json"
    scalar.write_text('"not-an-episode"', encoding="utf-8")
    with pytest.raises(ValueError, match="expected episode object"):
        load_episode_file(scalar)

    broken = tmp_path / "broken.jsonl"
    broken.write_text('{"episode_id":"ok"}\n{broken}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="broken.jsonl:2"):
        load_episode_file(broken)


def test_report_rendering_is_key_sorted_and_write_returns_exact_bytes(tmp_path: Path) -> None:
    report = {"z": 1, "a": {"b": 2}}
    pretty = render_report_json(report)
    compact = render_report_json(report, pretty=False)

    assert pretty.endswith("\n")
    assert compact == '{"a":{"b":2},"z":1}\n'

    path = tmp_path / "nested" / "report.json"
    payload = write_report_json(path, report, pretty=False)

    assert payload == compact.encode()
    assert path.read_bytes() == payload
    assert json.loads(path.read_text()) == report
