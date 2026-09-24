"""Deterministic TLA+ projection from IEC transition-system IR.

This module renders formal artifacts. It does not invoke SANY, TLC, or TLAPS,
and therefore cannot claim model-check or proof standing.
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

    tuple_expr = f"<<{variables}>>"
    parts.extend(
        [
            f"Spec == Init /\\ [][Next]_{tuple_expr}",
            "",
        ]
    )

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
    parts.append("====")

    cfg_lines = ["SPECIFICATION Spec"]
    for invariant in system.invariants:
        cfg_lines.append(f"INVARIANT {invariant.name}")
    for liveness in system.liveness:
        cfg_lines.append(f"PROPERTY {liveness.name}")

    return TlaProjection(
        module_name=system.name,
        tla="\n".join(parts) + "\n",
        cfg="\n".join(cfg_lines) + "\n",
        source_system_id=system.system_id,
    )
