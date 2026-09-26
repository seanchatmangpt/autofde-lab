"""Clean git reconstruction and replay harness for SWE-Prometheus/VGG."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .model import IECRefusal, Verdict, canonical_json, content_id
from .prometheus import evaluate_case
from .prometheus_mutation import run_mutation_court
from .prometheus_probe import (
    PAIR_SCHEMA,
    SCORECARD_SCHEMA,
    assemble_case,
    execute_manifest,
    pair_runs,
    parse_manifest,
)

RECONSTRUCTION_SCHEMA = "autofde-lab.swe-prometheus-reconstruction/1"
ADMISSION_SCHEMA = "autofde-lab.swe-prometheus-admission-bundle/1"
COMMAND_TIMEOUT_SECONDS = 120.0


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            argv,
            cwd=None if cwd is None else str(cwd),
            input=input_bytes,
            capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = bytes(exc.stdout or b"")
        stderr = bytes(exc.stderr or b"")
        return {
            "argv": argv,
            "status": "timeout",
            "exit_code": None,
            "stdout_digest": _sha256(stdout),
            "stderr_digest": _sha256(stderr),
        }
    except (FileNotFoundError, PermissionError, OSError) as exc:
        return {
            "argv": argv,
            "status": "unavailable",
            "exit_code": None,
            "stdout_digest": _sha256(b""),
            "stderr_digest": _sha256(
                str(exc).encode("utf-8", errors="replace")
            ),
        }

    stdout = bytes(proc.stdout or b"")
    stderr = bytes(proc.stderr or b"")
    return {
        "argv": argv,
        "status": "pass" if proc.returncode == 0 else "fail",
        "exit_code": int(proc.returncode),
        "stdout": stdout,
        "stderr": stderr,
        "stdout_digest": _sha256(stdout),
        "stderr_digest": _sha256(stderr),
    }


def _require_command(
    result: Mapping[str, Any],
    *,
    code: str,
    detail: str,
) -> Mapping[str, Any]:
    if result.get("status") != "pass":
        raise IECRefusal(
            code,
            f"{detail}: status={result.get('status')} "
            f"exit={result.get('exit_code')} "
            f"stderr={result.get('stderr_digest')}",
        )
    return result


def _git(
    repo_root: Path,
    *args: str,
    input_bytes: bytes | None = None,
) -> dict[str, Any]:
    return _run(
        ["git", "-C", str(repo_root), *args],
        input_bytes=input_bytes,
    )


def _decode_stdout(result: Mapping[str, Any]) -> str:
    raw = result.get("stdout")
    if not isinstance(raw, (bytes, bytearray)):
        return ""
    return bytes(raw).decode("utf-8", errors="strict").strip()


def _resolve_exact_commit(repo_root: Path, requested: str) -> str:
    result = _require_command(
        _git(repo_root, "rev-parse", "--verify", f"{requested}^{{commit}}"),
        code="REFUSED_EXACT_BASE_UNAVAILABLE",
        detail=f"cannot resolve base commit {requested}",
    )
    resolved = _decode_stdout(result)
    if resolved != requested:
        raise IECRefusal(
            "REFUSED_EXACT_BASE_MISMATCH",
            f"requested {requested!r} resolved to {resolved!r}; "
            "abbreviated/moving refs are not exact subjects",
        )
    return resolved


def _tree_id(repo_root: Path, commit: str) -> str:
    result = _require_command(
        _git(repo_root, "rev-parse", f"{commit}^{{tree}}"),
        code="REFUSED_EXACT_BASE_UNAVAILABLE",
        detail=f"cannot resolve tree for {commit}",
    )
    return _decode_stdout(result)


def _status_clean(worktree: Path) -> bool:
    result = _require_command(
        _git(
            worktree,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ),
        code="REFUSED_RECONSTRUCTION_COMMAND_FAILED",
        detail=f"cannot inspect worktree {worktree}",
    )
    return _decode_stdout(result) == ""


def _add_worktree(repo_root: Path, target: Path, commit: str) -> None:
    _require_command(
        _git(
            repo_root,
            "worktree",
            "add",
            "--detach",
            str(target),
            commit,
        ),
        code="REFUSED_RECONSTRUCTION_COMMAND_FAILED",
        detail=f"cannot materialize detached worktree at {target}",
    )


def _remove_worktree(repo_root: Path, target: Path) -> None:
    result = _git(
        repo_root,
        "worktree",
        "remove",
        "--force",
        str(target),
    )
    if result.get("status") != "pass" and target.exists():
        raise IECRefusal(
            "REFUSED_RECONSTRUCTION_CLEANUP_FAILED",
            f"could not remove worktree {target}: "
            f"{result.get('stderr_digest')}",
        )


def _apply_patch(worktree: Path, patch_bytes: bytes) -> dict[str, Any]:
    if not patch_bytes:
        return {
            "status": "pass",
            "mode": "empty-noop",
            "semantic_id": content_id("git-apply", "empty-noop"),
        }
    result = _require_command(
        _git(
            worktree,
            "apply",
            "--binary",
            "--whitespace=nowarn",
            "-",
            input_bytes=patch_bytes,
        ),
        code="REFUSED_PATCH_APPLY_FAILED",
        detail=f"patch failed to apply to {worktree}",
    )
    return {
        "status": "pass",
        "mode": "git-apply",
        "semantic_id": content_id(
            "git-apply",
            result["exit_code"],
            result["stdout_digest"],
            result["stderr_digest"],
        ),
    }


def _receipt(
    *,
    kind: str,
    verdict: str,
    stable_parts: list[Any],
) -> dict[str, str]:
    return {
        "verdict": verdict,
        "receipt_id": content_id(kind, *stable_parts),
    }


def _run_diff(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> list[dict[str, Any]]:
    def index(run: Mapping[str, Any]) -> dict[str, str]:
        rows = run.get("receipts")
        if not isinstance(rows, list):
            return {}
        return {
            str(row.get("probe_id")): str(row.get("semantic_id"))
            for row in rows
            if isinstance(row, Mapping)
        }

    left = index(first)
    right = index(second)
    keys = sorted(set(left) | set(right))
    return [
        {
            "probe_id": key,
            "treated": left.get(key),
            "replay": right.get(key),
        }
        for key in keys
        if left.get(key) != right.get(key)
    ]


def run_reconstruction(
    manifest_document: Mapping[str, Any],
    *,
    repo_root: Path,
    patch_path: Path,
    mutation_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconstruct base/treated/replay from one exact git commit and patch."""
    manifest = parse_manifest(manifest_document)
    repo_root = repo_root.resolve()
    patch_path = patch_path.resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise IECRefusal(
            "REFUSED_RECONSTRUCTION_SUBJECT_UNAVAILABLE",
            f"repository root does not exist: {repo_root}",
        )
    if not patch_path.exists() or not patch_path.is_file():
        raise IECRefusal(
            "REFUSED_RECONSTRUCTION_SUBJECT_UNAVAILABLE",
            f"patch does not exist: {patch_path}",
        )

    patch_bytes = patch_path.read_bytes()
    patch_digest = _sha256(patch_bytes)
    if patch_digest != manifest["patch_digest"]:
        raise IECRefusal(
            "REFUSED_PATCH_DIGEST_MISMATCH",
            f"{patch_digest} != {manifest['patch_digest']}",
        )

    base_commit = _resolve_exact_commit(repo_root, manifest["base_commit"])
    base_tree = _tree_id(repo_root, base_commit)

    with tempfile.TemporaryDirectory(
        prefix="autofde-prometheus-reconstruction-"
    ) as directory:
        root = Path(directory)
        base_worktree = root / "base"
        treated_worktree = root / "treated"
        replay_worktree = root / "replay"
        materialized: list[Path] = []
        try:
            for target in (
                base_worktree,
                treated_worktree,
                replay_worktree,
            ):
                _add_worktree(repo_root, target, base_commit)
                materialized.append(target)

            initial_clean = {
                "base": _status_clean(base_worktree),
                "treated": _status_clean(treated_worktree),
                "replay": _status_clean(replay_worktree),
            }
            if not all(initial_clean.values()):
                raise IECRefusal(
                    "REFUSED_DIRTY_RECONSTRUCTION",
                    f"new detached worktrees were not clean: {initial_clean}",
                )

            treated_apply = _apply_patch(treated_worktree, patch_bytes)
            replay_apply = _apply_patch(replay_worktree, patch_bytes)

            base_run = execute_manifest(
                manifest_document,
                root=base_worktree,
                side="base",
            )
            treated_run = execute_manifest(
                manifest_document,
                root=treated_worktree,
                side="treated",
            )
            replay_run = execute_manifest(
                manifest_document,
                root=replay_worktree,
                side="treated",
            )

            clean_receipt = _receipt(
                kind="clean-reconstruction",
                verdict=Verdict.PASS.value,
                stable_parts=[
                    manifest["repository"],
                    base_commit,
                    base_tree,
                    patch_digest,
                    initial_clean,
                    treated_apply["semantic_id"],
                    replay_apply["semantic_id"],
                ],
            )

            replay_diff = _run_diff(treated_run, replay_run)
            replay_verdict = (
                Verdict.PASS.value
                if treated_run["run_id"] == replay_run["run_id"]
                else Verdict.COUNTEREXAMPLE.value
            )
            replay_receipt = _receipt(
                kind="semantic-replay",
                verdict=replay_verdict,
                stable_parts=[
                    manifest["repository"],
                    base_commit,
                    patch_digest,
                    treated_run["run_id"],
                    replay_run["run_id"],
                    replay_diff,
                ],
            )

            mutation_report = (
                None
                if mutation_manifest is None
                else run_mutation_court(
                    mutation_manifest,
                    root=treated_worktree,
                )
            )

            pair = pair_runs(
                manifest_document,
                base_run,
                treated_run,
                mutation_report=mutation_report,
                clean_environment_receipt=clean_receipt,
                replay_receipt=replay_receipt,
            )

            result: dict[str, Any] = {
                "schema": RECONSTRUCTION_SCHEMA,
                "repository": manifest["repository"],
                "base_commit": base_commit,
                "base_tree": base_tree,
                "patch_digest": patch_digest,
                "manifest_id": manifest["manifest_id"],
                "clean_environment": clean_receipt,
                "replay": replay_receipt,
                "replay_diff": replay_diff,
                "base_run": base_run,
                "treated_run": treated_run,
                "replay_run": replay_run,
                "mutation_report": mutation_report,
                "pair": pair,
                "claim_ceiling": (
                    "clean reconstruction proves exact local git materialization "
                    "and patch replay for this subject; it does not imply deployed "
                    "production standing"
                ),
            }
            result["receipt_id"] = content_id(
                result["schema"],
                result["repository"],
                result["base_commit"],
                result["base_tree"],
                result["patch_digest"],
                result["manifest_id"],
                clean_receipt,
                replay_receipt,
                pair["pair_id"],
                (
                    None
                    if mutation_report is None
                    else mutation_report["receipt_id"]
                ),
            )
            return result
        finally:
            for target in reversed(materialized):
                _remove_worktree(repo_root, target)
            _git(repo_root, "worktree", "prune")


