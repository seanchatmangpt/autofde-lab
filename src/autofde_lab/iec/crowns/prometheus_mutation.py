"""Reversible mutation court for SWE-Prometheus characterization gates."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .model import IECRefusal, canonical_json, content_id

MUTATION_MANIFEST_SCHEMA = "autofde-lab.swe-prometheus-mutation-manifest/1"
MUTATION_REPORT_SCHEMA = "autofde-lab.swe-prometheus-mutation-report/1"
OPERATORS = {"replace_once", "delete_once", "append_text", "write_text"}
DETECTION_MODES = {"exit_changed", "stdout_changed", "either"}
MAX_TIMEOUT_SECONDS = 3600.0

Executor = Callable[..., Any]


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _observed_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _relative_path(value: Any, field: str) -> str:
    text = str(value or "").strip()
    path = Path(text)
    if not text or path.is_absolute() or ".." in path.parts:
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            f"{field} must be a non-escaping relative path",
        )
    return text


def _argv(value: Any, field: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(part, str) or not part for part in value)
    ):
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            f"{field} must be a non-empty string list",
        )
    return list(value)


def _timeout(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            "verifier.timeout_seconds must be numeric",
        )
    value = float(value)
    if not 0.01 <= value <= MAX_TIMEOUT_SECONDS:
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            f"verifier.timeout_seconds={value} outside supported range",
        )
    return value


def parse_mutation_manifest(document: Mapping[str, Any]) -> dict[str, Any]:
    if document.get("schema") != MUTATION_MANIFEST_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            f"schema must be {MUTATION_MANIFEST_SCHEMA}",
        )
    repository = str(document.get("repository", "")).strip()
    base_commit = str(document.get("base_commit", "")).strip()
    patch_digest = str(document.get("patch_digest", "")).strip()
    if not repository or "/" not in repository or not base_commit or not patch_digest:
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            "repository, base_commit, and patch_digest are required",
        )

    verifier_raw = document.get("verifier")
    if not isinstance(verifier_raw, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            "verifier must be an object",
        )
    expected_exit = verifier_raw.get("expected_exit", 0)
    if isinstance(expected_exit, bool) or not isinstance(expected_exit, int):
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            "verifier.expected_exit must be an integer",
        )
    detection_mode = str(verifier_raw.get("detection_mode", "exit_changed"))
    if detection_mode not in DETECTION_MODES:
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            f"invalid detection_mode {detection_mode!r}",
        )
    verifier = {
        "argv": _argv(verifier_raw.get("argv"), "verifier.argv"),
        "cwd": _relative_path(verifier_raw.get("cwd", "."), "verifier.cwd")
        if str(verifier_raw.get("cwd", ".")).strip() != "."
        else ".",
        "timeout_seconds": _timeout(verifier_raw.get("timeout_seconds", 60.0)),
        "expected_exit": expected_exit,
        "detection_mode": detection_mode,
    }

    mutations_raw = document.get("mutations")
    if not isinstance(mutations_raw, list):
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            "mutations must be a list",
        )
    seen: set[str] = set()
    mutations: list[dict[str, Any]] = []
    for row in mutations_raw:
        if not isinstance(row, Mapping):
            raise IECRefusal(
                "REFUSED_INVALID_MUTATION_MANIFEST",
                "mutation must be an object",
            )
        mutation_id = str(row.get("id", "")).strip()
        if not mutation_id or mutation_id in seen:
            raise IECRefusal(
                "REFUSED_INVALID_MUTATION_MANIFEST",
                f"mutation id must be unique and non-empty: {mutation_id!r}",
            )
        seen.add(mutation_id)
        operator = str(row.get("operator", ""))
        if operator not in OPERATORS:
            raise IECRefusal(
                "REFUSED_INVALID_MUTATION_MANIFEST",
                f"mutation {mutation_id}: unsupported operator {operator!r}",
            )
        before_sha256 = str(row.get("before_sha256", "")).strip()
        if not before_sha256.startswith("sha256:"):
            raise IECRefusal(
                "REFUSED_INVALID_MUTATION_MANIFEST",
                f"mutation {mutation_id}: before_sha256 is required",
            )
        normalized: dict[str, Any] = {
            "id": mutation_id,
            "path": _relative_path(row.get("path"), f"mutation {mutation_id}.path"),
            "before_sha256": before_sha256,
            "operator": operator,
        }
        if operator in {"replace_once", "delete_once"}:
            old = row.get("old")
            if not isinstance(old, str) or old == "":
                raise IECRefusal(
                    "REFUSED_INVALID_MUTATION_MANIFEST",
                    f"mutation {mutation_id}: old must be non-empty text",
                )
            normalized["old"] = old
        if operator == "replace_once":
            new = row.get("new")
            if not isinstance(new, str):
                raise IECRefusal(
                    "REFUSED_INVALID_MUTATION_MANIFEST",
                    f"mutation {mutation_id}: new must be text",
                )
            normalized["new"] = new
        if operator in {"append_text", "write_text"}:
            text = row.get("text")
            if not isinstance(text, str):
                raise IECRefusal(
                    "REFUSED_INVALID_MUTATION_MANIFEST",
                    f"mutation {mutation_id}: text must be text",
                )
            normalized["text"] = text
        mutations.append(normalized)

    normalized_manifest: dict[str, Any] = {
        "schema": MUTATION_MANIFEST_SCHEMA,
        "repository": repository,
        "base_commit": base_commit,
        "patch_digest": patch_digest,
        "verifier": verifier,
        "mutations": mutations,
        "include_git_metadata": bool(document.get("include_git_metadata", False)),
    }
    normalized_manifest["manifest_id"] = content_id(normalized_manifest)
    return normalized_manifest


def _under(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise IECRefusal(
            "REFUSED_MUTATION_ROOT_ESCAPE",
            f"{relative!r} escapes {root}",
        )
    return candidate


def _run_verifier(
    verifier: Mapping[str, Any],
    *,
    root: Path,
    executor: Executor,
) -> dict[str, Any]:
    cwd = _under(root, str(verifier["cwd"]))
    observed_at = _observed_at()
    started = time.monotonic()
    try:
        proc = executor(
            list(verifier["argv"]),
            cwd=str(cwd),
            capture_output=True,
            timeout=float(verifier["timeout_seconds"]),
            check=False,
        )
        stdout = bytes(proc.stdout or b"")
        stderr = bytes(proc.stderr or b"")
        exit_code = int(proc.returncode)
        status = (
            "pass"
            if exit_code == int(verifier["expected_exit"])
            else "fail"
        )
    except subprocess.TimeoutExpired as exc:
        stdout = bytes(exc.stdout or b"")
        stderr = bytes(exc.stderr or b"")
        exit_code = None
        status = "timeout"
    except (FileNotFoundError, PermissionError, OSError) as exc:
        stdout = b""
        stderr = str(exc).encode("utf-8", errors="replace")
        exit_code = None
        status = "unavailable"

    stdout_digest = _sha256(stdout)
    stderr_digest = _sha256(stderr)
    result = {
        "status": status,
        "exit_code": exit_code,
        "stdout_digest": stdout_digest,
        "stderr_digest": stderr_digest,
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
        "duration_ms": (time.monotonic() - started) * 1000.0,
        "observed_at": observed_at,
    }
    result["semantic_id"] = content_id(
        "mutation-verifier",
        verifier["argv"],
        verifier["cwd"],
        verifier["expected_exit"],
        status,
        exit_code,
        stdout_digest,
        stderr_digest,
    )
    return result


def _apply_mutation(root: Path, mutation: Mapping[str, Any]) -> dict[str, Any]:
    target = _under(root, str(mutation["path"]))
    if not target.exists() or not target.is_file():
        raise IECRefusal(
            "REFUSED_MUTATION_PREIMAGE_MISMATCH",
            f"{mutation['id']}: target {mutation['path']} is not a file",
        )
    original = target.read_bytes()
    actual = _sha256(original)
    if actual != mutation["before_sha256"]:
        raise IECRefusal(
            "REFUSED_MUTATION_PREIMAGE_MISMATCH",
            f"{mutation['id']}: {actual} != {mutation['before_sha256']}",
        )

    operator = mutation["operator"]
    if operator in {"replace_once", "delete_once"}:
        try:
            text = original.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise IECRefusal(
                "REFUSED_MUTATION_ENCODING",
                f"{mutation['id']}: target is not UTF-8 text",
            ) from exc
        old = str(mutation["old"])
        count = text.count(old)
        if count != 1:
            raise IECRefusal(
                "REFUSED_MUTATION_CARDINALITY",
                f"{mutation['id']}: expected old text exactly once, observed {count}",
            )
        replacement = "" if operator == "delete_once" else str(mutation["new"])
        mutated = text.replace(old, replacement, 1).encode("utf-8")
    elif operator == "append_text":
        mutated = original + str(mutation["text"]).encode("utf-8")
    else:
        mutated = str(mutation["text"]).encode("utf-8")

    target.write_bytes(mutated)
    return {
        "path": mutation["path"],
        "before_sha256": actual,
        "after_sha256": _sha256(mutated),
        "changed": mutated != original,
    }


def _detected(
    *,
    verifier: Mapping[str, Any],
    baseline: Mapping[str, Any],
    mutated: Mapping[str, Any],
) -> bool | None:
    if mutated["status"] in {"timeout", "unavailable"}:
        return None
    mode = verifier["detection_mode"]
    exit_changed = mutated["exit_code"] != baseline["exit_code"]
    stdout_changed = mutated["stdout_digest"] != baseline["stdout_digest"]
    if mode == "exit_changed":
        return exit_changed
    if mode == "stdout_changed":
        return stdout_changed
    return exit_changed or stdout_changed


def run_mutation_court(
    document: Mapping[str, Any],
    *,
    root: Path,
    executor: Executor = subprocess.run,
) -> dict[str, Any]:
    """Apply one exact mutation per scratch copy; the treated root is read-only."""
    manifest = parse_mutation_manifest(document)
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise IECRefusal(
            "REFUSED_MUTATION_SUBJECT_UNAVAILABLE",
            f"treated root does not exist: {root}",
        )

    verifier = manifest["verifier"]
    baseline = _run_verifier(verifier, root=root, executor=executor)
    rows: list[dict[str, Any]] = []

    if baseline["status"] == "pass":
        for mutation in manifest["mutations"]:
            with tempfile.TemporaryDirectory(
                prefix="autofde-prometheus-mutation-"
            ) as directory:
                scratch = Path(directory) / "subject"
                ignore = (
                    None
                    if manifest["include_git_metadata"]
                    else shutil.ignore_patterns(".git")
                )
                shutil.copytree(
                    root,
                    scratch,
                    symlinks=True,
                    ignore=ignore,
                )
                applied = _apply_mutation(scratch, mutation)
                verifier_result = _run_verifier(
                    verifier,
                    root=scratch,
                    executor=executor,
                )
                detected = _detected(
                    verifier=verifier,
                    baseline=baseline,
                    mutated=verifier_result,
                )
                rows.append(
                    {
                        "mutation_id": mutation["id"],
                        "path": mutation["path"],
                        "operator": mutation["operator"],
                        "preimage": applied["before_sha256"],
                        "postimage": applied["after_sha256"],
                        "changed": applied["changed"],
                        "verifier": verifier_result,
                        "detected": detected,
                    }
                )

    if baseline["status"] != "pass":
        gate_strength = "none"
        standing = "INVALID_BASELINE"
    elif not manifest["mutations"]:
        gate_strength = "vacuous"
        standing = "OBSERVED"
    elif any(row["detected"] is None for row in rows):
        gate_strength = "none"
        standing = "PARTIAL"
    elif all(row["detected"] is True for row in rows):
        gate_strength = "detected"
        standing = "OBSERVED"
    else:
        gate_strength = "blind"
        standing = "OBSERVED"

    semantic_rows = [
        {
            "mutation_id": row["mutation_id"],
            "path": row["path"],
            "operator": row["operator"],
            "preimage": row["preimage"],
            "postimage": row["postimage"],
            "changed": row["changed"],
            "verifier_id": row["verifier"]["semantic_id"],
            "detected": row["detected"],
        }
        for row in rows
    ]
    report: dict[str, Any] = {
        "schema": MUTATION_REPORT_SCHEMA,
        "manifest_id": manifest["manifest_id"],
        "repository": manifest["repository"],
        "base_commit": manifest["base_commit"],
        "patch_digest": manifest["patch_digest"],
        "baseline": baseline,
        "mutations": rows,
        "gate_strength": gate_strength,
        "standing": standing,
        "summary": {
            "declared": len(manifest["mutations"]),
            "executed": len(rows),
            "detected": sum(row["detected"] is True for row in rows),
            "survived": sum(row["detected"] is False for row in rows),
            "unsupported": sum(row["detected"] is None for row in rows),
        },
        "claim_ceiling": (
            "detected requires a passing baseline and every declared mutation "
            "to change the configured verifier observation; timeout/unavailable "
            "mutation observations do not become blind or detected"
        ),
    }
    report["receipt_id"] = content_id(
        report["schema"],
        report["manifest_id"],
        report["repository"],
        report["base_commit"],
        report["patch_digest"],
        baseline["semantic_id"],
        semantic_rows,
        gate_strength,
        standing,
    )
    return report


def _read(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IECRefusal(
            "REFUSED_INVALID_MUTATION_MANIFEST",
            f"{path} must contain a JSON object",
        )
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)

    result = run_mutation_court(
        _read(args.manifest),
        root=args.root,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        canonical_json(
            {
                "receipt_id": result["receipt_id"],
                "gate_strength": result["gate_strength"],
                "summary": result["summary"],
            }
        )
    )
    if not args.gate:
        return 0
    return 0 if result["gate_strength"] == "detected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
