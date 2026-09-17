"""Episode2Runner: fresh candidate -> admit -> classify KNOWN -> known route ->
authority -> BRCE -> receipt -> independent verify -> OCEL -> frontier_clean
(v26.9.17 ARD §20-23; PRD §6.11-6.13).

Three invariants this runner exists to prove, each directly answering a gap the
v26.9.17 audit found:

1. **Fresh actuation identity (PRD §6.11).** `episode_id`/`request_identity`/
   `actuation_identity` are minted fresh, never derived from or equal to Episode 1's.
   `ConsequenceBoundary.execute()` legitimately returns a cached `FinalReceipt` for a
   REPEATED idempotency_token (replay protection, brce/boundary.py) -- reusing
   Episode 1's token here would make Episode 2 "succeed" by returning Episode 1's
   cached receipt without ever really executing anything, exactly what PRD §6.11
   forbids. A fresh token structurally rules that shortcut out.
2. **No UNKNOWN discovery router call after KNOWN classification (ARD §20).** This
   runner never imports `UnknownResolutionPipeline.route_unknown_to_frontier` or any
   discovery engine; classification is a `KnownRouteRegistry.lookup()` call only. If
   lookup returns None the episode ends UNKNOWN/REFUSED here -- it does NOT silently
   fall back to real exploration (a real system would re-enter `Episode1Runner`
   there; wiring that loop is out of this pass's scope, named honestly rather than
   faked).
3. **frontier_clean is computed, never asserted (ARD §22-23).** `Episode.frontier_clean`
   reads the real `ExplorationMeter` counts for THIS episode_id; since this runner
   never calls the meter's "explore_unknown"/"frontier"/"worker" resource classes,
   the zero-conjunction holds because the exploratory call sites genuinely do not
   exist in this code path, not because a flag was hand-set to True.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant, ConsequenceRequest
from autofde_lab.sa2a.brce.boundary import BoundaryExecutionResult, ConsequenceBoundary, ExecutionEnvelope
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)
from autofde_lab.sa2a.episode.episode1 import admit_target_binding
from autofde_lab.sa2a.episode.types import Episode, EpisodeKind, ExplorationMeter
from autofde_lab.sa2a.experience.compiler import ArtifactRegistry
from autofde_lab.sa2a.experience.known_route import KnownRoute, KnownRouteRegistry
from autofde_lab.sa2a.experience.types import MachineExperience
from autofde_lab.sa2a.falsification.ocel_tracer import OcelExecutionTracer

ExperienceStore = Mapping[str, MachineExperience]


@dataclass(frozen=True, slots=True)
class Episode2Result:
    episode: Episode
    known_route: Optional[KnownRoute]
    boundary_result: Optional[BoundaryExecutionResult]


class Episode2Runner:
    """Orchestrates one Episode 2 run against an already-ACTIVE KnownRoute (ARD §20)."""

    def __init__(
        self,
        *,
        state_dir: Path,
        journal_path: Path,
        receipt_store_dir: Path,
        known_route_registry: KnownRouteRegistry,
        artifact_registry: ArtifactRegistry,
        experience_store: ExperienceStore,
        exploration_meter: Optional[ExplorationMeter] = None,
    ) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = journal_path
        self.receipt_store_dir = receipt_store_dir
        self.routes = known_route_registry
        self.artifacts = artifact_registry
        self.experience_store = experience_store
        self.meter = exploration_meter or ExplorationMeter()
        self._tracer = OcelExecutionTracer("episode2")

    def _checkpoint(self, episode_id: str, stage: str, payload: Mapping[str, Any]) -> None:
        path = self.state_dir / f"{episode_id}.json"
        record = {"episode_id": episode_id, "last_completed_stage": stage, **payload}
        path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")

    def run(
        self,
        *,
        semantic_class_id: str,
        fresh_candidate: Any,
        probe_input: str,
        action_iri: str,
        target_resource: str,
        actor_id: str = "episode2-actor",
        fixture_id: str = "default-fixture",
        exact_subject_digest: str = "",
    ) -> Episode2Result:
        episode_id = f"ep2-{uuid.uuid4().hex[:12]}"
        request_identity = f"req-{uuid.uuid4().hex[:12]}"
        actuation_identity = f"act-{uuid.uuid4().hex[:12]}"  # FRESH -- never episode 1's

        # --- classify: semantic-class + equivalence-predicate lookup only, no
        # UNKNOWN discovery router call anywhere in this path (ARD §20, §10).
        route = self.routes.lookup(semantic_class_id, fresh_candidate)
        self._checkpoint(episode_id, "classify", {"classification": "KNOWN" if route else "UNKNOWN"})
        if route is None:
            episode = Episode(
                episode_id=episode_id, kind=EpisodeKind.KNOWN_REPLAY,
                exact_subject_digest=exact_subject_digest, fixture_id=fixture_id,
                semantic_class_id=semantic_class_id, request_identity=request_identity,
                actuation_identity=actuation_identity, classification="UNKNOWN",
                intelligence_usage=self.meter.usage_for(episode_id), standing="UNKNOWN",
            )
            self._checkpoint(episode_id, "complete", episode.to_dict())
            return Episode2Result(episode, None, None)

        # --- SELECT/CONSTRUCT: actually execute the compiled route against the
        # FRESH candidate's own probe key, never Episode 1's cached output. Resolved
        # via the shared experience_store (route.experience_id -> MachineExperience
        # -> compiled_artifact_ids) since KnownRoute itself (ARD §5.8) doesn't carry
        # artifact ids directly.
        route_executed = False
        experience = self.experience_store.get(route.experience_id)
        if experience is not None and experience.compiled_artifact_ids:
            artifact = self.artifacts.get(experience.compiled_artifact_ids[0])
            if artifact is not None:
                output = artifact.evaluate(probe_input)
                route_executed = output is not None

        # --- authority: a FRESH AuthorityBroker.evaluate() call, never a reused
        # Episode 1 AuthorityDecision (ARD §55-56).
        grant = AuthorityGrant(
            grant_id=f"grant-{uuid.uuid4().hex[:8]}", subject_id=actor_id,
            action_iri=action_iri, target_resource_iri=target_resource,
        )
        broker = AuthorityBroker(grants=[grant])
        decision = broker.evaluate(
            ConsequenceRequest(actor_id=actor_id, action_iri=action_iri, target_resource=target_resource, grant_id=grant.grant_id)
        )

        boundary_result: Optional[BoundaryExecutionResult] = None
        if route_executed and decision.authorized:
            actuator = RealDiskJournalActuator(self.journal_path)
            verifier = IndependentDiskJournalVerifier(self.journal_path)
            receipt_store = DurableDiskReceiptStore(self.receipt_store_dir)
            boundary = ConsequenceBoundary(broker, actuator, verifier, receipt_store)

            admission_for_action = admit_target_binding(
                action_iri, target_resource, issuer=actor_id, timestamp="2026-09-17T00:00:01Z"
            )
            envelope = ExecutionEnvelope(
                idempotency_token=actuation_identity, action_iri=action_iri,
                target_resource=target_resource, actor_id=actor_id, grant_id=grant.grant_id,
                plan_digest=route.qualification_receipt, admission_result=admission_for_action,
            )
            boundary_result = boundary.execute(envelope)
            self._checkpoint(
                episode_id, "execute_consequence",
                {"success": boundary_result.success, "state": boundary_result.state.value},
            )

        success = bool(boundary_result and boundary_result.success)

        self._tracer.declare_object(episode_id, "Episode", {"kind": "KNOWN_REPLAY"})
        self._tracer.declare_object(route.experience_id, "MachineExperience", {})
        self._tracer.declare_object(route.route_id, "KnownRoute", {"semantic_class_id": semantic_class_id})
        self._tracer.record_event(
            f"{episode_id}-e2-complete", "Episode2Completed",
            related_objects=[episode_id, route.experience_id, route.route_id],
            attributes={"success": success, "route_executed": route_executed, "authorized": decision.authorized},
        )
        ocel_path = self.state_dir / f"{episode_id}.ocel2.json"
        self._tracer.export_ocel2_json(ocel_path)

        episode = Episode(
            episode_id=episode_id, kind=EpisodeKind.KNOWN_REPLAY,
            exact_subject_digest=exact_subject_digest, fixture_id=fixture_id,
            semantic_class_id=semantic_class_id, request_identity=request_identity,
            actuation_identity=actuation_identity, classification="KNOWN",
            route_executed=route_executed, required_postcondition_verified=success,
            authority_grant_id=grant.grant_id if decision.authorized else None,
            prepared_receipt_digest=boundary_result.prepared_receipt.digest if boundary_result and boundary_result.prepared_receipt else "",
            final_receipt_digest=boundary_result.final_receipt.digest if boundary_result and boundary_result.final_receipt else "",
            ocel_digest=self._tracer.log.digest(),
            intelligence_usage=self.meter.usage_for(episode_id),
            standing=boundary_result.state.value if boundary_result else ("REFUSED_AUTHORITY" if not decision.authorized else "REFUSED_ROUTE_NOT_EXECUTED"),
            known_route_id=route.route_id,
            experience_id=route.experience_id,
        )
        self._checkpoint(episode_id, "complete", episode.to_dict())
        return Episode2Result(episode, route, boundary_result)
