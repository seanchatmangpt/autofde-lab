"""Bounded anti-unification for JSON-like semantic structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .model import digest


@dataclass(frozen=True, slots=True)
class Variable:
    name: str


@dataclass(frozen=True, slots=True)
class Generalization:
    template: Any
    substitutions: tuple[dict[str, Any], ...]
    member_ids: tuple[str, ...]

    @property
    def generalization_id(self) -> str:
        return digest(
            {
                "template": _json_term(self.template),
                "substitutions": self.substitutions,
                "member_ids": self.member_ids,
            }
        )

    def reconstruct(self, index: int) -> Any:
        return substitute(self.template, self.substitutions[index])


def _json_term(value: Any) -> Any:
    if isinstance(value, Variable):
        return {"$var": value.name}
    if isinstance(value, dict):
        return {key: _json_term(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_json_term(item) for item in value]
    if isinstance(value, list):
        return [_json_term(item) for item in value]
    return value


def substitute(term: Any, bindings: Mapping[str, Any]) -> Any:
    if isinstance(term, Variable):
        return bindings[term.name]
    if isinstance(term, dict):
        return {key: substitute(value, bindings) for key, value in term.items()}
    if isinstance(term, tuple):
        return tuple(substitute(value, bindings) for value in term)
    if isinstance(term, list):
        return [substitute(value, bindings) for value in term]
    return term


class AntiUnifier:
    """Generalize equal-shape structures and preserve reconstruction witnesses."""

    def generalize(
        self, members: Sequence[Any], *, member_ids: Sequence[str] | None = None
    ) -> Generalization:
        if len(members) < 2:
            raise ValueError("anti-unification requires at least two members")
        ids = tuple(member_ids or [f"member-{i}" for i in range(len(members))])
        if len(ids) != len(members):
            raise ValueError("member_ids length must equal members length")
        if len(set(ids)) != len(ids):
            raise ValueError("member identities must be unique")

        substitutions: list[dict[str, Any]] = [dict() for _ in members]
        counter = [0]
        template = self._generalize_node(tuple(members), substitutions, counter)
        result = Generalization(template, tuple(substitutions), ids)

        for index, original in enumerate(members):
            if result.reconstruct(index) != original:
                raise AssertionError(
                    f"anti-unification reconstruction failed for {ids[index]}"
                )
        return result

    def _variable(
        self,
        values: tuple[Any, ...],
        substitutions: list[dict[str, Any]],
        counter: list[int],
    ) -> Variable:
        name = f"V{counter[0]}"
        counter[0] += 1
        for index, value in enumerate(values):
            substitutions[index][name] = value
        return Variable(name)

    def _generalize_node(
        self,
        values: tuple[Any, ...],
        substitutions: list[dict[str, Any]],
        counter: list[int],
    ) -> Any:
        first = values[0]
        if all(value == first for value in values[1:]):
            return first

        if all(isinstance(value, dict) for value in values):
            key_sets = [set(value) for value in values]
            if all(keys == key_sets[0] for keys in key_sets[1:]):
                return {
                    key: self._generalize_node(
                        tuple(value[key] for value in values), substitutions, counter
                    )
                    for key in sorted(key_sets[0])
                }
            return self._variable(values, substitutions, counter)

        if all(isinstance(value, tuple) for value in values):
            lengths = {len(value) for value in values}
            if len(lengths) == 1:
                return tuple(
                    self._generalize_node(
                        tuple(value[index] for value in values), substitutions, counter
                    )
                    for index in range(len(first))
                )
            return self._variable(values, substitutions, counter)

        if all(isinstance(value, list) for value in values):
            lengths = {len(value) for value in values}
            if len(lengths) == 1:
                return [
                    self._generalize_node(
                        tuple(value[index] for value in values), substitutions, counter
                    )
                    for index in range(len(first))
                ]
            return self._variable(values, substitutions, counter)

        return self._variable(values, substitutions, counter)
