#!/usr/bin/env python3
"""WS2 Repo Action-Surface Discovery.

    python3 discover.py <repo_root> --out surface.json [--run-help] [--ocel out.ocel.json]
                        [--max-depth N] [--scratch DIR]

Reads build/CI/infra declarations under <repo_root> and projects them to
CandidateCapability[] (see model.py). No command is executed in <repo_root>.
With --run-help, `<bin> --help` is executed for binaries found on PATH, with
cwd = --scratch (never the repo). With --ocel, each capability is appended as an
Action object to an OCEL 2.0 log via tools/ocel_v2/emitter.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..", "ocel_v2")))

import extractors as X  # noqa: E402
from classify import propagate_dependencies  # noqa: E402
from model import RepoSurface, CandidateCapability  # noqa: E402

_FILE_EXTRACTORS = [
    (lambda n: n.lower() == "justfile" or n == ".justfile", "justfile", X.extract_justfile),
    (lambda n: n in ("Makefile", "makefile", "GNUmakefile"), "makefile", X.extract_makefile),
    (lambda n: n in ("Taskfile.yml", "Taskfile.yaml", "taskfile.yml"), "taskfile", X.extract_taskfile),
    (lambda n: n == "package.json", "package_json", X.extract_package_json),
    (lambda n: n == "mix.exs", "mix_exs", X.extract_mix_exs),
    (lambda n: n == "Cargo.toml", "cargo_toml", X.extract_cargo_toml),
    (lambda n: n == "pyproject.toml", "pyproject", X.extract_pyproject),
    (lambda n: n.startswith("Dockerfile"), "dockerfile", X.extract_dockerfile),
    (lambda n: n in ("compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml") or (n.startswith("compose.") and n.endswith((".yml", ".yaml"))), "compose", X.extract_compose),
]


def discover(root: str, repo: str | None = None, max_depth: int = 4, run_help: bool = False, scratch: str | None = None) -> RepoSurface:
    root = os.path.abspath(root)
    repo = repo or os.path.basename(root)
    surf = RepoSurface(repo=repo, root=root, generated_at=datetime.now(timezone.utc).isoformat())
    seen_cargo_ws_members: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath[len(root):].count(os.sep)
        skipped = [d for d in dirnames if d in X.SKIP_DIRS or (d.startswith(".") and d != ".github" and d != ".cargo")]
        for d in skipped:
            surf.skipped_dirs.append(os.path.relpath(os.path.join(dirpath, d), root))
        dirnames[:] = sorted(d for d in dirnames if d not in skipped)
        if depth >= max_depth:
            dirnames[:] = []
        rel_dir = os.path.relpath(dirpath, root)
        # GitHub workflows
        if rel_dir == os.path.join(".github", "workflows"):
            for fn in sorted(filenames):
                if fn.endswith((".yml", ".yaml")):
                    p = os.path.join(dirpath, fn)
                    surf.sources.append({"kind": "github_workflow", "path": os.path.relpath(p, root)})
                    surf.capabilities.extend(X.extract_github_workflow(repo, root, p))
            continue
        # .cargo/config
        if os.path.basename(dirpath) == ".cargo":
            for fn in ("config.toml", "config"):
                p = os.path.join(dirpath, fn)
                if os.path.exists(p):
                    surf.sources.append({"kind": "cargo_config", "path": os.path.relpath(p, root)})
                    surf.capabilities.extend(X.extract_cargo_config(repo, root, p))
            continue
        tf = [f for f in filenames if f.endswith(".tf")]
        if tf:
            surf.sources.append({"kind": "terraform", "path": rel_dir})
            surf.capabilities.extend(X.extract_terraform_dir(repo, root, dirpath, tf))
        for fn in sorted(filenames):
            for pred, kind, fn_extract in _FILE_EXTRACTORS:
                if pred(fn):
                    p = os.path.join(dirpath, fn)
                    if kind == "cargo_toml" and os.path.abspath(p) in seen_cargo_ws_members:
                        break
                    surf.sources.append({"kind": kind, "path": os.path.relpath(p, root)})
                    caps = list(fn_extract(repo, root, p))
                    if kind == "cargo_toml":
                        for c in caps:
                            seen_cargo_ws_members.add(os.path.abspath(os.path.join(root, c.evidence_source.rsplit(":", 1)[0])))
                    surf.capabilities.extend(caps)
                    break
    # case-insensitive filesystems: justfile + Justfile resolve to one file -> dedupe by evidence+name
    dedup: dict[tuple[str, str, str], CandidateCapability] = {}
    for c in surf.capabilities:
        key = (c.source_kind, c.evidence_source.rsplit(":", 1)[0].lower(), c.name)
        dedup.setdefault(key, c)
    surf.capabilities = list(dedup.values())
    uniq_sources = {(s["kind"], s["path"].lower()): s for s in surf.sources}
    surf.sources = list(uniq_sources.values())
    propagate_dependencies(surf.capabilities)
    if run_help:
        bins = X.declared_cli_binaries(surf.capabilities)
        surf.capabilities.extend(X.extract_cli_help(repo, bins, scratch or os.getcwd()))
    # unique ids (same command from two files in the same kind is legal; ids include name+command)
    ids: dict[str, int] = {}
    for c in surf.capabilities:
        if c.id in ids:
            ids[c.id] += 1
            c.id = f"{c.id}#{ids[c.id]}"
        else:
            ids[c.id] = 0
    return surf


def emit_ocel(surf: RepoSurface, ocel_path: str) -> dict:
    import emitter  # tools/ocel_v2/emitter.py

    if not os.path.exists(ocel_path):
        emitter.init(ocel_path)
    repo_id = f"repo:{surf.repo}"
    log = emitter._read(ocel_path)
    if not any(o["id"] == repo_id for o in log["objects"]):
        emitter.add_object(ocel_path, "Repository", repo_id, {"path": surf.root, "remote_url": "", "default_branch": ""})
    # batch: emitter is per-call read/write; build in memory via its validators then write once
    for c in surf.capabilities:
        emitter.add_object(ocel_path, "Action", f"{surf.repo}/{c.id}", {"name": c.name, "kind": f"{c.source_kind}/{c.authority_class}"})
    emitter.add_event(ocel_path, "WorldStateObserved", f"ws2:surface:{surf.repo}:{surf.generated_at}",
                      {"label": f"ws2 surface {surf.repo}: {len(surf.capabilities)} capabilities"}, [repo_id])
    return emitter._read(ocel_path)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo")
    ap.add_argument("--run-help", action="store_true")
    ap.add_argument("--ocel")
    ap.add_argument("--max-depth", type=int, default=4)
    ap.add_argument("--scratch")
    a = ap.parse_args(argv[1:])
    surf = discover(a.root, a.repo, a.max_depth, a.run_help, a.scratch)
    surf.dump(a.out)
    j = surf.to_json()
    print(json.dumps({"repo": surf.repo, "out": a.out, "sources": len(surf.sources), **j["summary"]}, indent=2))
    if a.ocel:
        emit_ocel(surf, a.ocel)
        print(json.dumps({"ocel": a.ocel}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
