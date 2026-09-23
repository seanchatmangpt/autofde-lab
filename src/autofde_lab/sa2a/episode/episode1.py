"""Episode1Runner: UNKNOWN -> candidate -> admit -> compile/admit/qualify experience
-> lawful consequence -> receipt -> independent verify -> OCEL (v26.9.17 ARD §16).

Composes real, already-Chicago-tested sa2a/ components end to end -- none of this
module reimplements admission, allocation, authority, or BRCE; it only sequences
them. Reused directly (not duplicated): `UnknownResolutionPipeline` (unknown/
resolution.py), `CMCACandidateAllocator`/`ExplorationBudget` (unknown/allocator.py),
`AuthorityBroker` (authority/broker.py), `ConsequenceBoundary` (brce/boundary.py), and
the real disk actuator/verifier/receipt-store already built for the Chicago courts
(`RealDiskJournalActuator`, `IndependentDiskJournalVerifier`, `DurableDiskReceiptStore`
in `conformance.courts.consequence_court`) -- reusing these rather than adding a
fourth near-duplicate disk-actuator implementation (the gap-audit workflow this
session already found three competing ones).

Persists intermediate episode state as a durable JSON snapshot after every stage
(ARD §16's "SHALL persist intermediate state for crash recovery/diagnosis") -- a real,
if minimal, checkpoint: re-running `Episode1Runner.run()` after a crash cannot resume
mid-stage, but the snapshot on disk names exactly which stage last completed, which is
the honest floor this pass builds rather than claiming full crash-resumability nobody
has verified.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline, AdmissionResult
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import (
    BoundaryExecutionResult,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)
from autofde_lab.sa2a.episode.types import Episode, EpisodeKind, ExplorationMeter
from autofde_lab.sa2a.experience.admission import ExperienceAdmissionGate
from autofde_lab.sa2a.experience.compiler import (
    ArtifactRegistry,
    EpisodeEvidence,
    ExperienceCompiler,
)
from autofde_lab.sa2a.experience.known_route import KnownRouteRegistry
from autofde_lab.sa2a.experience.qualification import ExperienceQualifier
from autofde_lab.sa2a.experience.types import ExperienceState, MachineExperience
from autofde_lab.sa2a.falsification.ocel_tracer import OcelExecutionTracer
from autofde_lab.sa2a.unknown.allocator import CMCACandidateAllocator, ExplorationBudget
from autofde_lab.sa2a.unknown.resolution import (
    AdmissionReceipt as UnknownAdmissionReceipt,
)
from autofde_lab.sa2a.unknown.resolution import (
    CandidateResolution,
    EpistemicState,
    UnknownQuery,
    UnknownResolutionPipeline,
)
from autofde_lab.sa2a.unknown.router import DiscoveryEngineKind, DiscoveryRouter


def admit_target_binding(
    action_iri: str, target_resource: str, *, issuer: str, timestamp: str
) -> AdmissionResult:
    """Real, Standing.ADMITTED AdmissionResult binding `action_iri` to `target_resource`.

    Same construction the AFDE-2604 fail-secure-closure test suite uses
    (`tests/sa2a/test_v26_9_16_falsification_court.py::_admit_target_binding`) --
    reused here rather than re-derived, since a distinct implementation would create
    exactly the two-implementations-of-one-invariant drift risk this repo's own
    v26.9.17 gap-audit flagged for the Chicago crown gates.
    """
    ttl = (
        "@prefix afl: <urn:autofde-lab:> .\n"
        f"<{action_iri}> afl:targetResource <{target_resource}> .\n"
    )
    result = AdmissionPipeline().admit(
        ttl, provenance_record={"issuer": issuer, "timestamp": timestamp}
    )
    if result.standing != Standing.ADMITTED:
        raise ValueError(
            f"admit_target_binding failed: {result.refusal_code} {result.reasons}"
        )
    return result


@dataclass(frozen=True, slots=True)
class Episode1Result:
    episode: Episode
    machine_experience: MachineExperience
    admission_receipt: UnknownAdmissionReceipt
    boundary_result: Optional[BoundaryExecutionResult]


class Episode1Runner:
    """Orchestrates one Episode 1 run for one semantic class (ARD §16)."""

    def __init__(
        self,
        *,
        state_dir: Path,
        journal_path: Path,
        receipt_store_dir: Path,
        exploration_meter: Optional[ExplorationMeter] = None,
        known_route_registry: Optional[KnownRouteRegistry] = None,
        artifact_registry: Optional[ArtifactRegistry] = None,
        allocator: Optional[CMCACandidateAllocator] = None,
    ) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = journal_path
        self.receipt_store_dir = receipt_store_dir
        self.meter = exploration_meter or ExplorationMeter()
        self.routes = known_route_registry or KnownRouteRegistry()
        self.artifacts = artifact_registry or ArtifactRegistry()
        self.allocator = allocator or CMCACandidateAllocator()
        self._resolution = UnknownResolutionPipeline(allocator=self.allocator)
        self._compiler = ExperienceCompiler(self.artifacts)
        self._admission_gate = ExperienceAdmissionGate(self.artifacts)
        self._qualifier = ExperienceQualifier(self.artifacts, self.routes)
        self._tracer = OcelExecutionTracer("episode1")

    def _checkpoint(
        self, episode_id: str, stage: str, payload: Mapping[str, Any]
    ) -> None:
        path = self.state_dir / f"{episode_id}.json"
        record = {"episode_id": episode_id, "last_completed_stage": stage, **payload}
        path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")

    def _no_candidate_result(
        self,
        *,
        episode_id: str,
        request_identity: str,
        actuation_identity: str,
        semantic_class_id: str,
        exact_subject_digest: str,
        fixture_id: str,
        equivalence_predicate_id: str,
        refusal_code: str,
        reason: str,
    ) -> Episode1Result:
        """Shared UNKNOWN/REFUSED result for 'no discovery mechanism produced a
        candidate' -- whether because a DiscoveryRouter had no matching engine or a
        caller-supplied `discover` callable raised (hardening, 2026-09-17)."""
        episode = Episode(
            episode_id=episode_id,
            kind=EpisodeKind.UNKNOWN_DISCOVERY,
            exact_subject_digest=exact_subject_digest,
            fixture_id=fixture_id,
            semantic_class_id=semantic_class_id,
            request_identity=request_identity,
            actuation_identity=actuation_identity,
            classification="UNKNOWN",
            intelligence_usage=self.meter.usage_for(episode_id),
            standing="UNKNOWN",
        )
        self._checkpoint(episode_id, "complete", episode.to_dict())
        return Episode1Result(
            episode=episode,
            machine_experience=MachineExperience(
                experience_id="",
                semantic_class_id=semantic_class_id,
                source_episode_id=episode_id,
                source_candidate_digest="",
                source_admission_receipt="",
                discovery_identity="",
                discovery_resource_receipt="",
                solution_candidate_digest="",
                solution_admission_receipt="",
                compiled_artifact_ids=(),
                equivalence_predicate_id=equivalence_predicate_id,
                state=ExperienceState.REFUSED,
                refusal_code=refusal_code,
            ),
            admission_receipt=UnknownAdmissionReceipt(
                receipt_id="",
                candidate_hash="",
                admitted=False,
                epistemic_standing=EpistemicState.REFUSED,
                reasons=(reason,),
            ),
            boundary_result=None,
        )

    def run(
        self,
        *,
        semantic_class_id: str,
        query: UnknownQuery,
        discover: Optional[Callable[[UnknownQuery], CandidateResolution]] = None,
        discovery_router: Optional[DiscoveryRouter] = None,
        equivalence_predicate: Callable[[Any], bool],
        equivalence_predicate_id: str,
        probe_input: str,
        action_iri: str,
        target_resource: str,
        actor_id: str = "episode1-actor",
        fixture_id: str = "default-fixture",
        exact_subject_digest: str = "",
    ) -> Episode1Result:
        episode_id = f"ep1-{uuid.uuid4().hex[:12]}"
        request_identity = f"req-{uuid.uuid4().hex[:12]}"
        actuation_identity = f"act-{uuid.uuid4().hex[:12]}"

        # --- explore-unknown: route the query to the candidate frontier under a
        # finite budget (ARD §13). This IS the exploratory event; recorded before
        # any candidate exists.
        budget = ExplorationBudget(
            max_compute_ticks=64, max_tokens=4096, max_experiments=4
        )
        self._resolution.route_unknown_to_frontier(
            [query], budget, plan_id=f"{episode_id}-frontier"
        )
        self.meter.record(episode_id, "explore_unknown", "invocations", 1)
        self._checkpoint(
            episode_id, "explore_unknown", {"semantic_class_id": semantic_class_id}
        )

        # --- discovery: produce ONE candidate. Either a caller-supplied `discover`
        # callable (never general frontier inference unless that callable chooses to
        # call one, in which case it is the caller's responsibility to also call
        # self.meter.record(...) for "frontier"/"calls" -- this runner never
        # fabricates that count), or a real `DiscoveryRouter` selecting among
        # registered engines in ARD §15 precedence order (formal-machinery-first).
        # Exactly one of `discover`/`discovery_router` must be supplied.
        if (discover is None) == (discovery_router is None):
            raise ValueError(
                "Episode1Runner.run() requires exactly one of discover= or discovery_router="
            )

        if discovery_router is not None:
            routing = discovery_router.route(query)
            self._checkpoint(
                episode_id,
                "discovery_routing",
                {
                    "selected_engine_id": routing.selected_engine_id,
                    "attempted": list(routing.attempted_engine_ids),
                    "errored": list(routing.errored_engine_ids),
                },
            )
            if routing.candidate is None:
                return self._no_candidate_result(
                    episode_id=episode_id,
                    request_identity=request_identity,
                    actuation_identity=actuation_identity,
                    semantic_class_id=semantic_class_id,
                    exact_subject_digest=exact_subject_digest,
                    fixture_id=fixture_id,
                    equivalence_predicate_id=equivalence_predicate_id,
                    refusal_code="REFUSED_NO_DISCOVERY_ENGINE_PRODUCED_CANDIDATE",
                    reason="NO_ENGINE_PRODUCED_CANDIDATE",
                )
            candidate = routing.candidate
            if routing.selected_kind in (
                DiscoveryEngineKind.FORMAL_PLANNER_OR_SOLVER,
                DiscoveryEngineKind.BOUNDED_LOCAL_SYNTHESIS,
            ):
                self.meter.record(episode_id, "exploratory_planner", "invocations", 1)
            elif (
                routing.selected_kind
                == DiscoveryEngineKind.GENERAL_EXPLORATORY_INTELLIGENCE
            ):
                self.meter.record(episode_id, "frontier", "calls", 1)
        else:
            assert discover is not None
            # Hardening (2026-09-17): a caller-supplied `discover` callable that
            # raises (a bug in the caller's own engine, a malformed query it did
            # not expect) must not crash the whole episode -- it degrades to the
            # same UNKNOWN outcome a DiscoveryRouter reports when no engine can
            # answer, never an uncaught exception escaping run().
            try:
                candidate = discover(query)
            except Exception as exc:
                self._checkpoint(episode_id, "discovery", {"error": repr(exc)})
                return self._no_candidate_result(
                    episode_id=episode_id,
                    request_identity=request_identity,
                    actuation_identity=actuation_identity,
                    semantic_class_id=semantic_class_id,
                    exact_subject_digest=exact_subject_digest,
                    fixture_id=fixture_id,
                    equivalence_predicate_id=equivalence_predicate_id,
                    refusal_code="REFUSED_DISCOVER_CALLABLE_RAISED",
                    reason=f"discover() raised: {exc!r}",
                )

        self.meter.record(episode_id, "local_discovery", "calls", 1)
        self.meter.record(
            episode_id, "local_discovery", "tokens", candidate.consumed_tokens
        )
        self._checkpoint(
            episode_id, "discovery", {"candidate_id": candidate.candidate_id}
        )

        # --- admit candidate (Received != Admitted, PRD §6.3).
        admission_receipt = self._resolution.admit_candidate(candidate)
        self._checkpoint(
            episode_id,
            "candidate_admission",
            {
                "admitted": admission_receipt.admitted,
                "reasons": list(admission_receipt.reasons),
            },
        )
        if not admission_receipt.admitted:
            episode = Episode(
                episode_id=episode_id,
                kind=EpisodeKind.UNKNOWN_DISCOVERY,
                exact_subject_digest=exact_subject_digest,
                fixture_id=fixture_id,
                semantic_class_id=semantic_class_id,
                request_identity=request_identity,
                actuation_identity=actuation_identity,
                classification="REFUSED",
                intelligence_usage=self.meter.usage_for(episode_id),
                standing="REFUSED",
            )
            return Episode1Result(
                episode=episode,
                machine_experience=MachineExperience(
                    experience_id="",
                    semantic_class_id=semantic_class_id,
                    source_episode_id=episode_id,
                    source_candidate_digest=candidate.candidate_hash,
                    source_admission_receipt="",
                    discovery_identity=candidate.source_identity,
                    discovery_resource_receipt="",
                    solution_candidate_digest=candidate.candidate_hash,
                    solution_admission_receipt="",
                    compiled_artifact_ids=(),
                    equivalence_predicate_id=equivalence_predicate_id,
                    state=ExperienceState.REFUSED,
                    refusal_code="REFUSED_CANDIDATE_NOT_ADMITTED",
                ),
                admission_receipt=admission_receipt,
                boundary_result=None,
            )

        # --- compile candidate experience (ARD §17) -- CANDIDATE state only.
        experience = self._compiler.compile(
            semantic_class_id=semantic_class_id,
            admitted_solution=candidate,
            admission_receipt=admission_receipt,
            episode_evidence=EpisodeEvidence(
                episode_id=episode_id,
                discovery_identity=candidate.source_identity,
                discovery_resource_receipt=f"budget:{budget.max_compute_ticks}:{budget.max_tokens}",
            ),
            equivalence_predicate_id=equivalence_predicate_id,
        )
        self._checkpoint(
            episode_id,
            "compile_experience",
            {"experience_id": experience.experience_id},
        )

        # --- admit experience (ARD §18).
        admit_result = self._admission_gate.admit(experience)
        self._checkpoint(
            episode_id,
            "admit_experience",
            {"admitted": admit_result.admitted, "reasons": list(admit_result.reasons)},
        )
        if not admit_result.admitted:
            episode = Episode(
                episode_id=episode_id,
                kind=EpisodeKind.UNKNOWN_DISCOVERY,
                exact_subject_digest=exact_subject_digest,
                fixture_id=fixture_id,
                semantic_class_id=semantic_class_id,
                request_identity=request_identity,
                actuation_identity=actuation_identity,
                classification="REFUSED",
                intelligence_usage=self.meter.usage_for(episode_id),
                standing="REFUSED",
                experience_id=experience.experience_id,
            )
            return Episode1Result(
                episode, admit_result.experience, admission_receipt, None
            )

        # --- qualify experience -> ACTIVE + register KnownRoute (ARD §19).
        qual_result = self._qualifier.qualify(
            admit_result.experience,
            equivalence_predicate=equivalence_predicate,
            probe_input=probe_input,
        )
        self._checkpoint(
            episode_id,
            "qualify_experience",
            {
                "qualified": qual_result.qualified,
                "route_id": qual_result.known_route.route_id
                if qual_result.known_route
                else None,
            },
        )
        if not qual_result.qualified:
            episode = Episode(
                episode_id=episode_id,
                kind=EpisodeKind.UNKNOWN_DISCOVERY,
                exact_subject_digest=exact_subject_digest,
                fixture_id=fixture_id,
                semantic_class_id=semantic_class_id,
                request_identity=request_identity,
                actuation_identity=actuation_identity,
                classification="REFUSED",
                intelligence_usage=self.meter.usage_for(episode_id),
                standing="REFUSED",
                experience_id=experience.experience_id,
            )
            return Episode1Result(
                episode, qual_result.experience, admission_receipt, None
            )

        active_experience = qual_result.experience

        # --- execute the lawful resulting route through real authority + BRCE
        # (Episode 1 also produces a real consequence for the class it just solved).
        grant = AuthorityGrant(
            grant_id=f"grant-{uuid.uuid4().hex[:8]}",
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
        broker = AuthorityBroker(grants=[grant])
        actuator = RealDiskJournalActuator(self.journal_path)
        verifier = IndependentDiskJournalVerifier(self.journal_path)
        receipt_store = DurableDiskReceiptStore(self.receipt_store_dir)
        boundary = ConsequenceBoundary(broker, actuator, verifier, receipt_store)

        admission_for_action = admit_target_binding(
            action_iri,
            target_resource,
            issuer=actor_id,
            timestamp="2026-09-17T00:00:00Z",
        )
        envelope = ExecutionEnvelope(
            idempotency_token=actuation_identity,
            action_iri=action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            grant_id=grant.grant_id,
            plan_digest=active_experience.digest,
            admission_result=admission_for_action,
        )
        boundary_result = boundary.execute(envelope)
        self._checkpoint(
            episode_id,
            "execute_consequence",
            {"success": boundary_result.success, "state": boundary_result.state.value},
        )

        # --- OCEL evidence.
        self._tracer.declare_object(
            episode_id, "Episode", {"kind": "UNKNOWN_DISCOVERY"}
        )
        self._tracer.declare_object(
            experience.experience_id,
            "MachineExperience",
            {"state": active_experience.state.value},
        )
        if qual_result.known_route:
            self._tracer.declare_object(
                qual_result.known_route.route_id,
                "KnownRoute",
                {"semantic_class_id": semantic_class_id},
            )
        self._tracer.record_event(
            f"{episode_id}-e1-complete",
            "Episode1Completed",
            related_objects=[episode_id, experience.experience_id]
            + ([qual_result.known_route.route_id] if qual_result.known_route else []),
            attributes={
                "success": boundary_result.success,
                "standing": boundary_result.state.value,
            },
        )
        ocel_path = self.state_dir / f"{episode_id}.ocel2.json"
        self._tracer.export_ocel2_json(ocel_path)

        # Hardening (2026-09-17, tag-readiness audit): `Episode.manufacture_digest`
        # (PRD §14 item 12 "real manufacture where required") was defined and
        # serialized but never assigned anywhere -- confirmed live, every crown run
        # emitted an empty string despite a real CompiledDeterministicRule genuinely
        # being manufactured. Bind it to that artifact's own real fingerprint.
        manufactured_artifact = (
            self.artifacts.get(active_experience.compiled_artifact_ids[0])
            if active_experience.compiled_artifact_ids
            else None
        )
        manufacture_digest = (
            manufactured_artifact.fingerprint if manufactured_artifact else ""
        )

        episode = Episode(
            episode_id=episode_id,
            kind=EpisodeKind.UNKNOWN_DISCOVERY,
            exact_subject_digest=exact_subject_digest,
            fixture_id=fixture_id,
            semantic_class_id=semantic_class_id,
            request_identity=request_identity,
            actuation_identity=actuation_identity,
            classification="KNOWN" if boundary_result.success else "REFUSED",
            route_executed=boundary_result.success,
            required_postcondition_verified=boundary_result.success,
            plan_digest=active_experience.digest,
            manufacture_digest=manufacture_digest,
            authority_grant_id=grant.grant_id,
            prepared_receipt_digest=boundary_result.prepared_receipt.digest
            if boundary_result.prepared_receipt
            else "",
            final_receipt_digest=boundary_result.final_receipt.digest
            if boundary_result.final_receipt
            else "",
            ocel_digest=self._tracer.log.digest(),
            intelligence_usage=self.meter.usage_for(episode_id),
            standing=boundary_result.state.value,
            known_route_id=qual_result.known_route.route_id
            if qual_result.known_route
            else "",
            experience_id=experience.experience_id,
        )
        self._checkpoint(episode_id, "complete", episode.to_dict())
        return Episode1Result(
            episode, active_experience, admission_receipt, boundary_result
        )
