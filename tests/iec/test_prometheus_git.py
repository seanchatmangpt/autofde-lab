"""Integration court for exact git reconstruction and VGG admission."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.prometheus import DIMENSIONS
from autofde_lab.iec.crowns.prometheus_git import (
    admit_reconstruction,
    run_reconstruction,
)
from autofde_lab.iec.crowns.prometheus_mutation import (
    MUTATION_MANIFEST_SCHEMA,
)
from autofde_lab.iec.crowns.prometheus_probe import (
    MANIFEST_SCHEMA,
    SCORECARD_SCHEMA,
)


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    ).stdout


def repository(tmp_path) -> tuple[Path, str, bytes]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "court@example.test")
    git(repo, "config", "user.name", "Court")
    (repo / "app.txt").write_text("ALLOW\n", encoding="utf-8")
    (repo / "governance.txt").write_text("BASE\n", encoding="utf-8")
    git(repo, "add", "app.txt", "governance.txt")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD").decode().strip()

    (repo / "governance.txt").write_text("TREATED\n", encoding="utf-8")
    patch = git(repo, "diff", "--binary")
    git(repo, "checkout", "--", "governance.txt")
    return repo, base, patch


def probe_manifest(base: str, patch: bytes) -> dict:
    probes = [
        {
            "id": f"gov-{index}",
            "role": "governance",
            "dimension": dimension,
            "scope": "both",
            "argv": [
                sys.executable,
                "-c",
                "raise SystemExit(0)",
            ],
        }
        for index, dimension in enumerate(DIMENSIONS, start=1)
    ]
    probes.append(
        {
            "id": "behavior",
            "role": "behavior",
            "scope": "both",
            "comparison": "stdout_digest",
            "argv": [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    "print(Path('app.txt').read_text(), end='')"
                ),
            ],
        }
    )
    return {
        "schema": MANIFEST_SCHEMA,
        "repository": "org/example",
        "base_commit": base,
        "patch_digest": sha256(patch),
        "probes": probes,
    }


def mutation_manifest(base: str, patch: bytes) -> dict:
    before = sha256(b"ALLOW\n")
    return {
        "schema": MUTATION_MANIFEST_SCHEMA,
        "repository": "org/example",
        "base_commit": base,
        "patch_digest": sha256(patch),
        "verifier": {
            "argv": [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    "raise SystemExit("
                    "0 if 'ALLOW' in Path('app.txt').read_text() else 1)"
                ),
            ],
            "cwd": ".",
            "expected_exit": 0,
            "detection_mode": "exit_changed",
        },
        "mutations": [
            {
                "id": "flip-behavior-token",
                "path": "app.txt",
                "before_sha256": before,
                "operator": "replace_once",
                "old": "ALLOW",
                "new": "DENY",
            }
        ],
    }


def scorecard(pair_id: str) -> dict:
    return {
        "schema": SCORECARD_SCHEMA,
        "pair_id": pair_id,
        "model": "MACHINE_SERIAL",
        "scaffold": "git-reconstruction",
        "dimensions": {
            dimension: {"base": 2, "treated": 4}
            for dimension in DIMENSIONS
        },
    }


def write_patch(tmp_path: Path, patch: bytes) -> Path:
    path = tmp_path / "candidate.patch"
    path.write_bytes(patch)
    return path


def test_full_exact_git_mutation_replay_vgg_round_trip(tmp_path) -> None:
    repo, base, patch = repository(tmp_path)
    manifest = probe_manifest(base, patch)
    reconstruction = run_reconstruction(
        manifest,
        repo_root=repo,
        patch_path=write_patch(tmp_path, patch),
        mutation_manifest=mutation_manifest(base, patch),
    )

    assert reconstruction["base_commit"] == base
    assert reconstruction["clean_environment"]["verdict"] == "PASS"
    assert reconstruction["replay"]["verdict"] == "PASS"
    assert reconstruction["replay_diff"] == []
    assert reconstruction["pair"]["gate_strength"] == "detected"
    assert (
        reconstruction["pair"]["mutation_source"]
        == "reversible-mutation-court"
    )

    admitted = admit_reconstruction(
        reconstruction,
        scorecard(reconstruction["pair"]["pair_id"]),
    )
    assert admitted["report"]["gate"] == "PASS"
    assert admitted["report"]["vgg"]["standing"] == "ALIVE"
    assert admitted["report"]["vgg"]["value"] == pytest.approx(2 / 3)


def test_reconstruction_receipt_is_semantically_replayable(tmp_path) -> None:
    repo, base, patch = repository(tmp_path)
    manifest = probe_manifest(base, patch)
    patch_path = write_patch(tmp_path, patch)
    mutation = mutation_manifest(base, patch)

    first = run_reconstruction(
        manifest,
        repo_root=repo,
        patch_path=patch_path,
        mutation_manifest=mutation,
    )
    second = run_reconstruction(
        manifest,
        repo_root=repo,
        patch_path=patch_path,
        mutation_manifest=mutation,
    )
    assert first["receipt_id"] == second["receipt_id"]
    assert first["pair"]["pair_id"] == second["pair"]["pair_id"]


def test_abbreviated_commit_is_refused_as_moving_subject(tmp_path) -> None:
    repo, base, patch = repository(tmp_path)
    manifest = probe_manifest(base, patch)
    manifest["base_commit"] = base[:12]
    with pytest.raises(
        IECRefusal,
        match="REFUSED_EXACT_BASE_MISMATCH",
    ):
        run_reconstruction(
            manifest,
            repo_root=repo,
            patch_path=write_patch(tmp_path, patch),
        )


def test_patch_digest_must_match_manifest_before_worktrees_exist(
    tmp_path,
) -> None:
    repo, base, patch = repository(tmp_path)
    manifest = probe_manifest(base, patch)
    manifest["patch_digest"] = "sha256:wrong"
    with pytest.raises(
        IECRefusal,
        match="REFUSED_PATCH_DIGEST_MISMATCH",
    ):
        run_reconstruction(
            manifest,
            repo_root=repo,
            patch_path=write_patch(tmp_path, patch),
        )


def test_nondeterministic_probe_is_replay_counterexample(tmp_path) -> None:
    repo, base, patch = repository(tmp_path)
    manifest = probe_manifest(base, patch)
    manifest["probes"][0]["argv"] = [
        sys.executable,
        "-c",
        "import time; print(time.time_ns())",
    ]

    reconstruction = run_reconstruction(
        manifest,
        repo_root=repo,
        patch_path=write_patch(tmp_path, patch),
    )
    assert reconstruction["replay"]["verdict"] == "COUNTEREXAMPLE"
    assert reconstruction["replay_diff"]
    assert any(
        row["probe_id"] == "gov-1"
        for row in reconstruction["replay_diff"]
    )


def test_empty_patch_is_a_lawful_noop_baseline(tmp_path) -> None:
    repo, base, _ = repository(tmp_path)
    patch = b""
    manifest = probe_manifest(base, patch)
    reconstruction = run_reconstruction(
        manifest,
        repo_root=repo,
        patch_path=write_patch(tmp_path, patch),
    )
    assert reconstruction["replay"]["verdict"] == "PASS"
    assert reconstruction["patch_digest"] == sha256(b"")
    assert reconstruction["pair"]["gate_strength"] == "vacuous"


def test_detached_worktrees_are_removed_after_execution(tmp_path) -> None:
    repo, base, patch = repository(tmp_path)
    manifest = probe_manifest(base, patch)
    run_reconstruction(
        manifest,
        repo_root=repo,
        patch_path=write_patch(tmp_path, patch),
    )
    listing = git(repo, "worktree", "list", "--porcelain").decode()
    worktree_lines = [
        line
        for line in listing.splitlines()
        if line.startswith("worktree ")
    ]
    assert len(worktree_lines) == 1
    assert str(repo.resolve()) in worktree_lines[0]


def test_scorecard_from_another_reconstruction_cannot_be_reused(
    tmp_path,
) -> None:
    repo, base, patch = repository(tmp_path)
    manifest = probe_manifest(base, patch)
    reconstruction = run_reconstruction(
        manifest,
        repo_root=repo,
        patch_path=write_patch(tmp_path, patch),
    )
    wrong = scorecard("sha256:other-pair")
    with pytest.raises(
        IECRefusal,
        match="REFUSED_EXACT_SUBJECT_MISMATCH",
    ):
        admit_reconstruction(reconstruction, wrong)
