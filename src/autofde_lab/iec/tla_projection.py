"""Deterministic TLA+ projection from IEC transition-system IR.

This module renders formal artifacts. It does not invoke SANY, TLC, or TLAPS,
and therefore cannot claim model-check or proof standing. Execution lives in
:mod:`autofde_lab.iec.tlc_court`, which consumes these projections.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import digest
from .protocol_ir import TransitionSystem


@dataclass(frozen=True, slots=True)
class TlaProjection:
    module_name: str
    tla: str
    cfg: str
    source_system_id: str
    warnings: tuple[str, ...] = ()

    @property
    def projection_id(self) -> str:
        return digest(self)


def _action(system: TransitionSystem, name: str) -> str:
    action = next(item for item in system.actions if item.name == name)
    lines = [f"{action.name} ==", f"    /\\ {action.guard}"]
    update_names = {key for key, _ in action.updates}
    for variable, expression in action.updates:
        lines.append(f"    /\\ {variable}' = {expression}")
    unchanged = set(action.unchanged)
    for variable in system.variable_names:
        if variable not in update_names and variable not in unchanged:
            unchanged.add(variable)
    if unchanged:
        ordered = ", ".join(sorted(unchanged))
        lines.append(f"    /\\ UNCHANGED <<{ordered}>>")
    return "\n".join(lines)


def render_tla(system: TransitionSystem) -> TlaProjection:
    variables = ", ".join(system.variable_names)
    constants = ", ".join(system.constants)

    parts: list[str] = [
        f"---- MODULE {system.name} ----",
        "EXTENDS Naturals, Sequences, FiniteSets",
        "",
    ]
    if constants:
        parts.extend([f"CONSTANTS {constants}", ""])
    parts.extend([f"VARIABLES {variables}", ""])

    init_lines = ["Init =="]
    for variable in system.variables:
        init_lines.append(f"    /\\ {variable.name} = {variable.initial}")
    parts.extend(init_lines)
    parts.append("")

    for action in system.actions:
        parts.append(_action(system, action.name))
        parts.append("")

    parts.append("Next ==")
    for index, action in enumerate(system.actions):
        prefix = "    \\/" if index == 0 else "    \\/"
        parts.append(f"{prefix} {action.name}")
    parts.append("")

    parts.extend([f"vars == <<{variables}>>", ""])
    spec = "Spec == Init /\\ [][Next]_vars"
    for item in system.fairness:
        spec += f" /\\ {item.kind}_vars({item.target})"
    parts.extend([spec, ""])

    for invariant in system.invariants:
        parts.extend(
            [
                f"{invariant.name} ==",
                f"    {invariant.expression}",
                "",
            ]
        )
    for liveness in system.liveness:
        parts.extend(
            [
                f"{liveness.name} ==",
                f"    {liveness.expression}",
                "",
            ]
        )
    for constraint in system.state_constraints:
        parts.extend(
            [
                f"{constraint.name} ==",
                f"    {constraint.expression}",
                "",
            ]
        )
    parts.append("====")

    warnings: list[str] = []
    if system.liveness and not system.fairness:
        warnings.append("LIVENESS_WITHOUT_FAIRNESS")

    return TlaProjection(
        module_name=system.name,
        tla="\n".join(parts) + "\n",
        cfg=render_cfg(system),
        source_system_id=system.system_id,
        warnings=tuple(warnings),
    )


def render_cfg(
    system: TransitionSystem,
    *,
    invariants: tuple[str, ...] | None = None,
    properties: tuple[str, ...] | None = None,
) -> str:
    """Render a TLC configuration.

    ``invariants``/``properties`` default to every declared one. Passing an
    explicit subset yields a per-property cfg: TLC stops at the first
    violation, so a single combined run would leave later properties UNKNOWN.
    """

    known_invariants = tuple(item.name for item in system.invariants)
    known_properties = tuple(item.name for item in system.liveness)
    chosen_invariants = known_invariants if invariants is None else tuple(invariants)
    chosen_properties = known_properties if properties is None else tuple(properties)
    for name in chosen_invariants:
        if name not in known_invariants:
            raise ValueError(f"unknown invariant {name}")
    for name in chosen_properties:
        if name not in known_properties:
            raise ValueError(f"unknown property {name}")

    cfg_lines = ["SPECIFICATION Spec"]
    for name, value in system.constant_values:
        cfg_lines.append(f"CONSTANT {name} = {value}")
    for constraint in system.state_constraints:
        cfg_lines.append(f"CONSTRAINT {constraint.name}")
    for name in chosen_invariants:
        cfg_lines.append(f"INVARIANT {name}")
    for name in chosen_properties:
        cfg_lines.append(f"PROPERTY {name}")
    return "\n".join(cfg_lines) + "\n"