def admit_reconstruction(
    reconstruction: Mapping[str, Any],
    scorecard: Mapping[str, Any],
) -> dict[str, Any]:
    if reconstruction.get("schema") != RECONSTRUCTION_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_RECONSTRUCTION_RECEIPT",
            "invalid reconstruction schema",
        )
    pair = reconstruction.get("pair")
    if not isinstance(pair, Mapping) or pair.get("schema") != PAIR_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_RECONSTRUCTION_RECEIPT",
            "reconstruction has no valid pair",
        )
    if scorecard.get("schema") != SCORECARD_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_SCORECARD",
            "invalid scorecard schema",
        )
    case = assemble_case(pair, scorecard)
    report = evaluate_case(case)
    result = {
        "schema": ADMISSION_SCHEMA,
        "reconstruction_receipt_id": reconstruction.get("receipt_id"),
        "pair_id": pair["pair_id"],
        "case": case,
        "report": report,
    }
    result["id"] = content_id(result)
    return result


def _read(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IECRefusal(
            "REFUSED_INVALID_RECONSTRUCTION_DOCUMENT",
            f"{path} must contain a JSON object",
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
    run.add_argument("repo_root", type=Path)
    run.add_argument("patch", type=Path)
    run.add_argument("out", type=Path)
    run.add_argument("--mutation-manifest", type=Path)

    admit = sub.add_parser("admit")
    admit.add_argument("reconstruction", type=Path)
    admit.add_argument("scorecard", type=Path)
    admit.add_argument("out", type=Path)

    args = parser.parse_args(argv)
    if args.command == "run":
        result = run_reconstruction(
            _read(args.manifest),
            repo_root=args.repo_root,
            patch_path=args.patch,
            mutation_manifest=(
                _read(args.mutation_manifest)
                if args.mutation_manifest
                else None
            ),
        )
        summary = {
            "receipt_id": result["receipt_id"],
            "pair_id": result["pair"]["pair_id"],
            "replay": result["replay"]["verdict"],
            "gate_strength": result["pair"]["gate_strength"],
        }
    else:
        result = admit_reconstruction(
            _read(args.reconstruction),
            _read(args.scorecard),
        )
        summary = {
            "id": result["id"],
            "gate": result["report"]["gate"],
            "standing": result["report"]["vgg"]["standing"],
        }

    _write(args.out, result)
    print(canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
