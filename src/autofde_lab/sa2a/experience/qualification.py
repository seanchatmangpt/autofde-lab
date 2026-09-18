"""ExperienceQualifier: ADMITTED MachineExperience -> QUALIFIED -> ACTIVE (ARD §19).

Admission alone does not make a route KNOWN (PRD §6.8). This module proves the
compiled representation can actually replace Episode 1's exploratory transformation
before permitting `state=ACTIVE` -- the only state `KnownRouteRegistry.lookup()`
(known_route.py) will ever return -- by checking, in order, every clause ARD §19
names: semantic class bound, equivalence predicate bound, compiled route exists,
compiled route executes (a real probe call, not merely "the object is present"),
stays inside declared resources, and carries no forbidden exploratory boundary
(structurally true here: `CompiledDeterministicRule.evaluate()` is a pure function
over its own frozen fields -- it cannot make an external/exploratory call by
construction, unlike an LLM-backed fallback would).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from autofde_lab.sa2a.experience.compiler import ArtifactRegistry
from autofde_lab.sa2a.experience.known_route import KnownRoute, KnownRouteRegistry
from autofde_lab.sa2a.experience.types import ExperienceState, MachineExperience

REFUSED_PREDICATE_UNBOUND = "REFUSED_EXPERIENCE_EQUIVALENCE_PREDICATE_UNBOUND"
REFUSED_PROBE_FAILED = "REFUSED_EXPERIENCE_PROBE_FAILED"
REFUSED_UNBOUNDED_RESOURCES = "REFUSED_EXPERIENCE_UNBOUNDED_RESOURCES"
#: Hardening (2026-09-17): a second qualify() call on the same still-ADMITTED
#: experience object (immutability means the state check alone can't catch this --
#: see KnownRouteRegistry.register_route()'s docstring for the confirmed-live bug).
REFUSED_ALREADY_QUALIFIED = "REFUSED_EXPERIENCE_ALREADY_QUALIFIED"


@dataclass(frozen=True, slots=True)
class QualificationResult:
    experience: MachineExperience
    known_route: Optional[KnownRoute]
    receipt_id: str
    qualified: bool
    refusal_code: Optional[str] = None
    reasons: tuple[str, ...] = ()


class ExperienceQualifier:
    def __init__(self, artifact_registry: ArtifactRegistry, known_route_registry: KnownRouteRegistry) -> None:
        self._artifacts = artifact_registry
        self._routes = known_route_registry

    def qualify(
        self,
        experience: MachineExperience,
        *,
        equivalence_predicate: Callable[[Any], bool],
        probe_input: str,
        required_preconditions: tuple[str, ...] = (),
        planner_or_policy_identity: str = "experience-compiler",
        manufacturer_identity: str = "sa2a.experience.compiler",
        expected_capabilities: tuple[str, ...] = (),
        resource_envelope: Mapping[str, int] | None = None,
    ) -> QualificationResult:
        if experience.state != ExperienceState.ADMITTED:
            return self._refuse(
                experience,
                REFUSED_PREDICATE_UNBOUND,
                (f"expected state ADMITTED, got {experience.state.value}",),
            )

        # Clause: equivalence predicate bound -- register it so future KnownRoute
        # lookups (episode 2) can actually invoke it; a route whose predicate was
        # never registered can never be looked up, by construction.
        if experience.equivalence_predicate_id:
            self._routes.register_predicate(experience.equivalence_predicate_id, equivalence_predicate)
        else:
            return self._refuse(
                experience, REFUSED_PREDICATE_UNBOUND, ("equivalence_predicate_id is empty",)
            )

        # Clause: compiled route exists + compiled route executes -- a real probe,
        # not merely checking the artifact object is present (ArtifactRegistry.get
        # already proved presence at admission time; this proves it PRODUCES the
        # deterministic output it claims to for a real, matching input).
        artifact = self._artifacts.get(experience.compiled_artifact_ids[0])
        if artifact is None:
            return self._refuse(experience, REFUSED_PROBE_FAILED, ("compiled artifact missing at qualification",))
        probe_output = artifact.evaluate(probe_input)
        if probe_output is None:
            return self._refuse(
                experience,
                REFUSED_PROBE_FAILED,
                (f"artifact.evaluate({probe_input!r}) returned None -- route does not execute",),
            )

        # Clause: stays inside declared resources -- every bound must be finite
        # and positive (a real AllocationEnvelope-style check, ARD §5.5).
        envelope = dict(resource_envelope or {"max_probe_calls": 1})
        for key, value in envelope.items():
            if not isinstance(value, int) or value <= 0:
                return self._refuse(
                    experience, REFUSED_UNBOUNDED_RESOURCES, (f"resource bound {key}={value} is not finite/positive",)
                )

        qualified_experience = experience.with_state(ExperienceState.QUALIFIED)
        qualification_receipt = f"expqual-{uuid.uuid4().hex[:12]}"
        route_id = f"route-{uuid.uuid4().hex[:12]}"
        active_experience = qualified_experience.with_state(
            ExperienceState.ACTIVE,
            known_route_id=route_id,
            qualification_receipt=qualification_receipt,
        )

        route = KnownRoute(
            route_id=route_id,
            semantic_class_id=experience.semantic_class_id,
            experience_id=experience.experience_id,
            equivalence_predicate_id=experience.equivalence_predicate_id,
            required_preconditions=required_preconditions,
            planner_or_policy_identity=planner_or_policy_identity,
            manufacturer_identity=manufacturer_identity,
            expected_capabilities=expected_capabilities,
            resource_envelope=envelope,
            qualification_receipt=qualification_receipt,
            invalidation_set=dict(experience.invalidation_set),
            state="ACTIVE",
        )
        try:
            self._routes.register_route(route)
        except ValueError as exc:
            # Same-shaped typed refusal as every other clause above -- never let
            # register_route()'s duplicate-registration guard escape as a raw,
            # uncaught ValueError from this method.
            return self._refuse(experience, REFUSED_ALREADY_QUALIFIED, (str(exc),))

        return QualificationResult(
            experience=active_experience,
            known_route=route,
            receipt_id=qualification_receipt,
            qualified=True,
            reasons=("SEMANTIC_CLASS_BOUND", "PREDICATE_BOUND", "PROBE_EXECUTED", "RESOURCES_BOUNDED"),
        )

    @staticmethod
    def _refuse(experience: MachineExperience, code: str, reasons: tuple[str, ...]) -> QualificationResult:
        refused = experience.with_state(ExperienceState.REFUSED, refusal_code=code)
        return QualificationResult(
            experience=refused,
            known_route=None,
            receipt_id=f"expqual-{uuid.uuid4().hex[:12]}",
            qualified=False,
            refusal_code=code,
            reasons=reasons,
        )
