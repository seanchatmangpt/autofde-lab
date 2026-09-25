"""Declared generator outputs, read from the generators' own declarations.

One relation, several surface syntaxes:

    DeclaredOutput(declaration, template, target, literal)

* ggen_igniter packs -- EEx frontmatter `to:` in `priv/ggen/<pack>/templates/*.eex`
  (ggen_igniter `lib/ggen_igniter/frontmatter.ex`);
* ggen projects -- `[[generation.rules]]` in any `ggen.toml`, with `template.file`
  and `output_file` (autofde-lab `ggen.toml` is one);
* ggen packages -- Tera frontmatter `to:` in `*.tera` / `*.tmpl` templates
  (ggen-create emits these, `src/ggen_create/package.py`).

A target is `literal` only when it contains no template syntax. A parameterized
target (`lib/<%= name %>.ex`, or a Tera output tag around `row.lower` followed by
`.js`) names a *family* of paths; this
module records it and does not try to evaluate it, so it can never be mistaken for
a claim about one specific committed file.

The target path is interpreted relative to the declaration's project root: the
repository root for pack templates (ggen_igniter runs `mix ggen_igniter.sync` from
its root), the directory holding `ggen.toml` for ggen rules (ggen resolves relative
to the manifest; `[generation] output_dir` is honoured when present).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .census import Census, read_blob
from .model import IECRefusal
from .templates import split_frontmatter

__all__ = ["DeclaredOutput", "declared_outputs", "declared_targets"]

_TEMPLATE_SYNTAX = ("<%", "{{", "{%", "%>", "}}")
_TERA_SUFFIXES = (".tera", ".tmpl")


@dataclass(frozen=True)
class DeclaredOutput:
    syntax: str  # "eex-frontmatter" | "ggen-toml-rule" | "tera-frontmatter"
    declaration: str  # the file that states the relation
    template: str
    target: str  # repository-relative when literal, raw expression otherwise
    literal: bool
    rule: str = ""
    query: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "syntax": self.syntax,
            "declaration": self.declaration,
            "template": self.template,
            "target": self.target,
            "literal": self.literal,
            "rule": self.rule,
            "query": self.query,
        }


def _is_literal(target: str) -> bool:
    return bool(target) and not any(mark in target for mark in _TEMPLATE_SYNTAX)


def _join(root: PurePosixPath, relative: str) -> str:
    parts: list[str] = []
    for part in (root / relative).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise IECRefusal("REFUSED_PATH_ESCAPE", f"{root}/{relative}")
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def declared_outputs(census: Census, checkout: Path) -> list[DeclaredOutput]:
    subject = census.subject
    found: list[DeclaredOutput] = []
    for record in census.files:
        path = PurePosixPath(record.path)
        if record.binary:
            continue
        if path.suffix == ".eex" and path.parent.name == "templates":
            text = read_blob(subject, checkout, record.path).decode("utf-8", "replace")
            header, _unsupported, _body = (
                split_frontmatter(text)
                if text.startswith("---\n")
                else (None, [], text)
            )
            target = (header or {}).get("to")
            if target:
                literal = _is_literal(target)
                found.append(
                    DeclaredOutput(
                        "eex-frontmatter",
                        record.path,
                        record.path,
                        _join(PurePosixPath(""), target) if literal else target,
                        literal,
                    )
                )
        elif path.suffix in _TERA_SUFFIXES:
            text = read_blob(subject, checkout, record.path).decode("utf-8", "replace")
            if not text.startswith("---\n"):
                continue
            try:
                header, _unsupported, _body = split_frontmatter(text)
            except IECRefusal:
                continue
            target = (header or {}).get("to")
            if target:
                literal = _is_literal(target)
                found.append(
                    DeclaredOutput(
                        "tera-frontmatter",
                        record.path,
                        record.path,
                        _join(path.parent, target) if literal else target,
                        literal,
                    )
                )
        elif path.name == "ggen.toml":
            data = tomllib.loads(
                read_blob(subject, checkout, record.path).decode("utf-8")
            )
            root = path.parent
            output_dir = str(data.get("generation", {}).get("output_dir", "."))
            for rule in data.get("generation", {}).get("rules", []):
                target = str(rule.get("output_file", ""))
                template = rule.get("template", {})
                template_file = (
                    template.get("file", "") if isinstance(template, dict) else ""
                )
                query = rule.get("query", {})
                query_file = query.get("file", "") if isinstance(query, dict) else ""
                if not target:
                    continue
                literal = _is_literal(target)
                found.append(
                    DeclaredOutput(
                        "ggen-toml-rule",
                        record.path,
                        _join(root, template_file) if template_file else "",
                        _join(root / output_dir, target) if literal else target,
                        literal,
                        rule=str(rule.get("name", "")),
                        query=_join(root, query_file) if query_file else "",
                    )
                )
    return sorted(found, key=lambda item: (item.target, item.declaration, item.rule))


def declared_targets(outputs: list[DeclaredOutput]) -> dict[str, dict[str, str]]:
    """Literal target -> its declaration, for `census(..., declared_targets=...)`.

    Two declarations claiming one literal path are both kept, joined, and marked
    contested: the census must not pick one producer by fiat.
    """
    targets: dict[str, dict[str, str]] = {}
    for output in outputs:
        if not output.literal:
            continue
        entry = {
            "syntax": output.syntax,
            "declaration": output.declaration,
            "template": output.template,
            "rule": output.rule,
        }
        if output.target in targets:
            previous = targets[output.target]
            targets[output.target] = {
                "contested": "true",
                "declarations": ";".join(
                    sorted(
                        {
                            previous.get(
                                "declaration", previous.get("declarations", "")
                            ),
                            output.declaration,
                        }
                    )
                ),
            }
        else:
            targets[output.target] = entry
    return targets
