"""Reflexion model: the declared generator vs. what the committed output shows.

Software reflexion models (Murphy, Notkin, Sullivan, IEEE TSE 27(4), 2001) compare a
proposed high-level model against recovered source structure and keep the
disagreement as evidence instead of presuming either side correct. Here the two
sides are

* the *declared* generator -- a template's literal chunks and output tags,
  parsed by `templates.eex_chunks`, never evaluated;
* the *recovered* structure -- where kernel and declaration values occur in the
  committed output (`decompile.find_bindings`).

Each finding is typed and carries its own falsifier. None is admitted by this
module; they are hypotheses for the frontier.

* `CONVERGENT_HOLE` -- a fact value sits where the template has an output tag.
* `LITERAL_RESTATES_DECLARATION` -- a declaration fact (the template's own `to:`
  path, the pack name, the ontology path) is spelled out as template literal
  text. Two places now state one fact; renaming the target updates one of them.
* `LITERAL_MATCHES_KERNEL_VALUE` -- template literal text equals a kernel value.
  Either the template hard-codes a domain fact, or the overlap is coincidental
  prose; one output cannot tell which, so it stays a candidate.
* `COMPUTED_HOLE` -- an output tag emitted text that equals no fact: the
  template computes it (`<%= inspect(x) %>`, a string transform). The kernel
  alone does not determine the output there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

from .decompile import find_bindings
from .templates import Chunk, Containment, chunk_depths, literal_containment

__all__ = [
    "Finding",
    "analyze",
    "normalized_containment",
    "strip_whitespace_and_call_parens",
]


@dataclass(frozen=True)
class Finding:
    kind: str
    value: str
    span: tuple[int, int]
    sources: tuple[str, ...]
    falsifier: str
    template_expression: str = ""

    def to_json(self) -> dict[str, Any]:
        record = {
            "kind": self.kind,
            "value": self.value,
            "span": list(self.span),
            "sources": list(self.sources),
            "falsifier": self.falsifier,
        }
        if self.template_expression:
            record["template_expression"] = self.template_expression
        return record


def _inside(span: tuple[int, int], regions: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= span[0] and span[1] <= end for start, end in regions)


def analyze(
    chunks: list[Chunk], output: str, facts: Mapping[str, str]
) -> dict[str, Any]:
    containment = literal_containment(chunks, output)
    findings: list[Finding] = []
    literal_regions = containment.literal_spans if containment.holds else ()
    for binding in find_bindings(output, facts):
        span = (binding.start, binding.end)
        declaration = all(
            source.startswith("declaration:") for source in binding.sources
        )
        if containment.holds and _inside(span, literal_regions):
            if declaration:
                findings.append(
                    Finding(
                        "LITERAL_RESTATES_DECLARATION",
                        binding.value,
                        span,
                        binding.sources,
                        "change the declaration value and re-render: the literal copy does not follow",
                    )
                )
            else:
                findings.append(
                    Finding(
                        "LITERAL_MATCHES_KERNEL_VALUE",
                        binding.value,
                        span,
                        binding.sources,
                        "vary the kernel value: if the literal stays, the overlap was coincidental",
                    )
                )
        elif containment.holds:
            findings.append(
                Finding(
                    "CONVERGENT_HOLE",
                    binding.value,
                    span,
                    binding.sources,
                    "vary the kernel value: the output must change exactly here",
                )
            )
    findings.extend(_computed_holes(chunks, output, facts, containment))
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.kind] = counts.get(finding.kind, 0) + 1
    return {
        "containment": containment.to_json(),
        "finding_counts": dict(sorted(counts.items())),
        "findings": [finding.to_json() for finding in findings],
    }


def _computed_holes(
    chunks: list[Chunk], output: str, facts: Mapping[str, str], containment: Containment
) -> list[Finding]:
    """Attribute each output-tag gap to its expression, where attribution is unique."""
    if not containment.holds:
        return []
    values = set(facts.values())
    findings: list[Finding] = []
    literal_index = -1
    between: list[tuple[Chunk, int]] = []
    spans = containment.literal_spans
    for chunk, depth in zip(chunks, chunk_depths(chunks)):
        if chunk.kind != "literal" or depth > 0:
            between.append((chunk, depth))
            continue
        literal_index += 1
        if literal_index > 0:
            gap = (spans[literal_index - 1][1], spans[literal_index][0])
            outputs = [item for item, _ in between if item.kind == "output"]
            blocked = any(
                depth_between > 0 or bool(item.block)
                for item, depth_between in between
                if item.kind != "comment"
            )
            if len(outputs) == 1 and not blocked and gap[1] > gap[0]:
                text = output[gap[0] : gap[1]]
                if text not in values:
                    findings.append(
                        Finding(
                            "COMPUTED_HOLE",
                            text,
                            gap,
                            (),
                            "add the computed value to the kernel: the hole becomes convergent",
                            outputs[0].text,
                        )
                    )
        between = []
    return findings


def strip_whitespace_and_call_parens(text: str) -> str:
    """A named, lossy normalization: delete whitespace and `(` `)` characters.

    It identifies the textual differences Elixir's `Code.format_string!/1`
    introduces for call syntax and layout (`input :email` vs `input(:email)`),
    and nothing it identifies is claimed to be semantically equal beyond that.
    """
    return re.sub(r"[\s()]", "", text)


def normalized_containment(
    chunks: list[Chunk], output: str, normalize: Callable[[str], str]
) -> Containment:
    """`literal_containment` after applying `normalize` to both sides."""
    normalized = [
        replace(chunk, text=normalize(chunk.text)) if chunk.kind == "literal" else chunk
        for chunk in chunks
    ]
    kept = [chunk for chunk in normalized if chunk.kind != "literal" or chunk.text]
    return literal_containment(kept, normalize(output))
