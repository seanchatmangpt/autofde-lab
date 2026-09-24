"""Decompile a committed output into (residue template, kernel bindings) and back.

`R_old --extract--> K_R --manufacture--> R_new` (ARD section O4), for outputs whose
producer exposes its kernel as rows (`kernel.PackKernel`).

Three pieces:

* `find_bindings` locates every occurrence of a kernel or declaration value in the
  output, longest value first, non-overlapping, respecting identifier boundaries.
  An occurrence whose value is shared by several sources is kept *ambiguous* --
  all sources are recorded, none is chosen -- because nothing in one output can
  say which one the producer read.
* `RowProgram` handles an output that repeats one line per kernel row: it pairs
  lines to rows, anti-unifies the paired lines into a row template, maps each
  hole to the one kernel variable that explains it on every training line, and
  records every row-ordering hypothesis the data leaves open.
* `leave_one_out` is the held-out court for a row program: the row template is
  learned without row k, and must predict row k from kernel facts alone.

Regeneration from a program never reads the original output. It reads the
residue template and the kernel; whether that reproduces the original is the
court's question, not this module's assumption.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .antiunify import Generalization, Hole, Node, Term, anti_unify, tokenize
from .model import IECRefusal

__all__ = [
    "Binding",
    "FlatProgram",
    "RowProgram",
    "family_leave_one_out",
    "fill",
    "find_bindings",
    "flat_program",
    "leave_one_out",
    "row_program",
]

_WORD = re.compile(r"\w", re.UNICODE)


@dataclass(frozen=True)
class Binding:
    start: int
    end: int
    value: str
    sources: tuple[str, ...]

    @property
    def ambiguous(self) -> bool:
        return len(self.sources) > 1

    def to_json(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "value": self.value,
            "sources": list(self.sources),
            "ambiguous": self.ambiguous,
        }


def _bounded(text: str, start: int, end: int) -> bool:
    if start > 0 and _WORD.match(text[start]) and _WORD.match(text[start - 1]):
        return False
    if end < len(text) and _WORD.match(text[end - 1]) and _WORD.match(text[end]):
        return False
    return True


def find_bindings(
    text: str, facts: Mapping[str, str], *, min_length: int = 2
) -> list[Binding]:
    by_value: dict[str, list[str]] = {}
    for source, value in facts.items():
        if len(value) >= min_length:
            by_value.setdefault(value, []).append(source)
    taken = bytearray(len(text))
    found: list[Binding] = []
    for value in sorted(by_value, key=lambda item: (-len(item), item)):
        cursor = 0
        while True:
            start = text.find(value, cursor)
            if start < 0:
                break
            end = start + len(value)
            if _bounded(text, start, end) and not any(taken[start:end]):
                taken[start:end] = b"\1" * (end - start)
                found.append(Binding(start, end, value, tuple(sorted(by_value[value]))))
            cursor = start + 1
    return sorted(found, key=lambda binding: binding.start)


@dataclass(frozen=True)
class FlatProgram:
    """Residue text with holes at kernel-value occurrences."""

    segments: tuple[str | Binding, ...]

    @property
    def bindings(self) -> list[Binding]:
        return [segment for segment in self.segments if isinstance(segment, Binding)]

    def regenerate(self, facts: Mapping[str, str]) -> str:
        out: list[str] = []
        for segment in self.segments:
            if isinstance(segment, str):
                out.append(segment)
                continue
            values = {facts[source] for source in segment.sources if source in facts}
            if len(values) != 1:
                raise IECRefusal(
                    "UNKNOWN_EQUIVALENCE",
                    f"hole at {segment.start} has sources {segment.sources} with values {sorted(values)}",
                )
            out.append(values.pop())
        return "".join(out)

    def coverage(self) -> dict[str, int]:
        bound = sum(binding.end - binding.start for binding in self.bindings)
        residue = sum(
            len(segment) for segment in self.segments if isinstance(segment, str)
        )
        return {
            "bytes_total": bound + residue,
            "bytes_bound_to_facts": bound,
            "bytes_residue": residue,
            "holes": len(self.bindings),
            "ambiguous_holes": sum(1 for binding in self.bindings if binding.ambiguous),
        }


def flat_program(text: str, facts: Mapping[str, str]) -> FlatProgram:
    segments: list[str | Binding] = []
    cursor = 0
    for binding in find_bindings(text, facts):
        if binding.start > cursor:
            segments.append(text[cursor : binding.start])
        segments.append(binding)
        cursor = binding.end
    if cursor < len(text):
        segments.append(text[cursor:])
    return FlatProgram(tuple(segments))


def fill(template: Term, values: Mapping[int, str]) -> str:
    """Render `template` with each hole replaced by a kernel value string."""
    if isinstance(template, str):
        return template
    if isinstance(template, Hole):
        return values[template.index]
    return "".join(fill(child, values) for child in template.children)


def _pair_lines(
    lines: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> list[int | None]:
    """For each line, the unique row with the most of its values present, else None."""
    pairs: list[int | None] = []
    for line in lines:
        scores = []
        for row in rows:
            score = 0
            for value in row.values():
                start = line.find(value)
                if (
                    len(value) >= 2
                    and start >= 0
                    and _bounded(line, start, start + len(value))
                ):
                    score += 1
            scores.append(score)
        best = max(scores) if scores else 0
        pairs.append(
            scores.index(best) if best >= 2 and scores.count(best) == 1 else None
        )
    return pairs


def _line_term(line: str, row: Mapping[str, str]) -> Term:
    """Tokenize `line` so each occurrence of one of `row`'s values is one token."""
    spans = [(b.start, b.end) for b in find_bindings(line, dict(row))]
    return tokenize(line, spans)


