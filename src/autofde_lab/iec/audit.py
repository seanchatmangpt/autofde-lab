"""Mechanized generated-output audit -- the replacement for a repeated LLM task.

The reasoning class (`retirement.GENERATED_OUTPUT_AUDIT`): *for one commit, which
committed files does a declared generator claim, and is each one what its
template literally emits?* This session paid an LLM to answer it by reading
templates and expanding them by hand. This module answers it deterministically:

* `generators.declared_outputs` finds every declaration (EEx frontmatter, Tera
  frontmatter, `ggen.toml` rules);
* each committed literal target is checked against its template's mandatory
  literal text (`templates.literal_containment`) at three strengths, reporting
  the strongest that holds:

  - `RAW_RENDER_CONSISTENT` -- the always-emitted literals embed exactly;
  - `CONSISTENT_MODULO_WHITESPACE` -- they embed once whitespace is deleted on
    both sides (a formatter changed layout only);
  - `CONSISTENT_MODULO_WHITESPACE_AND_CALL_PARENS` -- also deleting `(` `)`
    (a formatter added call parentheses);
  - `INCONSISTENT` -- none holds: the output lacks template text beyond layout.

"Mandatory" is deliberate and is the audit's own claim ceiling: literals inside
`for`/`if` blocks may legitimately be emitted zero times, so they are not checked,
and a divergence confined to a block body is invisible here. The receipt says so.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .census import Census, read_blob
from .generators import declared_outputs
from .model import IECRefusal, content_id
from .reflexion import normalized_containment, strip_whitespace_and_call_parens
from .templates import eex_chunks, literal_containment, split_frontmatter, tera_chunks

__all__ = [
    "AUDIT_CLASSES",
    "AUDIT_VERSION",
    "audit_generated_outputs",
    "audit_source_digest",
]

AUDIT_VERSION = "1"
AUDIT_CLASSES = (
    "RAW_RENDER_CONSISTENT",
    "CONSISTENT_MODULO_WHITESPACE",
    "CONSISTENT_MODULO_WHITESPACE_AND_CALL_PARENS",
    "INCONSISTENT",
    "UNSUPPORTED_TEMPLATE",
)


def _chunks(template_path: str, text: str) -> list[Any]:
    if template_path.endswith(".eex"):
        _header, _unsupported, body = split_frontmatter(text)
        return eex_chunks(body)
    if text.startswith("---\n"):
        _header, _unsupported, text = split_frontmatter(text)
    return tera_chunks(text)


def _classify(chunks: list[Any], output: str) -> tuple[str, dict[str, Any]]:
    raw = literal_containment(chunks, output)
    if raw.holds:
        return "RAW_RENDER_CONSISTENT", {"raw": raw.to_json()}
    spaced = normalized_containment(
        chunks, output, lambda value: re.sub(r"\s", "", value)
    )
    if spaced.holds:
        return "CONSISTENT_MODULO_WHITESPACE", {"raw": raw.to_json()}
    parens = normalized_containment(chunks, output, strip_whitespace_and_call_parens)
    if parens.holds:
        return "CONSISTENT_MODULO_WHITESPACE_AND_CALL_PARENS", {"raw": raw.to_json()}
    return "INCONSISTENT", {"raw": raw.to_json(), "modulo_whitespace": spaced.to_json()}


def audit_generated_outputs(
    census: Census, checkout: Path, *, include: str = r".*"
) -> dict[str, Any]:
    """Audit every committed literal declared output whose path matches `include`."""
    subject = census.subject
    paths = {record.path for record in census.files}
    selector = re.compile(include)
    rows = []
    for output in declared_outputs(census, checkout):
        if not output.literal or not selector.search(output.target):
            continue
        row: dict[str, Any] = {
            "target": output.target,
            "declaration": output.declaration,
            "template": output.template,
            "rule": output.rule,
            "committed": output.target in paths,
        }
        if not row["committed"]:
            row["class"] = "NOT_COMMITTED"
            rows.append(row)
            continue
        try:
            template_text = read_blob(subject, checkout, output.template).decode(
                "utf-8"
            )
            chunks = _chunks(output.template, template_text)
            output_text = read_blob(subject, checkout, output.target).decode("utf-8")
            row["class"], row["evidence"] = _classify(chunks, output_text)
        except IECRefusal as refusal:
            row["class"] = "UNSUPPORTED_TEMPLATE"
            row["evidence"] = {"code": refusal.code, "detail": refusal.detail}
        rows.append(row)
    rows.sort(key=lambda item: (item["target"], item["declaration"]))
    body = {
        "schema": "autofde-lab.iec.generated-output-audit/1",
        "audit_version": AUDIT_VERSION,
        "subject": subject.uri,
        "include": include,
        "claim_ceiling": "mandatory (block-depth-0) template literals only; divergence "
        "confined to for/if block bodies is not observed by this audit",
        "rows": rows,
        "class_counts": _counts(rows),
    }
    return {**body, "id": content_id(body)}


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["class"]] = counts.get(row["class"], 0) + 1
    return dict(sorted(counts.items()))


def audit_source_digest() -> str:
    """Content digest of the modules that *are* the mechanized audit.

    Recorded before any held-out comparison, so a later edit to the mechanism is
    visible as a different digest rather than a silently re-fit answer.
    """
    root = Path(__file__).parent
    names = (
        "audit.py",
        "generators.py",
        "templates.py",
        "reflexion.py",
        "census.py",
        "decompile.py",
    )
    return content_id(
        {name: (root / name).read_text(encoding="utf-8") for name in names}
    )
