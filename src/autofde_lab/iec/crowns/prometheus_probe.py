"""Executable paired-probe protocol for SWE-Prometheus/VGG evidence.

The probe layer manufactures observations only. It never assigns governance
scores and never promotes a repository to ALIVE. A scorer may bind 1..5 values
to successful paired observations; the VGG court remains the admission authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .model import IECRefusal, Verdict, canonical_json, content_id
from .prometheus import CASE_SCHEMA, DIMENSIONS, evaluate_case

MANIFEST_SCHEMA = "autofde-lab.swe-prometheus-probe-manifest/1"
RUN_SCHEMA = "autofde-lab.swe-prometheus-probe-run/1"
PAIR_SCHEMA = "autofde-lab.swe-prometheus-probe-pair/1"
SCORECARD_SCHEMA = "autofde-lab.swe-prometheus-scorecard/1"

ROLES = {"governance", "behavior", "mutation", "clean_environment", "replay"}
SCOPES = {"base", "treated", "both"}
COMPARISONS = {"exit_only", "stdout_digest"}
MAX_TIMEOUT_SECONDS = 3600.0

Executor = Callable[..., Any]


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _bounded_number(value: Any, field: str, *, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"{field} must be numeric",
        )
    value = float(value)
    if not lo <= value <= hi:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"{field}={value} outside [{lo}, {hi}]",
        )
    return value


def _probe(row: Any, seen: set[str]) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            "probe must be an object",
        )
    probe_id = str(row.get("id", "")).strip()
    if not probe_id or probe_id in seen:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"probe id must be unique and non-empty: {probe_id!r}",
        )
    seen.add(probe_id)

    role = str(row.get("role", ""))
    scope = str(row.get("scope", "both"))
    if role not in ROLES:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"probe {probe_id}: invalid role {role!r}",
        )
    if scope not in SCOPES:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"probe {probe_id}: invalid scope {scope!r}",
        )

    if role == "governance":
        dimension = str(row.get("dimension", ""))
        if dimension not in DIMENSIONS:
            raise IECRefusal(
                "REFUSED_INVALID_PROBE_MANIFEST",
                f"probe {probe_id}: governance dimension {dimension!r} is invalid",
            )
    else:
        dimension = None

    if role == "mutation" and scope == "base":
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"probe {probe_id}: mutation cannot be base-only",
        )

    argv = row.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(part, str) or not part for part in argv)
    ):
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"probe {probe_id}: argv must be a non-empty string list",
        )

    cwd = str(row.get("cwd", ".")).strip() or "."
    cwd_path = Path(cwd)
    if cwd_path.is_absolute() or ".." in cwd_path.parts:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"probe {probe_id}: cwd must stay under the subject root",
        )

    timeout = _bounded_number(
        row.get("timeout_seconds", 60.0),
        f"probe {probe_id}.timeout_seconds",
        lo=0.01,
        hi=MAX_TIMEOUT_SECONDS,
    )
    expected_exit = row.get("expected_exit", 0)
    if isinstance(expected_exit, bool) or not isinstance(expected_exit, int):
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"probe {probe_id}.expected_exit must be an integer",
        )

    comparison = str(row.get("comparison", "exit_only"))
    if comparison not in COMPARISONS:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"probe {probe_id}: invalid comparison {comparison!r}",
        )

    return {
        "id": probe_id,
        "role": role,
        "scope": scope,
        "dimension": dimension,
        "argv": list(argv),
        "cwd": cwd,
        "timeout_seconds": timeout,
        "expected_exit": expected_exit,
        "comparison": comparison,
    }


def parse_manifest(document: Mapping[str, Any]) -> dict[str, Any]:
    if document.get("schema") != MANIFEST_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            f"schema must be {MANIFEST_SCHEMA}",
        )
    repository = str(document.get("repository", "")).strip()
    base_commit = str(document.get("base_commit", "")).strip()
    patch_digest = str(document.get("patch_digest", "")).strip()
    if not repository or "/" not in repository or not base_commit or not patch_digest:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            "repository, base_commit, and patch_digest are required",
        )

    rows = document.get("probes")
    if not isinstance(rows, list) or not rows:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            "probes must be a non-empty list",
        )
    seen: set[str] = set()
    probes = tuple(_probe(row, seen) for row in rows)

    behavior = [p for p in probes if p["role"] == "behavior"]
    if len(behavior) > 1:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_MANIFEST",
            "at most one behavior probe is allowed per fixed subject",
        )
    for role in ("clean_environment", "replay"):
        selected = [p for p in probes if p["role"] == role]
        if len(selected) > 1:
            raise IECRefusal(
                "REFUSED_INVALID_PROBE_MANIFEST",
                f"at most one {role} probe is allowed",
            )

    normalized: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "repository": repository,
        "base_commit": base_commit,
        "patch_digest": patch_digest,
        "probes": list(probes),
    }
    normalized["manifest_id"] = content_id(normalized)
    return normalized


def _rooted(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise IECRefusal(
            "REFUSED_PROBE_ROOT_ESCAPE",
            f"{relative!r} escapes {root}",
        )
    return candidate


def _observed_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _execute_one(
    probe: Mapping[str, Any],
    *,
    root: Path,
    executor: Executor,
    env: Mapping[str, str] | None,
) -> dict[str, Any]:
    cwd = _rooted(root, str(probe["cwd"]))
    if not cwd.exists() or not cwd.is_dir():
        detail = f"missing cwd: {cwd}"
        return {
            "probe_id": probe["id"],
            "role": probe["role"],
            "dimension": probe["dimension"],
            "status": "unavailable",
            "exit_code": None,
            "stdout_digest": _sha256(b""),
            "stderr_digest": _sha256(detail.encode()),
            "stdout_bytes": 0,
            "stderr_bytes": len(detail.encode()),
            "duration_ms": 0.0,
            "observed_at": _observed_at(),
            "semantic_id": content_id(
                probe["id"],
                probe["argv"],
                str(probe["cwd"]),
                "unavailable",
                "missing-cwd",
            ),
        }

    started = time.monotonic()
    observed_at = _observed_at()
    try:
        proc = executor(
            list(probe["argv"]),
            cwd=str(cwd),
            env=dict(env) if env is not None else None,
            capture_output=True,
            timeout=float(probe["timeout_seconds"]),
            check=False,
        )
        stdout = bytes(proc.stdout or b"")
        stderr = bytes(proc.stderr or b"")
        exit_code = int(proc.returncode)
        status = "pass" if exit_code == int(probe["expected_exit"]) else "fail"
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

    duration_ms = (time.monotonic() - started) * 1000.0
    stdout_digest = _sha256(stdout)
    stderr_digest = _sha256(stderr)
    semantic_id = content_id(
        probe["id"],
        probe["role"],
        probe["dimension"],
        probe["argv"],
        probe["cwd"],
        probe["expected_exit"],
        status,
        exit_code,
        stdout_digest,
        stderr_digest,
    )
    return {
        "probe_id": probe["id"],
        "role": probe["role"],
        "dimension": probe["dimension"],
        "status": status,
        "exit_code": exit_code,
        "stdout_digest": stdout_digest,
        "stderr_digest": stderr_digest,
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
        "duration_ms": duration_ms,
        "observed_at": observed_at,
        "semantic_id": semantic_id,
    }


def execute_manifest(
    document: Mapping[str, Any],
    *,
    root: Path,
    side: str,
    executor: Executor = subprocess.run,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute one side of an exact paired benchmark without shell evaluation."""
    if side not in {"base", "treated"}:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_RUN",
            f"side must be base|treated, got {side!r}",
        )

    manifest = parse_manifest(document)
    selected = [
        probe
        for probe in manifest["probes"]
        if probe["scope"] in {"both", side}
    ]
    receipts = [
        _execute_one(probe, root=root, executor=executor, env=env)
        for probe in selected
    ]
    report: dict[str, Any] = {
        "schema": RUN_SCHEMA,
        "manifest_id": manifest["manifest_id"],
        "repository": manifest["repository"],
        "base_commit": manifest["base_commit"],
        "patch_digest": manifest["patch_digest"],
        "side": side,
        "root_identity": _sha256(str(root.resolve()).encode()),
        "receipts": receipts,
    }
    report["run_id"] = content_id(
        report["schema"],
        report["manifest_id"],
        report["repository"],
        report["base_commit"],
        report["patch_digest"],
        report["side"],
        [receipt["semantic_id"] for receipt in receipts],
    )
    return report


