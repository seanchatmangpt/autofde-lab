#!/usr/bin/env python3
"""validate_cli.py — validate a GGenManifestStub with the REAL ggen CLI.

Discovered contract (ggen 26.8.28; `~/.local/bin/ggen` is a bash wrapper that
execs `docker run -v "$PWD:/workspace" -w /workspace ghcr.io/.../ggen-ecosystem`):

  * `ggen graph validate --files <ttl>`   — parse/constraint check of a Turtle file
  * `ggen sync run --dry-run --format json` — resolve/enrich/extract/render, no write
  * no `--manifest` flag: ggen.toml is read from the cwd only, and every path
    inside it must be relative and inside the cwd (the Docker mount).
    Paths under /private/tmp are NOT mounted, so the stage dir lives inside
    the worktree (`.stage/`, gitignored).

Each step returns a dict {cmd, returncode, stdout_tail, stderr_tail, status}.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from manifest import GGenManifestStub, build_stub  # noqa: E402
from packs import load_registry  # noqa: E402
from requirement import CapabilityRequirement, fixture_requirements  # noqa: E402

STAGE_ROOT = os.path.join(HERE, ".stage")


def ggen_available() -> bool:
    return shutil.which("ggen") is not None


def _run(cmd: list[str], cwd: str, timeout: int = 180) -> dict:
    try:
        cp = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "returncode": None, "stdout_tail": "", "stderr_tail": "timeout", "status": "BLOCKED"}
    return {
        "cmd": cmd,
        "returncode": cp.returncode,
        "stdout_tail": cp.stdout[-2000:],
        "stderr_tail": cp.stderr[-2000:],
        "status": "ALIVE" if cp.returncode == 0 else "BLOCKED",
    }


def validate_stub(stub: GGenManifestStub, stage_name: str = "default") -> dict:
    registry = load_registry()
    project_dir = os.path.join(STAGE_ROOT, stage_name)
    shutil.rmtree(project_dir, ignore_errors=True)
    written = stub.write(project_dir, registry)
    result = {"project_dir": project_dir, "written": sorted(written), "preservation": stub.preservation_report()}
    if not ggen_available():
        result["ggen"] = {"status": "UNVERIFIED", "reason": "ggen not on PATH"}
        return result
    ttl_files = [stub.ontology_source, *stub.ontology_imports]
    result["graph_validate"] = _run(
        ["ggen", "graph", "validate", "--format", "json", "--files", ",".join(ttl_files)], project_dir
    )
    result["sync_dry_run"] = _run(["ggen", "sync", "run", "--dry-run", "--format", "json"], project_dir)
    result["ggen"] = {
        "status": "ALIVE"
        if result["graph_validate"]["status"] == "ALIVE" and result["sync_dry_run"]["status"] == "ALIVE"
        else "BLOCKED"
    }
    return result


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        with open(argv[1]) as fh:
            data = json.load(fh)
        reqs = [CapabilityRequirement.from_dict(d) for d in (data if isinstance(data, list) else [data])]
    else:
        reqs = fixture_requirements()
    stub = build_stub(reqs)
    res = validate_stub(stub)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0 if res["ggen"]["status"] == "ALIVE" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
