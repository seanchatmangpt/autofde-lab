"""WS2 data model: RepoSurface -> CandidateCapability[] (stdlib only).

A CandidateCapability is the minimum record the Crown-2 authority plane needs
to decide whether an action discovered in a repository may be run, and how it
would be qualified. Everything here is a *candidate*: nothing is executed by
discovery except `--help` of binaries already on PATH (opt-in).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any

AUTHORITY_CLASSES = ("READ", "REVERSIBLE_BUILD", "NETWORK_FETCH", "CONSEQUENTIAL", "DESTRUCTIVE")
REVERSIBILITY = ("IDEMPOTENT", "REVERSIBLE", "IRREVERSIBLE", "UNKNOWN")

SOURCE_KINDS = (
    "justfile", "makefile", "taskfile", "package_json", "mix_exs", "cargo_toml",
    "cargo_config", "pyproject", "github_workflow", "dockerfile", "compose",
    "terraform", "cli_help",
)


@dataclass
class CandidateCapability:
    id: str
    name: str
    source_kind: str
    command: str
    cwd: str
    evidence_source: str
    authority_class: str
    reversibility: str
    preconditions: list[str] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    qualification_strategy: str = ""
    depends_on: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    help_excerpt: str = ""

    def validate(self) -> None:
        assert self.authority_class in AUTHORITY_CLASSES, self.authority_class
        assert self.reversibility in REVERSIBILITY, self.reversibility
        assert self.source_kind in SOURCE_KINDS, self.source_kind
        assert ":" in self.evidence_source, self.evidence_source
        assert self.command.strip(), "empty command"


def make_id(repo: str, source_kind: str, name: str, command: str) -> str:
    h = hashlib.sha256(f"{repo}|{source_kind}|{name}|{command}".encode()).hexdigest()[:12]
    return f"cap:{source_kind}:{name}:{h}"


@dataclass
class RepoSurface:
    repo: str
    root: str
    generated_at: str
    sources: list[dict[str, str]] = field(default_factory=list)
    capabilities: list[CandidateCapability] = field(default_factory=list)
    skipped_dirs: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["summary"] = {
            "capabilities": len(self.capabilities),
            "by_authority_class": {
                c: sum(1 for x in self.capabilities if x.authority_class == c) for c in AUTHORITY_CLASSES
            },
            "by_source_kind": {
                k: sum(1 for x in self.capabilities if x.source_kind == k)
                for k in SOURCE_KINDS
                if any(x.source_kind == k for x in self.capabilities)
            },
        }
        return d

    def dump(self, path: str) -> None:
        for c in self.capabilities:
            c.validate()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, indent=2, sort_keys=True)
            f.write("\n")
