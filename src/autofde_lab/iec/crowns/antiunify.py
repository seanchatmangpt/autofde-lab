"""IEC-006: n-ary anti-unification with hedge holes (PR-006, ARD A5).

Given members `x_1..x_n`, `anti_unify` returns a generalization `g` and one
substitution per member such that `apply(g, sigma_i) == x_i`
(`AntiUnify(x_1..x_n) -> (g, sigma_1..sigma_n)` in ARD section 10).

Two kinds of hole exist:

* a *term* hole stands for one subterm (Plotkin/Reynolds first-order LGG);
* a *hedge* hole stands for a run of zero or more siblings, used where members
  have different numbers of children at an aligned position.

Identical differences share a hole: if two positions differ in exactly the same
way across every member, they get the same hole index. That is the property that
turns "the same name appears twice" into one parameter instead of two.

Soundness is checked, not assumed. The alignment of sibling runs uses
`difflib.SequenceMatcher` pairwise across members, which is a heuristic, so the
result is not guaranteed to be *least* general. It is guaranteed to reconstruct,
because `Generalization.verify()` re-applies every substitution and compares
terms exactly; a generalization that fails that check is never returned.

Text enters as `tokenize(text)`: a document node of line nodes of word, space,
and punctuation tokens whose concatenation is the original text byte-for-byte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping, Sequence, Union

from .model import IECRefusal

__all__ = [
    "COST_FUNCTION",
    "Generalization",
    "Hole",
    "Node",
    "Term",
    "anti_unify",
    "apply",
    "cost",
    "render",
    "template_text",
    "tokenize",
]

COST_FUNCTION = (
    "iec.cost/1: literal characters + 1 per hole + 1 per substitution binding"
)


@dataclass(frozen=True)
class Node:
    label: str
    children: tuple["Term", ...]


@dataclass(frozen=True)
class Hole:
    index: int
    hedge: bool = False


Term = Union[str, Node, Hole]
Binding = Union[str, Node, tuple]  # a term, or for a hedge hole a tuple of terms

_TOKEN = re.compile(r"\w+|\s+|[^\w\s]", re.UNICODE)


def tokenize(text: str, atoms: Sequence[tuple[int, int]] = ()) -> Node:
    """Document -> lines -> tokens; `render(tokenize(t)) == t` for every `t`.

    `atoms` are `(start, end)` character spans that must each become one token --
    e.g. the occurrences of kernel values, so that a generalization's holes line
    up with whole values instead of the words inside them. An atom may not cross
    a line break.
    """
    boundaries = sorted(atoms)
    lines = []
    offset = 0
    for line in text.splitlines(keepends=True):
        end_of_line = offset + len(line)
        tokens: list[str] = []
        cursor = offset
        for start, end in boundaries:
            if end <= offset or start >= end_of_line:
                continue
            if start < cursor or end > end_of_line or start >= end:
                raise IECRefusal(
                    "UNSUPPORTED_GENERATOR_CAPABILITY", f"atom {start}:{end} overlaps"
                )
            tokens.extend(_TOKEN.findall(text[cursor:start]))
            tokens.append(text[start:end])
            cursor = end
        tokens.extend(_TOKEN.findall(text[cursor:end_of_line]))
        lines.append(Node("line", tuple(tokens)))
        offset = end_of_line
    return Node("doc", tuple(lines))


def render(term: Term) -> str:
    if isinstance(term, str):
        return term
    if isinstance(term, Hole):
        raise IECRefusal(
            "UNKNOWN_EQUIVALENCE", f"cannot render unfilled hole X{term.index}"
        )
    return "".join(render(child) for child in term.children)


def apply(term: Term, substitution: Mapping[int, Binding]) -> Term:
    """Instantiate every hole in `term` from `substitution`."""
    if isinstance(term, str):
        return term
    if isinstance(term, Hole):
        if term.hedge:
            raise IECRefusal(
                "UNKNOWN_EQUIVALENCE", f"hedge hole X{term.index} outside a node"
            )
        return substitution[term.index]
    children: list[Term] = []
    for child in term.children:
        if isinstance(child, Hole) and child.hedge:
            children.extend(substitution[child.index])
        else:
            children.append(apply(child, substitution))
    return Node(term.label, tuple(children))


def _leaf_chars(term: Term) -> int:
    if isinstance(term, str):
        return len(term)
    if isinstance(term, Hole):
        return 0
    return sum(_leaf_chars(child) for child in term.children)


def _holes(term: Term) -> Iterable[Hole]:
    if isinstance(term, Hole):
        yield term
    elif isinstance(term, Node):
        for child in term.children:
            yield from _holes(child)


def _binding_chars(binding: Binding) -> int:
    if isinstance(binding, tuple):
        return sum(_leaf_chars(item) for item in binding)
    return _leaf_chars(binding)


def cost(template: Term, substitutions: Sequence[Mapping[int, Binding]] = ()) -> int:
    """`COST_FUNCTION`, versioned so dominance claims (ARD section 20) are comparable."""
    total = _leaf_chars(template) + len(set(_holes(template)))
    for substitution in substitutions:
        total += sum(_binding_chars(value) + 1 for value in substitution.values())
    return total


def template_text(
    template: Term, *, open_mark: str = "{{", close_mark: str = "}}"
) -> str:
    """A human-readable rendering with ``open_mark Xn close_mark`` placeholders.

    A hedge hole renders as ``Xn...`` between the marks. (The default marks
    are double braces; they are named, not written, here because the
    VuePress reference build treats a literal double-brace pair in a
    docstring as a Vue template expression and ``Xn...`` does not parse.)
    """
    if isinstance(template, str):
        if open_mark in template or close_mark in template:
            raise IECRefusal(
                "UNSUPPORTED_GENERATOR_CAPABILITY",
                f"literal text contains placeholder mark {open_mark!r} or {close_mark!r}",
            )
        return template
    if isinstance(template, Hole):
        suffix = "..." if template.hedge else ""
        return f"{open_mark}X{template.index}{suffix}{close_mark}"
    return "".join(
        template_text(child, open_mark=open_mark, close_mark=close_mark)
        for child in template.children
    )


@dataclass(frozen=True)
class Generalization:
    template: Term
    substitutions: tuple[dict[int, Binding], ...]
    members: tuple[Term, ...]

    @property
    def holes(self) -> list[Hole]:
        return sorted(set(_holes(self.template)), key=lambda hole: hole.index)

    def verify(self) -> None:
        """Refuse unless every substitution reconstructs its member exactly."""
        for position, (member, substitution) in enumerate(
            zip(self.members, self.substitutions)
        ):
            if apply(self.template, substitution) != member:
                raise IECRefusal(
                    "COUNTEREXAMPLE_EQUIVALENCE",
                    f"generalization does not reconstruct member {position}",
                )

    def compression(self) -> dict[str, Any]:
        original = sum(_leaf_chars(member) for member in self.members)
        generalized = cost(self.template, self.substitutions)
        return {
            "cost_function": COST_FUNCTION,
            "original_cost": original,
            "generalized_cost": generalized,
            "ratio": round(original / generalized, 6) if generalized else None,
        }

    def binding_text(self, member: int, hole: int) -> str:
        value = self.substitutions[member][hole]
        if isinstance(value, tuple):
            return "".join(render(item) for item in value)
        return render(value)


class _AntiUnifier:
    def __init__(self, arity: int) -> None:
        self.arity = arity
        self.table: dict[tuple, Hole] = {}

    def hole(self, key: tuple, hedge: bool) -> Hole:
        found = self.table.get(key)
        if found is None:
            found = Hole(len(self.table), hedge)
            self.table[key] = found
        return found

    def term(self, terms: tuple[Term, ...]) -> Term:
        first = terms[0]
        if all(term == first for term in terms[1:]):
            return first
        if (
            all(isinstance(term, Node) for term in terms)
            and len({t.label for t in terms}) == 1
        ):
            return Node(first.label, tuple(self.children([t.children for t in terms])))
        return self.hole(("term", terms), hedge=False)

    def children(self, sequences: list[tuple[Term, ...]]) -> list[Term]:
        anchors = _align(sequences)
        out: list[Term] = []
        previous = tuple(-1 for _ in sequences)
        ends = tuple(len(sequence) for sequence in sequences)
        for position in [*anchors, ends]:
            gaps = tuple(
                tuple(sequence[previous[m] + 1 : position[m]])
                for m, sequence in enumerate(sequences)
            )
            if any(gaps):
                if len({len(gap) for gap in gaps}) == 1:
                    out.extend(self.term(column) for column in zip(*gaps))
                else:
                    out.append(self.hole(("hedge", gaps), hedge=True))
            if position is not ends:
                out.append(sequences[0][position[0]])
            previous = position
        return out

    def substitutions(self) -> tuple[dict[int, Binding], ...]:
        result: list[dict[int, Binding]] = [dict() for _ in range(self.arity)]
        for (kind, values), hole in self.table.items():
            for member in range(self.arity):
                result[member][hole.index] = values[member]
        return tuple(result)


def _align(sequences: list[tuple[Term, ...]]) -> list[tuple[int, ...]]:
    """Positions of elements equal across all members, strictly increasing in each."""
    values = list(sequences[0])
    positions: list[tuple[int, ...]] = [(index,) for index in range(len(values))]
    for other in sequences[1:]:
        matcher = SequenceMatcher(None, values, list(other), autojunk=False)
        kept_values, kept_positions = [], []
        for left, right, size in matcher.get_matching_blocks():
            for offset in range(size):
                kept_values.append(values[left + offset])
                kept_positions.append(positions[left + offset] + (right + offset,))
        values, positions = kept_values, kept_positions
    return positions


def anti_unify(members: Sequence[Term]) -> Generalization:
    """Generalize `members`; the result is verified to reconstruct every member."""
    if len(members) < 1:
        raise IECRefusal(
            "UNKNOWN_EQUIVALENCE", "anti-unification needs at least one member"
        )
    unifier = _AntiUnifier(len(members))
    template = unifier.term(tuple(members))
    generalization = Generalization(template, unifier.substitutions(), tuple(members))
    generalization.verify()
    return generalization
