"""Authority classification of shell command text, driven by rules.json."""
from __future__ import annotations

import json
import os
import re
from typing import Any

_RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json")

with open(_RULES_PATH, "r", encoding="utf-8") as _f:
    RULES: dict[str, Any] = json.load(_f)

CLASS_ORDER: list[str] = RULES["class_order"]
_RANK = {c: i for i, c in enumerate(CLASS_ORDER)}
_COMPILED = [(r["class"], re.compile(r["pattern"]), r) for r in RULES["rules"]]
_REV_RANK = {"IDEMPOTENT": 0, "REVERSIBLE": 1, "UNKNOWN": 2, "IRREVERSIBLE": 3}

_STRIP_PREFIX = re.compile(r"^[@\-+]+\s*")
_ENV_ASSIGN = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+")


def split_shell_lines(command: str) -> list[str]:
    """Split a recipe body into classifiable simple commands (by newline, &&, ||, ;, |)."""
    out: list[str] = []
    for raw in command.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.rstrip("\\").strip()
        for part in re.split(r"\s*(?:&&|\|\||;|\|)\s*", line):
            part = _STRIP_PREFIX.sub("", part.strip())
            part = _ENV_ASSIGN.sub("", part)
            if part:
                out.append(part)
    return out


def classify_line(line: str) -> dict[str, str]:
    for cls, rx, rule in _COMPILED:
        if rx.search(line):
            return {"class": cls, "effect": rule["effect"], "reversibility": rule["reversibility"], "pattern": rule["pattern"]}
    d = RULES["default"]
    return {"class": d["class"], "effect": d["effect"], "reversibility": d["reversibility"], "pattern": ""}


def classify_command(command: str) -> dict[str, Any]:
    """Return {authority_class, reversibility, effects[], qualification_strategy, matched[]}."""
    lines = split_shell_lines(command)
    best_cls = "READ"
    best_rev = "IDEMPOTENT"
    effects: list[str] = []
    matched: list[dict[str, str]] = []
    for ln in lines:
        c = classify_line(ln)
        matched.append({"line": ln, **c})
        if _RANK[c["class"]] > _RANK[best_cls]:
            best_cls = c["class"]
        if _REV_RANK[c["reversibility"]] > _REV_RANK[best_rev]:
            best_rev = c["reversibility"]
        if c["effect"] and c["effect"] not in effects:
            effects.append(c["effect"])
    if not lines:
        effects.append("no command lines (dependency-only recipe)")
    return {
        "authority_class": best_cls,
        "reversibility": best_rev,
        "effects": effects,
        "qualification_strategy": RULES["qualification_by_class"][best_cls],
        "matched": matched,
    }


def max_class(a: str, b: str) -> str:
    return a if _RANK[a] >= _RANK[b] else b


def max_rev(a: str, b: str) -> str:
    return a if _REV_RANK[a] >= _REV_RANK[b] else b


def propagate_dependencies(caps: list, name_key=lambda c: c.name) -> None:
    """Recipes inherit the max class/reversibility of their transitive depends_on
    (matched within the same source_kind + evidence file)."""
    by_key: dict[tuple[str, str, str], Any] = {}
    for c in caps:
        by_key[(c.source_kind, c.evidence_source.rsplit(":", 1)[0], name_key(c))] = c

    def resolve(c, seen: set) -> tuple[str, str]:
        if id(c) in seen:
            return c.authority_class, c.reversibility
        seen.add(id(c))
        cls, rev = c.authority_class, c.reversibility
        for dep in c.depends_on:
            d = by_key.get((c.source_kind, c.evidence_source.rsplit(":", 1)[0], dep))
            if d is None:
                continue
            dcls, drev = resolve(d, seen)
            if _RANK[dcls] > _RANK[cls]:
                cls = dcls
                c.notes.append(f"authority_class inherited from dependency '{dep}'")
            rev = max_rev(rev, drev)
        c.authority_class, c.reversibility = cls, rev
        c.qualification_strategy = RULES["qualification_by_class"][cls]
        return cls, rev

    for c in caps:
        resolve(c, set())
