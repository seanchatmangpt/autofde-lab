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


class UnboundConstantError(ValueError):
    """UNBOUND_CONSTANT: a declared CONSTANT has no model value.

    TLC cannot check a model whose constants are unassigned, so the IR refuses
    to construct one rather than emitting a cfg that fails at tool time.
    """

    code = "UNBOUND_CONSTANT"


@dataclass(frozen=True, slots=True)
class Fairness:
    """A fairness conjunct: ``WF_vars(A)`` or ``SF_vars(A)``.

    ``action=None`` means the whole next-state relation (``Next``).
    """

    kind: str = "WF"
    action: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("WF", "SF"):
            raise ValueError(f"fairness kind must be WF or SF, got {self.kind!r}")
        if self.action is not None:
            require_identifier(self.action, "fairness action")

    @property
    def target(self) -> str:
        return self.action or "Next"


@dataclass(frozen=True, slots=True)
class TransitionSystem:
    name: str
    variables: tuple[StateVariable, ...]
    actions: tuple[TransitionAction, ...]
    invariants: tuple[Invariant, ...]
    liveness: tuple[LivenessProperty, ...] = ()
    constants: tuple[str, ...] = ()
    fairness: tuple[Fairness, ...] = ()
    constant_values: tuple[tuple[str, str], ...] = ()
    state_constraints: tuple[Invariant, ...] = ()

    def __post_init__(self) -> None:
        require_identifier(self.name, "transition-system name")
        bound = {name for name, _ in self.constant_values}
        for name, value in self.constant_values:
            require_identifier(name, "constant")
            if not value.strip():
                raise UnboundConstantError(f"UNBOUND_CONSTANT: {name} has empty value")
        unknown_bound = bound - set(self.constants)
        if unknown_bound:
            raise ValueError(
                f"values bound to undeclared constants: {sorted(unknown_bound)}"
            )
        unbound = [name for name in self.constants if name not in bound]
        if unbound:
            raise UnboundConstantError(f"UNBOUND_CONSTANT: {unbound}")
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
        constraint_names = [item.name for item in self.state_constraints]
        if len(constraint_names) != len(set(constraint_names)):
            raise ValueError("duplicate state constraint")
        all_names = invariant_names + liveness_names + constraint_names + action_names
        if len(all_names) != len(set(all_names)):
            raise ValueError(
                "definition name collision between actions/properties/constraints"
            )
        for item in self.fairness:
            if item.action is not None and item.action not in action_names:
                raise ValueError(f"fairness names unknown action {item.action}")

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
