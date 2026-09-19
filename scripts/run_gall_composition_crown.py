#!/usr/bin/env python3
"""Run GALL-005 compile or fresh KNOWN replay from JSON artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autofde_lab.sa2a.gall.composition import GALLCompositionManifest
from autofde_lab.sa2a.gall.crown import (
    MachineExperienceArtifact,
    compile_verified_experience,
    run_known_replay,
    write_bundle,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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

    args = parser.parse_args()
    manifest = GALLCompositionManifest.from_dict(_load(args.manifest))

    if args.command == "compile":
        deterministic_output = _load(args.output_json)
        artifact, episode_1 = compile_verified_experience(
            manifest, deterministic_output=deterministic_output
        )
        output, episode_2 = run_known_replay(
            manifest, artifact, semantic_key=manifest.semantic_key
        )
        write_bundle(args.out_dir, manifest, artifact, episode_1, episode_2)
        print(json.dumps({"episode_2_output": output, **episode_2.to_dict()}, sort_keys=True))
        return 0

    artifact = MachineExperienceArtifact.from_dict(_load(args.experience))
    output, result = run_known_replay(
        manifest, artifact, semantic_key=args.semantic_key
    )
    print(json.dumps({"output": output, **result.to_dict()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
