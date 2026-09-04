#!/usr/bin/env python3
"""packs.py — registry of admitted ggen-marketplace packs, read from disk.

A pack is ADMITTED for WS4 binding when it has a `pack.toml` AND a
`ggen.toml` manifest AND at least one `templates/*.tera` and one
`queries/*.rq`. This is the shape the real marketplace uses
(observed: 215 packs with pack.toml, 81 with ggen.toml).
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field

DEFAULT_PACKS_ROOT = os.path.expanduser("~/ggen-marketplace/packs")


@dataclass(frozen=True)
class PackInfo:
    name: str
    version: str
    path: str
    ontology: str                       # absolute path to the pack ontology source
    templates: tuple[str, ...]          # basenames
    queries: tuple[str, ...]            # basenames
    rules: tuple[dict, ...] = field(default_factory=tuple)

    def template_path(self, basename: str) -> str:
        return os.path.join(self.path, "templates", basename)

    def query_path(self, basename: str) -> str:
        return os.path.join(self.path, "queries", basename)


def _listdir(p: str, suffix: str) -> tuple[str, ...]:
    if not os.path.isdir(p):
        return ()
    return tuple(sorted(f for f in os.listdir(p) if f.endswith(suffix)))


def load_pack(pack_dir: str) -> PackInfo | None:
    pack_toml = os.path.join(pack_dir, "pack.toml")
    ggen_toml = os.path.join(pack_dir, "ggen.toml")
    if not (os.path.isfile(pack_toml) and os.path.isfile(ggen_toml)):
        return None
    with open(pack_toml, "rb") as fh:
        pack = tomllib.load(fh).get("pack", {})
    with open(ggen_toml, "rb") as fh:
        manifest = tomllib.load(fh)
    templates = _listdir(os.path.join(pack_dir, "templates"), ".tera")
    queries = _listdir(os.path.join(pack_dir, "queries"), ".rq")
    if not templates or not queries:
        return None
    ont_src = manifest.get("ontology", {}).get("source", "ontology.ttl")
    return PackInfo(
        name=pack.get("name", os.path.basename(pack_dir)),
        version=str(pack.get("version", "")),
        path=os.path.abspath(pack_dir),
        ontology=os.path.abspath(os.path.join(pack_dir, ont_src)),
        templates=templates,
        queries=queries,
        rules=tuple(manifest.get("generation", {}).get("rules", [])),
    )


def load_registry(root: str = DEFAULT_PACKS_ROOT) -> dict[str, PackInfo]:
    reg: dict[str, PackInfo] = {}
    if not os.path.isdir(root):
        return reg
    for entry in sorted(os.listdir(root)):
        info = load_pack(os.path.join(root, entry))
        if info is not None:
            reg[info.name] = info
    return reg


if __name__ == "__main__":
    reg = load_registry()
    print(f"admitted packs: {len(reg)}")
    for name, p in list(reg.items())[:10]:
        print(f"  {name} v{p.version} templates={len(p.templates)} queries={len(p.queries)}")
