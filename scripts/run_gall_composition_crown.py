#!/usr/bin/env python3
"""Run the exact-head GALL-005 compile or fresh KNOWN replay court."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from autofde_lab.sa2a.gall.composition import GALLCompositionManifest
from autofde_lab.sa2a.gall.crown import (
    MachineExperienceArtifact,
    compile_verified_experience,
    run_known_replay,
    write_compile_bundle,
    write_replay_bundle,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _observed_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "BLOCKED_EXACT_HEAD: git rev-parse HEAD failed; the GALL-005 court "
            "requires a verified checkout"
        )
    return completed.stdout.strip()


def _require_exact_head(manifest: GALLCompositionManifest) -> None:
    observed = _observed_head()
    if observed != manifest.autofde_lab_sha:
        raise RuntimeError(
            "REFUSED_EXACT_HEAD: composition manifest autofde_lab_sha "
            f"{manifest.autofde_lab_sha} != observed checkout {observed}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    compile_cmd = sub.add_parser("compile")
    compile_cmd.add_argument("--manifest", required=True)
    compile_cmd.add_argument("--output-json", required=True)
    compile_cmd.add_argument("--out-dir", required=True)

    replay_cmd = sub.add_parser("replay")
    replay_cmd.add_argument("--manifest", required=True)
    replay_cmd.add_argument("--experience", required=True)
    replay_cmd.add_argument("--semantic-key", required=True)
    replay_cmd.add_argument("--out-dir")

    args = parser.parse_args()
    manifest = GALLCompositionManifest.from_dict(_load(args.manifest))
    try:
        _require_exact_head(manifest)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 78 if str(exc).startswith("BLOCKED_EXACT_HEAD") else 65

    if args.command == "compile":
        artifact, episode_1 = compile_verified_experience(
            manifest,
            deterministic_output=_load(args.output_json),
        )
        write_compile_bundle(args.out_dir, manifest, artifact, episode_1)
        print(
            json.dumps(
                {
                    "machine_experience_digest": artifact.digest,
                    "gate_12": "OPEN",
                    **episode_1.to_dict(),
                },
                sort_keys=True,
            )
        )
        return 0

    artifact = MachineExperienceArtifact.from_dict(_load(args.experience))
    output, result = run_known_replay(
        manifest,
        artifact,
        semantic_key=args.semantic_key,
    )
    if args.out_dir:
        write_replay_bundle(args.out_dir, manifest, artifact, result)
    print(json.dumps({"output": output, **result.to_dict()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