def _index(run: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = run.get("receipts")
    if not isinstance(rows, list):
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_RUN",
            "receipts must be a list",
        )
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not row.get("probe_id"):
            raise IECRefusal(
                "REFUSED_INVALID_PROBE_RUN",
                "invalid receipt row",
            )
        key = str(row["probe_id"])
        if key in result:
            raise IECRefusal(
                "REFUSED_INVALID_PROBE_RUN",
                f"duplicate receipt {key}",
            )
        result[key] = row
    return result


def _verdict(status: str) -> str:
    if status == "pass":
        return Verdict.PASS.value
    if status in {"fail", "timeout"}:
        return Verdict.COUNTEREXAMPLE.value
    return Verdict.UNSUPPORTED.value


def pair_runs(
    manifest_document: Mapping[str, Any],
    base_run: Mapping[str, Any],
    treated_run: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind independent base/treated observations to one fixed manifest."""
    manifest = parse_manifest(manifest_document)
    for run, side in ((base_run, "base"), (treated_run, "treated")):
        if run.get("schema") != RUN_SCHEMA or run.get("side") != side:
            raise IECRefusal(
                "REFUSED_INVALID_PROBE_RUN",
                f"{side} run schema/side mismatch",
            )
        for field in ("manifest_id", "repository", "base_commit", "patch_digest"):
            expected = (
                manifest["manifest_id"]
                if field == "manifest_id"
                else manifest[field]
            )
            if run.get(field) != expected:
                raise IECRefusal(
                    "REFUSED_EXACT_SUBJECT_MISMATCH",
                    f"{side}.{field}={run.get(field)!r}, expected {expected!r}",
                )

    base = _index(base_run)
    treated = _index(treated_run)

    governance: dict[str, list[dict[str, Any]]] = {
        dimension: [] for dimension in DIMENSIONS
    }
    for probe in manifest["probes"]:
        if probe["role"] != "governance":
            continue
        b = base.get(probe["id"])
        t = treated.get(probe["id"])
        if b is None or t is None:
            status = "unavailable"
        elif b["status"] == "pass" and t["status"] == "pass":
            status = "pass"
        elif b["status"] == "timeout" or t["status"] == "timeout":
            status = "timeout"
        elif b["status"] == "unavailable" or t["status"] == "unavailable":
            status = "unavailable"
        else:
            status = "fail"
        governance[str(probe["dimension"])].append(
            {
                "probe_id": probe["id"],
                "status": status,
                "base_receipt_id": None if b is None else b["semantic_id"],
                "treated_receipt_id": None if t is None else t["semantic_id"],
            }
        )

    behavior_probe = next(
        (
            probe
            for probe in manifest["probes"]
            if probe["role"] == "behavior"
        ),
        None,
    )
    behavior = "unavailable"
    if behavior_probe is not None:
        b = base.get(behavior_probe["id"])
        t = treated.get(behavior_probe["id"])
        if b is not None and t is not None:
            if b["status"] != "pass":
                behavior = "invalid"
            elif t["status"] != "pass":
                behavior = "broken"
            elif (
                behavior_probe["comparison"] == "stdout_digest"
                and b["stdout_digest"] != t["stdout_digest"]
            ):
                behavior = "broken"
            else:
                behavior = "preserved"

    mutations = [
        treated.get(probe["id"])
        for probe in manifest["probes"]
        if probe["role"] == "mutation"
        and treated.get(probe["id"]) is not None
    ]
    if behavior_probe is None:
        gate_strength = "none"
    elif not mutations:
        gate_strength = "vacuous"
    elif all(row["status"] == "pass" for row in mutations):
        gate_strength = "detected"
    else:
        gate_strength = "blind"

    mutation_receipt_id = (
        None
        if gate_strength != "detected"
        else content_id(
            "mutation-court",
            manifest["manifest_id"],
            [row["semantic_id"] for row in mutations],
        )
    )

    def singleton_role(role: str) -> dict[str, str]:
        probe = next(
            (p for p in manifest["probes"] if p["role"] == role),
            None,
        )
        if probe is None:
            return {
                "verdict": Verdict.UNSUPPORTED.value,
                "receipt_id": content_id(
                    role,
                    "missing",
                    manifest["manifest_id"],
                ),
            }
        row = treated.get(probe["id"])
        if row is None:
            return {
                "verdict": Verdict.UNSUPPORTED.value,
                "receipt_id": content_id(
                    role,
                    "missing-treated",
                    manifest["manifest_id"],
                ),
            }
        return {
            "verdict": _verdict(str(row["status"])),
            "receipt_id": row["semantic_id"],
        }

    pair: dict[str, Any] = {
        "schema": PAIR_SCHEMA,
        "manifest_id": manifest["manifest_id"],
        "repository": manifest["repository"],
        "base_commit": manifest["base_commit"],
        "patch_digest": manifest["patch_digest"],
        "base_run_id": base_run.get("run_id"),
        "treated_run_id": treated_run.get("run_id"),
        "behavior": behavior,
        "gate_strength": gate_strength,
        "mutation_receipt_id": mutation_receipt_id,
        "clean_environment": singleton_role("clean_environment"),
        "replay": singleton_role("replay"),
        "governance_evidence": governance,
    }
    pair["pair_id"] = content_id(pair)
    return pair


def assemble_case(
    pair: Mapping[str, Any],
    scorecard: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind explicit 1..5 scores to successful paired probe evidence."""
    if pair.get("schema") != PAIR_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_PAIR",
            "invalid pair schema",
        )
    if scorecard.get("schema") != SCORECARD_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_SCORECARD",
            "invalid scorecard schema",
        )
    if scorecard.get("pair_id") != pair.get("pair_id"):
        raise IECRefusal(
            "REFUSED_EXACT_SUBJECT_MISMATCH",
            "scorecard pair_id does not match pair",
        )

    dimensions_raw = scorecard.get("dimensions")
    if not isinstance(dimensions_raw, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_SCORECARD",
            "dimensions must be an object",
        )
    if set(dimensions_raw) != set(DIMENSIONS):
        raise IECRefusal(
            "REFUSED_INVALID_SCORECARD",
            "scorecard must contain exactly the six governance dimensions",
        )

    dimensions: dict[str, Any] = {}
    evidence = pair.get("governance_evidence")
    if not isinstance(evidence, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_PAIR",
            "governance_evidence missing",
        )

    for dimension in DIMENSIONS:
        rows = evidence.get(dimension)
        if not isinstance(rows, list) or not rows:
            dimensions[dimension] = {"evidence_status": "unavailable"}
            continue

        statuses = {
            str(row.get("status"))
            for row in rows
            if isinstance(row, Mapping)
        }
        if statuses != {"pass"}:
            if "timeout" in statuses:
                status = "timeout"
            elif "unavailable" in statuses:
                status = "unavailable"
            else:
                status = "fail"
            dimensions[dimension] = {"evidence_status": status}
            continue

        score = dimensions_raw[dimension]
        if not isinstance(score, Mapping):
            raise IECRefusal(
                "REFUSED_INVALID_SCORECARD",
                f"{dimension} score must be object",
            )
        base = score.get("base")
        treated = score.get("treated")
        for field, value in (("base", base), ("treated", treated)):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 1 <= float(value) <= 5
            ):
                raise IECRefusal(
                    "REFUSED_INVALID_SCORECARD",
                    f"{dimension}.{field} must be in [1,5]",
                )
        dimensions[dimension] = {
            "evidence_status": "pass",
            "base": float(base),
            "treated": float(treated),
        }

    case: dict[str, Any] = {
        "schema": CASE_SCHEMA,
        "repository": pair["repository"],
        "base_commit": pair["base_commit"],
        "patch_digest": pair["patch_digest"],
        "behavior": pair["behavior"],
        "gate_strength": pair["gate_strength"],
        "mutation_receipt_id": pair["mutation_receipt_id"],
        "clean_environment": pair["clean_environment"],
        "replay": pair["replay"],
        "dimensions": dimensions,
        "model": scorecard.get("model"),
        "scaffold": scorecard.get("scaffold"),
    }

    # Parse through the admission court now so malformed assembled cases never escape.
    evaluate_case(case)
    return case