def _map_holes(
    generalization: Generalization, rows: Sequence[Mapping[str, str]]
) -> dict[int, list[str]]:
    """Hole -> every kernel variable that equals the hole's binding on every member."""
    mapping: dict[int, list[str]] = {}
    variables = sorted(set().union(*(row.keys() for row in rows)))
    for hole in generalization.holes:
        mapping[hole.index] = [
            var
            for var in variables
            if all(
                generalization.binding_text(member, hole.index) == rows[member].get(var)
                for member in range(len(rows))
            )
        ]
    return mapping


def _constant_literals(
    template: Term, rows: Sequence[Mapping[str, str]]
) -> list[dict[str, str]]:
    """Literal tokens that equal a kernel variable constant across every member row."""
    constants = {}
    for var in sorted(set().union(*(row.keys() for row in rows))):
        values = {row.get(var) for row in rows}
        if len(values) == 1 and None not in values:
            constants[var] = values.pop()
    text = fill(template, {hole.index: "" for hole in _all_holes(template)})
    return [
        {"variable": var, "value": value}
        for var, value in constants.items()
        if len(value) >= 2 and value in text
    ]


def _all_holes(template: Term) -> list[Hole]:
    if isinstance(template, Hole):
        return [template]
    if isinstance(template, Node):
        return [hole for child in template.children for hole in _all_holes(child)]
    return []


@dataclass(frozen=True)
class RowProgram:
    binding: str
    prefix: str
    suffix: str
    row_template: Term
    hole_variables: dict[int, list[str]]
    order_hypotheses: tuple[str, ...]
    constant_literals: tuple[dict[str, str], ...]
    paired_rows: tuple[int, ...]
    compression: dict[str, Any] = field(default_factory=dict)

    def regenerate(
        self, rows: Sequence[Mapping[str, str]], *, order: str | None = None
    ) -> str:
        order = order or (self.order_hypotheses[0] if self.order_hypotheses else None)
        if order is None:
            raise IECRefusal("UNKNOWN_EQUIVALENCE", "no row-order hypothesis survived")
        unresolved = [hole for hole, vars_ in self.hole_variables.items() if not vars_]
        if unresolved:
            raise IECRefusal(
                "COUNTEREXAMPLE_EQUIVALENCE",
                f"row-template holes {unresolved} are explained by no kernel variable",
            )
        ordered = sorted(rows, key=lambda row: row.get(order, ""))
        body = "".join(
            fill(
                self.row_template,
                {hole: row[vars_[0]] for hole, vars_ in self.hole_variables.items()},
            )
            for row in ordered
        )
        return self.prefix + body + self.suffix

    def to_json(self) -> dict[str, Any]:
        from .antiunify import template_text

        return {
            "binding": self.binding,
            "prefix_bytes": len(self.prefix),
            "suffix_bytes": len(self.suffix),
            "row_template": template_text(self.row_template),
            "hole_variables": {
                f"X{hole}": vars_ for hole, vars_ in self.hole_variables.items()
            },
            "ambiguous_holes": [
                f"X{hole}"
                for hole, vars_ in self.hole_variables.items()
                if len(vars_) > 1
            ],
            "order_hypotheses": list(self.order_hypotheses),
            "constant_literals": list(self.constant_literals),
            "paired_rows": list(self.paired_rows),
            "compression": self.compression,
        }


