"""AutoFDE SELECT/CONSTRUCT -> GymAct BRCE DO composition.

AutoFDE owns candidate-plan geometry. GymAct owns consequential execution.
This module projects a flat admitted plan into POWL2, converts that document
through AutoFDE's existing POWL bridge, and binds each structural fire to a
caller-supplied :class:`gymact.brce.BrokerRequest`. It never constructs an
ExecutionGrant, infers a capability, or calls a provider/runtime ``act`` port.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from gymact.brce import BRCEBroker, BrokerRequest
from gymact.crown_runtime import VerifiedTransition
from gymact.models import Standing

from autofde_lab.fabric.powl import parse_powl_turtle, project_plan_to_powl
from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.powl_replay import ActionBinding, replay_structural_fires
from autofde_lab.powl.algebra import Atom, PartialOrder, PowlNode
from autofde_lab.powl.turtle_bridge import powl_model_to_node

__all__ = ["AdmittedPowlExecution", "execute_plan_lines_via_gymact_brce"]


@dataclass(frozen=True, slots=True)
class AdmittedPowlExecution:
    """The exact projected document, structural trace, and verified DO results."""

    powl_turtle: str
    ocel_log: OcelLog
    transitions: tuple[VerifiedTransition, ...]

    @property
    def alive(self) -> bool:
        """True only when every consequential transition independently verifies."""
        return bool(self.transitions) and all(
            transition.standing is Standing.ALIVE
            and transition.verification is not None
            and transition.verification.passed
            and transition.receipt.verified is True
            for transition in self.transitions
        )


def _run_async(coro: Any) -> Any:
    """Drive one GymAct broker coroutine without borrowing ambient authority."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _flat_atoms(tree: PowlNode) -> tuple[Atom, ...]:
    """Return the exact flat atom set admitted by AutoFDE's Turtle bridge."""
    if isinstance(tree, Atom):
        return (tree,)
    if isinstance(tree, PartialOrder) and all(
        isinstance(child, Atom) for child in tree.children
    ):
        return tree.children  # type: ignore[return-value]
    raise ValueError(
        "REFUSED:UNSUPPORTED_POWL_EXECUTION_SHAPE: expected the flat Atom/PartialOrder "
        "shape produced by project_plan_to_powl"
    )


def execute_plan_lines_via_gymact_brce(
    plan_lines: Sequence[str],
    *,
    base_iri: str,
    broker: BRCEBroker,
    request_binding: Mapping[str, BrokerRequest],
    domain_path: str | None = None,
    problem_path: str | None = None,
    planner_run: str = "run-autofde-lab-brce",
    domain_iri: str | None = None,
) -> AdmittedPowlExecution:
    """Project POWL geometry and execute every fired action through GymAct BRCE.

    ``request_binding`` is keyed by the exact ``mfwp:implementsAction`` IRI
    emitted into the POWL document. Every request must already contain its
    ``PreparedAction`` and identity-bound ``ExecutionGrant``; this function
    is intentionally incapable of manufacturing either.
    """
    turtle = project_plan_to_powl(
        plan_lines,
        base_iri,
        domain_path=domain_path,
        problem_path=problem_path,
        planner_run=planner_run,
        domain_iri=domain_iri,
    )
    tree = powl_model_to_node(parse_powl_turtle(turtle))
    atoms = _flat_atoms(tree)

    labels = [atom.label for atom in atoms]
    if len(labels) != len(set(labels)):
        raise ValueError(
            "REFUSED:AMBIGUOUS_POWL_ACTION_LABEL: BRCE bindings require one unique label "
            "per structural activity in this flat execution adapter"
        )

    transitions: list[VerifiedTransition] = []
    action_bindings: dict[str, ActionBinding] = {}

    for atom in atoms:
        action_ref = atom.action
        if not isinstance(action_ref, str) or not action_ref:
            raise ValueError(f"REFUSED:MISSING_IMPLEMENTS_ACTION: label={atom.label!r}")
        request = request_binding.get(action_ref)
        if request is None:
            raise ValueError(
                f"REFUSED:UNBOUND_IMPLEMENTS_ACTION: action={action_ref!r}"
            )

        def execute_bound(
            atom_attrs: dict[str, Any],
            *,
            expected_action: str = action_ref,
            bound_request: BrokerRequest = request,
        ) -> dict[str, Any]:
            if atom_attrs.get("action") != expected_action:
                raise ValueError(
                    "REFUSED:POWL_ACTION_IDENTITY_DRIFT: "
                    f"fired={atom_attrs.get('action')!r} expected={expected_action!r}"
                )
            transition = _run_async(broker.execute(bound_request))
            transitions.append(transition)
            return {
                "standing": transition.standing.value,
                "receipt_id": transition.receipt.receipt_id,
                "verified": transition.receipt.verified,
                "verification_passed": bool(
                    transition.verification is not None
                    and transition.verification.passed
                ),
            }

        action_bindings[atom.label] = execute_bound

    extra = sorted(set(request_binding) - {atom.action for atom in atoms})
    if extra:
        raise ValueError(f"REFUSED:UNUSED_BROKER_REQUEST: action(s)={extra!r}")

    ocel_log = replay_structural_fires(tree, action_bindings=action_bindings)
    return AdmittedPowlExecution(
        powl_turtle=turtle,
        ocel_log=ocel_log,
        transitions=tuple(transitions),
    )
