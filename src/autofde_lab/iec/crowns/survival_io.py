"""Shared JSON/JSONL artifact I/O for autonomic-survival courts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "load_episode_file",
    "load_episode_files",
    "render_report_json",
    "write_report_json",
]


def load_episode_file(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSONL: {exc.msg}"
                ) from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: episode must be an object")
            rows.append(value)
        return rows

    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(row, dict) for row in value):
        return list(value)
    raise ValueError(f"{path}: expected episode object or array of episode objects")


def load_episode_files(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(load_episode_file(Path(path)))
    return rows


def render_report_json(report: Any, *, pretty: bool = True) -> str:
    if pretty:
        return json.dumps(
            report,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        ) + "\n"
    return json.dumps(
        report,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"


def write_report_json(path: Path, report: Any, *, pretty: bool = True) -> bytes:
    payload = render_report_json(report, pretty=pretty).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload
