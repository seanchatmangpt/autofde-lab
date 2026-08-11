from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from autofde_lab.powl.algebra import Atom, NodeId, OrderEdge, PartialOrder, Silent
from autofde_lab.powl.runner import ActivityIntent, ActivityOutcome

from .models import MitigationProcessProposal, ObservationProcessProposal


class ProcessAdmissionError(ValueError):
    pass


# Adapter law derived from the public SREGym kubectl MCP contract. This is not a
# Kubernetes object/fault taxonomy; it distinguishes observation from mutation
# at the capability boundary so an LM cannot relabel a patch/delete as READ.
_KUBECTL_READ_PREFIXES = (
    "kubectl api-resources",
    "kubectl api-versions",
    "kubectl auth can-i",
    "kubectl auth whoami",
    "kubectl cluster-info",
    "kubectl describe",
    "kubectl diff",
    "kubectl events",
    "kubectl explain",
    "kubectl get",
    "kubectl logs",
    "kubectl rollout status",
    "kubectl top",
    "kubectl version",
)


def kubectl_command_is_read_only(command: str) -> bool:
    normalized = " ".join(str(command).strip().split())
    return any(
        normalized == prefix or normalized.startswith(prefix + " ")
        for prefix in _KUBECTL_READ_PREFIXES
    )


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

    def _authority_refusal(
        self,
        *,
        surface: str,
        tool: str,
        arguments: dict[str, Any],
        consequence: str,
    ) -> str | None:
        if surface == "submit":
            return "CONTROL_SURFACE_RESERVED"

        if surface != "kubectl":
            # Prometheus/Jaeger/Loki are observation surfaces in SREGym.
            return None if consequence != "DO" else "DO_SURFACE_NOT_ADMITTED"

        if tool == "get_previous_rollbackable_cmd":
            return None if consequence != "DO" else "DO_TOOL_IS_OBSERVATIONAL"

        if tool == "rollback_command":
            if consequence != "DO":
                return "MUTATION_MISLABELED_AS_OBSERVATION"
            return None if self.allow_do else "DO_NOT_ADMITTED"

        if tool != "exec_kubectl_cmd_safely":
            return "UNKNOWN_KUBECTL_TOOL_AUTHORITY"

        command = str(arguments.get("cmd", ""))
        read_only = kubectl_command_is_read_only(command)
        if consequence in {"READ", "VERIFY"} and not read_only:
            return "MUTATION_MISLABELED_AS_OBSERVATION"
        if consequence == "DO" and not self.allow_do:
            return "DO_NOT_ADMITTED"
        return None

    def execute(self, intent: ActivityIntent) -> ActivityOutcome:
        surface = str(intent.bindings["surface"])
        tool = str(intent.bindings["tool"])
        arguments = dict(intent.bindings.get("arguments", {}))
        consequence = str(intent.bindings.get("consequence", "READ"))
        if (surface, tool) not in self.allowed_capabilities:
            return ActivityOutcome(
                success=False, metadata={"refusal": "CAPABILITY_NOT_DISCOVERED"}
            )

        refusal = self._authority_refusal(
            surface=surface,
            tool=tool,
            arguments=arguments,
            consequence=consequence,
        )
        if refusal:
            return ActivityOutcome(success=False, metadata={"refusal": refusal})

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
