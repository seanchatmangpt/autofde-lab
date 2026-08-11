from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from autofde_lab.powl.algebra import Atom, NodeId, OrderEdge, PartialOrder, Silent
from autofde_lab.powl.runner import ActivityIntent, ActivityOutcome

from .models import MitigationProcessProposal, ObservationProcessProposal


class ProcessAdmissionError(ValueError):
    pass


def _compile_steps(steps: list[Any], *, allowed_consequences: set[str]) -> PartialOrder:
    if not steps:
        raise ProcessAdmissionError("empty process")
    ids = [step.id for step in steps]
    if len(ids) != len(set(ids)):
        raise ProcessAdmissionError("duplicate step id")
    index = {step_id: i for i, step_id in enumerate(ids)}
    children = []
    edges: set[OrderEdge] = set()
    for i, step in enumerate(steps):
        consequence = getattr(step, "consequence", "READ")
        if consequence not in allowed_consequences:
            raise ProcessAdmissionError(f"consequence {consequence!r} not admitted")
        if not step.surface or not step.tool:
            raise ProcessAdmissionError("surface/tool required")
        children.append(
            Atom(
                label=step.id,
                action=f"mcp://{step.surface}/{step.tool}",
                bindings={
                    "surface": step.surface,
                    "tool": step.tool,
                    "arguments": dict(step.arguments),
                    "consequence": consequence,
                },
            )
        )
        for predecessor in step.after:
            if predecessor not in index:
                raise ProcessAdmissionError(f"unknown predecessor {predecessor!r}")
            edges.add(OrderEdge(NodeId(index[predecessor]), NodeId(i)))
    if len(children) == 1:
        children.append(Silent())
        edges.add(OrderEdge(NodeId(0), NodeId(1)))
    return PartialOrder(children=tuple(children), order=frozenset(edges))


def compile_observation_process(process: ObservationProcessProposal) -> PartialOrder:
    return _compile_steps(process.steps, allowed_consequences={"READ"})


def compile_mitigation_process(process: MitigationProcessProposal) -> PartialOrder:
    if any(step.consequence == "DO" for step in process.steps) and not process.reversible:
        raise ProcessAdmissionError("consequential process must declare reversibility")
    if not any(step.consequence == "VERIFY" for step in process.steps):
        raise ProcessAdmissionError("mitigation requires explicit verification")
    return _compile_steps(process.steps, allowed_consequences={"DO", "VERIFY"})


@dataclass
class McpActivityDriver:
    broker: Any
    allowed_capabilities: set[tuple[str, str]]
    allow_do: bool = False

    def execute(self, intent: ActivityIntent) -> ActivityOutcome:
        surface = str(intent.bindings["surface"])
        tool = str(intent.bindings["tool"])
        arguments = dict(intent.bindings.get("arguments", {}))
        consequence = str(intent.bindings.get("consequence", "READ"))
        if (surface, tool) not in self.allowed_capabilities:
            return ActivityOutcome(
                success=False, metadata={"refusal": "CAPABILITY_NOT_DISCOVERED"}
            )
        if consequence == "DO" and not self.allow_do:
            return ActivityOutcome(success=False, metadata={"refusal": "DO_NOT_ADMITTED"})
        text = asyncio.run(self.broker.call(surface, tool, arguments))
        return ActivityOutcome(
            success=True,
            value=text,
            metadata={
                "surface": surface,
                "tool": tool,
                "consequence": consequence,
                "observation": text,
            },
        )