def _read(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IECRefusal(
            "REFUSED_INVALID_PROBE_DOCUMENT",
            f"{path} must be an object",
        )
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run")
    run.add_argument("manifest", type=Path)
    run.add_argument("root", type=Path)
    run.add_argument("side", choices=("base", "treated"))
    run.add_argument("out", type=Path)

    pair = sub.add_parser("pair")
    pair.add_argument("manifest", type=Path)
    pair.add_argument("base_run", type=Path)
    pair.add_argument("treated_run", type=Path)
    pair.add_argument("out", type=Path)

    assemble = sub.add_parser("assemble")
    assemble.add_argument("pair", type=Path)
    assemble.add_argument("scorecard", type=Path)
    assemble.add_argument("out", type=Path)

    args = parser.parse_args(argv)
    if args.command == "run":
        result = execute_manifest(
            _read(args.manifest),
            root=args.root,
            side=args.side,
            env=os.environ,
        )
    elif args.command == "pair":
        result = pair_runs(
            _read(args.manifest),
            _read(args.base_run),
            _read(args.treated_run),
        )
    else:
        result = assemble_case(
            _read(args.pair),
            _read(args.scorecard),
        )

    _write(args.out, result)
    print(
        canonical_json(
            {
                "schema": result["schema"],
                "id": (
                    result.get("run_id")
                    or result.get("pair_id")
                    or content_id(result)
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