def row_program(
    text: str, binding: str, rows: Sequence[Mapping[str, str]]
) -> RowProgram:
    """Recover `prefix + [row_template(r) for r in sorted(rows)] + suffix`."""
    if len(rows) < 2:
        raise IECRefusal(
            "UNSUPPORTED_GENERATOR_CAPABILITY",
            f"{binding}: {len(rows)} row(s) cannot separate template from kernel",
        )
    lines = text.splitlines(keepends=True)
    pairs = _pair_lines(lines, rows)
    positions = [index for index, pair in enumerate(pairs) if pair is not None]
    if not positions:
        raise IECRefusal(
            "UNSUPPORTED_GENERATOR_CAPABILITY", f"{binding}: no line pairs to a row"
        )
    first, last = positions[0], positions[-1]
    block = pairs[first : last + 1]
    if None in block or sorted(block) != list(range(len(rows))):
        raise IECRefusal(
            "UNSUPPORTED_GENERATOR_CAPABILITY",
            f"{binding}: paired lines are not one contiguous line per row ({block})",
        )
    member_rows = [rows[pair] for pair in block]
    generalization = anti_unify(
        [
            _line_term(line, row)
            for line, row in zip(lines[first : last + 1], member_rows)
        ]
    )
    template = generalization.template
    hole_variables = _map_holes(generalization, member_rows)
    observed = [dict(row) for row in member_rows]
    variables = sorted(set().union(*(row.keys() for row in rows)))
    order_hypotheses = tuple(
        var
        for var in variables
        if sorted(observed, key=lambda row: row.get(var, "")) == observed
        and len({row.get(var) for row in observed}) == len(observed)
    )
    return RowProgram(
        binding=binding,
        prefix="".join(lines[:first]),
        suffix="".join(lines[last + 1 :]),
        row_template=template,
        hole_variables=hole_variables,
        order_hypotheses=order_hypotheses,
        constant_literals=tuple(_constant_literals(template, member_rows)),
        paired_rows=tuple(block),
        compression=generalization.compression(),
    )


def family_leave_one_out(
    texts: Sequence[str], facts: Sequence[Mapping[str, str]]
) -> list[dict[str, Any]]:
    """Cross-file held-out court: learn a template from all members but one.

    Member `k`'s text must be predicted from the template learned on the others
    plus member `k`'s own facts -- never from member `k`'s text. This is the
    generalization-versus-memorization separation ARD section 26 asks of a kernel.
    """
    if len(texts) != len(facts) or len(texts) < 3:
        raise IECRefusal(
            "UNSUPPORTED_GENERATOR_CAPABILITY",
            "a family held-out court needs >= 3 members, each with its facts",
        )
    results = []
    for held in range(len(texts)):
        training = [index for index in range(len(texts)) if index != held]
        generalization = anti_unify([_line_term(texts[i], facts[i]) for i in training])
        mapping = _map_holes(generalization, [facts[i] for i in training])
        record: dict[str, Any] = {
            "held_out_member": held,
            "hole_facts": {f"X{hole}": keys for hole, keys in mapping.items()},
        }
        unexplained = [hole for hole, keys in mapping.items() if not keys]
        if unexplained:
            record.update(
                verdict="UNSUPPORTED",
                detail=f"holes {unexplained} are explained by no fact of the training members",
            )
        else:
            predicted = fill(
                generalization.template,
                {hole: facts[held].get(keys[0], "") for hole, keys in mapping.items()},
            )
            record.update(
                verdict="PASS" if predicted == texts[held] else "COUNTEREXAMPLE",
                predicted=predicted,
                actual=texts[held],
            )
        results.append(record)
    return results


def leave_one_out(
    text: str, binding: str, rows: Sequence[Mapping[str, str]]
) -> list[dict[str, Any]]:
    """Predict each row line from a row template learned without it."""
    program = row_program(text, binding, rows)
    lines = text.splitlines(keepends=True)
    start = len(program.prefix.splitlines(keepends=True))
    block_lines = lines[start : start + len(program.paired_rows)]
    results = []
    for held in range(len(block_lines)):
        training = [i for i in range(len(block_lines)) if i != held]
        training_rows = [rows[program.paired_rows[i]] for i in training]
        held_row = rows[program.paired_rows[held]]
        record: dict[str, Any] = {
            "held_out_line": start + held + 1,
            "row": dict(held_row),
        }
        if len(training) < 1:
            record.update(verdict="UNSUPPORTED", detail="no training rows")
            results.append(record)
            continue
        generalization = anti_unify(
            [_line_term(block_lines[i], rows[program.paired_rows[i]]) for i in training]
        )
        mapping = _map_holes(generalization, training_rows)
        unexplained = [hole for hole, vars_ in mapping.items() if not vars_]
        if unexplained:
            record.update(
                verdict="UNSUPPORTED",
                detail=f"holes {unexplained} explained by no kernel variable",
            )
            results.append(record)
            continue
        predicted = fill(
            generalization.template,
            {hole: held_row.get(vars_[0], "") for hole, vars_ in mapping.items()},
        )
        actual = block_lines[held]
        record.update(
            verdict="PASS" if predicted == actual else "COUNTEREXAMPLE",
            predicted=predicted,
            actual=actual,
            hole_variables={f"X{hole}": vars_ for hole, vars_ in mapping.items()},
            constants_memorized=_constant_literals(
                generalization.template, training_rows
            ),
        )
        results.append(record)
    return results
