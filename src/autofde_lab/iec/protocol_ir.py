"""Language-neutral transition-system IR for protocol recovery and projection.

The IR represents state variables, actions, invariants, and liveness
obligations. It is a specification artifact only and has no execution
authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

from .model import digest

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def require_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class StateVariable:
    name: str
    initial: str
    domain: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_identifier(self.name, "state variable")
        if not self.initial.strip():
            raise ValueError("state variable initial expression must be non-empty")


@dataclass(frozen=True, slots=True)
class TransitionAction:
    name: str
    guard: str
    updates: tuple[tuple[str, str], ...]
    unchanged: tuple[str, ...] = ()
    consequence: bool = False
    authority_required: bool = False

    def __post_init__(self) -> None:
        require_identifier(self.name, "action")
        if not self.guard.strip():
            raise ValueError("action guard must be non-empty")
        update_names = [name for name, _ in self.updates]
        if len(update_names) != len(set(update_names)):
            raise ValueError("action updates variable more than once")


@dataclass(frozen=True, slots=True)
class Invariant:
    name: str
    expression: str

    def __post_init__(self) -> None:
        require_identifier(self.name, "invariant")
        if not self.expression.strip():
            raise ValueError("invariant expression must be non-empty")


@dataclass(frozen=True, slots=True)
class LivenessProperty:
    name: str
    expression: str

    def __post_init__(self) -> None:
        require_identifier(self.name, "liveness property")
        if not self.expression.strip():
            raise ValueError("liveness expression must be non-empty")


@dataclass(frozen=True, slots=True)
class TransitionSystem:
    name: str
    variables: tuple[StateVariable, ...]
    actions: tuple[TransitionAction, ...]
    invariants: tuple[Invariant, ...]
    liveness: tuple[LivenessProperty, ...] = ()
    constants: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_identifier(self.name, "transition-system name")
        variable_names = [variable.name for variable in self.variables]
        if not variable_names:
            raise ValueError("transition system requires at least one variable")
        if len(variable_names) != len(set(variable_names)):
            raise ValueError("duplicate state variable")
        action_names = [action.name for action in self.actions]
        if not action_names:
            raise ValueError("transition system requires at least one action")
        if len(action_names) != len(set(action_names)):
            raise ValueError("duplicate action")
        known = set(variable_names)
        for action in self.actions:
            touched = {name for name, _ in action.updates} | set(action.unchanged)
            unknown = touched - known
            if unknown:
                raise ValueError(
                    f"action {action.name} references unknown variables: {sorted(unknown)}"
                )
            overlap = {name for name, _ in action.updates} & set(action.unchanged)
            if overlap:
                raise ValueError(
                    f"action {action.name} updates and marks unchanged: {sorted(overlap)}"
                )
        invariant_names = [invariant.name for invariant in self.invariants]
        if len(invariant_names) != len(set(invariant_names)):
            raise ValueError("duplicate invariant")
        liveness_names = [item.name for item in self.liveness]
        if len(liveness_names) != len(set(liveness_names)):
            raise ValueError("duplicate liveness property")

    @property
    def system_id(self) -> str:
        return digest(self)

    @property
    def variable_names(self) -> tuple[str, ...]:
        return tuple(variable.name for variable in self.variables)

    def consequence_actions(self) -> tuple[TransitionAction, ...]:
        return tuple(action for action in self.actions if action.consequence)

    def authority_gaps(self) -> tuple[str, ...]:
        """Find declared consequence actions lacking an authority requirement."""

        return tuple(
            action.name
            for action in self.actions
            if action.consequence and not action.authority_required
        )


def make_action(
    name: str,
    *,
    guard: str,
    updates: Mapping[str, str] | None = None,
    unchanged: Iterable[str] = (),
    consequence: bool = False,
    authority_required: bool = False,
) -> TransitionAction:
    return TransitionAction(
        name=name,
        guard=guard,
        updates=tuple(sorted((updates or {}).items())),
        unchanged=tuple(sorted(set(unchanged))),
        consequence=consequence,
        authority_required=authority_required,
    )
