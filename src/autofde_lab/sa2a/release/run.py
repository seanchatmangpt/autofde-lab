"""ReleaseRun: the v26.9.17 crown orchestrator (PRD §12; ARD §50).

"Crown command semantics... SHALL NOT contain independent duplicated semantic
logic" (ARD §50): every stage below is a call into an already-real, already-tested
component (`SubjectResolver`, `Episode1Runner`, `Episode2Runner`, the real
`ReplayEngine`, the real subprocess `fresh_consumer` verifier) -- this module only
sequences them and enforces the typed `ReleaseState` transition law
(`state_machine.py`), it computes no admission/authority/consequence verdict itself.

Each stage transition is enforced through `validate_release_transition()` for real
(not merely narrated): an attempt to skip a required predecessor raises, the same
discipline `state_machine.py`'s own docstring describes.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from autofde_lab.sa2a.admission.falsifier_corpus import FalsifierCorpusVerdict, run_falsifier_corpus
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.replay import ReplayEngine, ReplayReport, ReplayStanding
from autofde_lab.sa2a.composition.exact_subject import ExactSubject
from autofde_lab.sa2a.composition.receipt import CompositionReceipt, build_composition_receipt
from autofde_lab.sa2a.composition.resolver import SubjectResolutionError, SubjectResolver
from autofde_lab.sa2a.conformance.courts.authority_court import AuthorityCourt
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    ConsequenceCourt,
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)
from autofde_lab.sa2a.episode.episode1 import Episode1Result, Episode1Runner
from autofde_lab.sa2a.episode.episode2 import Episode2Result, Episode2Runner
from autofde_lab.sa2a.experience.compiler import ArtifactRegistry
from autofde_lab.sa2a.experience.known_route import KnownRouteRegistry
from autofde_lab.sa2a.release.state_machine import ReleaseState, validate_release_transition
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery
from autofde_lab.sa2a.unknown.router import DiscoveryRouter


@dataclass(frozen=True, slots=True)
class ReleaseRunResult:
    state: ReleaseState
    exact_subject: Optional[ExactSubject]
    episode1: Optional[Episode1Result]
    episode2: Optional[Episode2Result]
    replay_report: Optional[ReplayReport]
    fresh_consumer_standing: Optional[dict]
    # Gap 1 (PRD §14 item 28 / ARD §64 item 16): the standalone, independently-
    # verifiable receipt binding ExactSubject.composition_digest to THIS run's own
    # Episode 1 and Episode 2 evidence -- only ever set once the crown reaches
    # CROWNED (both episodes' real receipts/OCEL digests exist to bind).
    composition_receipt: Optional[CompositionReceipt] = None
    # Gap 2 (PRD §14 item 27 / ARD §64 item 15): the real, callable falsifier-corpus
    # verdict run during CHICAGO_RUNNING -- named which falsifiers ran, which
    # survived (a real finding), which were correctly caught.
    falsifier_corpus_verdict: Optional[FalsifierCorpusVerdict] = None
    # Gap 3 (PRD §14 item 26 / ARD §64 item 15): real, already-tested Chicago court
    # gates composed (never re-derived) against this crown's own evidence during
    # CHICAGO_RUNNING -- {gate_id: CourtGateResult | AuthorityCheckResult}.
    chicago_court_gates: Optional[Mapping[str, Any]] = None
    reason: str = ""

    def to_receipt(self) -> dict[str, Any]:
        """PRD §63-shaped machine-readable final result."""
        ep1 = self.episode1
        ep2 = self.episode2
        return {
            "release": self.exact_subject.release_id if self.exact_subject else "",
            "composition_digest": self.exact_subject.composition_digest if self.exact_subject else "",
            "profile": self.exact_subject.semantic_profile if self.exact_subject else "",
            "episode_1": ep1.episode.to_dict() if ep1 else None,
            "machine_experience": (
                {
                    "experience_id": ep1.machine_experience.experience_id,
                    "state": ep1.machine_experience.state.value,
                    "known_route_id": ep1.machine_experience.known_route_id,
                }
                if ep1
                else None
            ),
            "episode_2": ep2.episode.to_dict() if ep2 else None,
            "replay": (
                {"verdict": self.replay_report.verdict.value, "standing": self.replay_report.standing.value}
                if self.replay_report
                else None
            ),
            "fresh_consumer": (
                {"verdict": self.fresh_consumer_standing.get("verdict")} if self.fresh_consumer_standing else None
            ),
            "composition_receipt": (
                self.composition_receipt.to_dict() if self.composition_receipt else None
            ),
            "falsifier_corpus": (
                {
                    "corpus_digest": self.falsifier_corpus_verdict.corpus_digest,
                    "all_mandatory_caught": self.falsifier_corpus_verdict.all_mandatory_caught,
                    "survived_falsifier_ids": list(self.falsifier_corpus_verdict.survived_falsifier_ids),
                }
                if self.falsifier_corpus_verdict
                else None
            ),
            "chicago_court_gates": (
                {gate_id: bool(getattr(result, "passed", False)) for gate_id, result in self.chicago_court_gates.items()}
                if self.chicago_court_gates
                else None
            ),
            "standing": self.state.value,
            "reason": self.reason,
        }


class ReleaseRun:
    """Orchestrates one v26.9.17 crown run (PRD §12, ARD §50)."""

    def __init__(self, *, work_dir: Path) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.state = ReleaseState.CREATED
        self.history: list[ReleaseState] = [self.state]

    def _goto(self, target: ReleaseState) -> None:
        validate_release_transition(self.state, target)
        self.state = target
        self.history.append(target)

    def run(
        self,
        *,
        candidate_manifest: Mapping[str, Any],
        semantic_class_id: str,
        episode1_query: UnknownQuery,
        episode1_discover: Optional[Callable[[UnknownQuery], CandidateResolution]] = None,
        discovery_router: Optional[DiscoveryRouter] = None,
        equivalence_predicate: Callable[[Any], bool],
        equivalence_predicate_id: str,
        probe_input: str,
        action_iri: str,
        episode1_target_resource: str,
        episode2_fresh_candidate: CandidateResolution,
        episode2_target_resource: str,
    ) -> ReleaseRunResult:
        # Hardening (2026-09-17): `ReleaseRun` is single-run by design (one work_dir,
        # one state/history sequence -- ARD §50). A second `.run()` call on the same
        # already-CROWNED/REFUSED/... instance used to reach the first `self._goto()`
        # inside this method and raise an uncaught `ValueError` from
        # `validate_release_transition` ("cannot go from CROWNED to SUBJECT_FENCED"),
        # since only `SubjectResolutionError` is caught below. Refusing outright here
        # (rather than silently resetting `self.state`/`self.history`, which would
        # erase the record of the first run -- a `no-dual-bookkeeping.md` violation)
        # is the honest choice: construct a new `ReleaseRun` with a fresh `work_dir`
        # for a second attempt.
        if self.state != ReleaseState.CREATED:
            return ReleaseRunResult(
                self.state, None, None, None, None, None,
                reason=(
                    f"REFUSED:ALREADY_RUN: this ReleaseRun instance already reached "
                    f"{self.state.value!r} (history={[s.value for s in self.history]}); "
                    "ReleaseRun.run() is single-run by design -- construct a new "
                    "ReleaseRun with a fresh work_dir for a second attempt."
                ),
            )

        # Hardening (2026-09-17): `Episode1Runner.run()` requires EXACTLY one of
        # `discover=`/`discovery_router=` and raises an uncaught `ValueError`
        # otherwise -- but `ReleaseRun.run()` previously had no `discovery_router`
        # parameter at all, so a caller passing `episode1_discover=None` (legal --
        # nothing enforces the Callable type hint at runtime) had NO way to supply
        # the other half and would crash mid-run, leaving `self.state` stuck at
        # EPISODE_1_RUNNING (not a lawful terminal/exit state). Guarding here, before
        # any state transition, turns that crash into the same typed REFUSED result
        # every other misconfiguration in this method already produces.
        if (episode1_discover is None) == (discovery_router is None):
            return ReleaseRunResult(
                self.state, None, None, None, None, None,
                reason=(
                    "REFUSED:DISCOVERY_CONFIGURATION: exactly one of episode1_discover= "
                    "or discovery_router= must be supplied to ReleaseRun.run()"
                ),
            )

        state_dir = self.work_dir / "state"
        journal_path = self.work_dir / "journal.json"
        receipt_store_dir = self.work_dir / "receipts"

        # --- SUBJECT_FENCED
        try:
            exact_subject = SubjectResolver().resolve(candidate_manifest)
        except SubjectResolutionError as exc:
            self._goto(ReleaseState.REFUSED)
            return ReleaseRunResult(self.state, None, None, None, None, None, reason=str(exc))
        self._goto(ReleaseState.SUBJECT_FENCED)

        # --- PREFLIGHTED: fail closed on any repository pinned "dirty:" (ARD §61 --
        # a dirty worktree SHALL prevent final release standing).
        dirty = [r.name for r in exact_subject.repositories if r.exact_sha.startswith("dirty:")]
        if dirty:
            self._goto(ReleaseState.BLOCKED)
            return ReleaseRunResult(
                self.state, exact_subject, None, None, None, None,
                reason=f"BLOCKED:DIRTY_WORKTREE:{','.join(dirty)}",
            )
        self._goto(ReleaseState.PREFLIGHTED)

        # --- EPISODE_1_RUNNING / EPISODE_1_VERIFIED
        self._goto(ReleaseState.EPISODE_1_RUNNING)
        routes = KnownRouteRegistry()
        artifacts = ArtifactRegistry()
        runner1 = Episode1Runner(
            state_dir=state_dir, journal_path=journal_path, receipt_store_dir=receipt_store_dir,
            known_route_registry=routes, artifact_registry=artifacts,
        )
        ep1 = runner1.run(
            semantic_class_id=semantic_class_id, query=episode1_query, discover=episode1_discover,
            discovery_router=discovery_router,
            equivalence_predicate=equivalence_predicate, equivalence_predicate_id=equivalence_predicate_id,
            probe_input=probe_input, action_iri=action_iri, target_resource=episode1_target_resource,
            exact_subject_digest=exact_subject.composition_digest,
        )
        if ep1.episode.classification != "KNOWN" or ep1.episode.standing != "EXECUTED":
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, None, None, None,
                reason=f"episode 1 did not reach KNOWN/EXECUTED (classification={ep1.episode.classification!r}, standing={ep1.episode.standing!r})",
            )
        self._goto(ReleaseState.EPISODE_1_VERIFIED)

        # --- EXPERIENCE_ADMITTED
        if ep1.machine_experience.state.value != "ACTIVE":
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, None, None, None,
                reason=f"MachineExperience did not reach ACTIVE (state={ep1.machine_experience.state.value!r})",
            )
        self._goto(ReleaseState.EXPERIENCE_ADMITTED)

        # --- EPISODE_2_RUNNING / EPISODE_2_VERIFIED
        self._goto(ReleaseState.EPISODE_2_RUNNING)
        experience_store = {ep1.machine_experience.experience_id: ep1.machine_experience}
        runner2 = Episode2Runner(
            state_dir=state_dir, journal_path=journal_path, receipt_store_dir=receipt_store_dir,
            known_route_registry=routes, artifact_registry=artifacts, experience_store=experience_store,
        )
        ep2 = runner2.run(
            semantic_class_id=semantic_class_id, fresh_candidate=episode2_fresh_candidate,
            probe_input=probe_input, action_iri=action_iri, target_resource=episode2_target_resource,
            # Hardening (2026-09-17, tag-readiness audit): this call previously
            # omitted exact_subject_digest even though Episode2Runner.run() accepts
            # it -- confirmed live, Episode 2's own record carried "" while Episode
            # 1's carried the real composition digest, weakening PRD §14 item 28
            # ("one composition receipt binds the COMPLETE exact subject").
            exact_subject_digest=exact_subject.composition_digest,
        )
        if ep2.episode.classification != "KNOWN" or not ep2.episode.frontier_clean:
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, ep2, None, None,
                reason=f"episode 2 did not reach KNOWN+frontier_clean (classification={ep2.episode.classification!r}, frontier_clean={ep2.episode.frontier_clean})",
            )
        self._goto(ReleaseState.EPISODE_2_VERIFIED)

        # --- CHICAGO_RUNNING: real ReplayEngine (zero actuation) + fresh consumer
        # (real, separate subprocess) -- both UNCHANGED from before this pass, never
        # weakened -- PLUS (this pass, Gap 2/Gap 3): a real, callable falsifier-corpus
        # run (PRD §14 item 27) and real, already-tested Chicago court gates composed
        # directly against this crown's own evidence (PRD §14 item 26 / ARD §64 item
        # 15). Every gate below CALLS an already-real, already-tested method
        # (`ConsequenceCourt`/`AuthorityCourt`/`FalsifierSuite`/`SubjectResolver`) --
        # this stage computes no admission/authority/consequence verdict of its own,
        # per ARD §50. Named, not silent: this still does not consolidate the 3
        # pre-existing duplicate "12-gate" orchestrators (see
        # docs/jira/v26.9.17/ for what remains unconsolidated) -- it composes 2 of
        # the 6 real court classes' own real methods, plus the falsifiers/resolver
        # already reused elsewhere in this crown; the other 4 courts' checks do not
        # apply to this crown's own evidence shapes (named in
        # `ReleaseRun._chicago_court_scope_notes`, not silently skipped).
        self._goto(ReleaseState.CHICAGO_RUNNING)
        receipt_records = self._load_receipt_records(receipt_store_dir)
        replay_report = ReplayEngine().verify_chain(receipt_records)
        if replay_report.standing != ReplayStanding.ALIVE:
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, ep2, replay_report, None,
                reason=f"replay standing {replay_report.standing.value} (verdict {replay_report.verdict.value})",
            )

        fresh_consumer_standing = self._run_fresh_consumer(state_dir, ep1.episode.episode_id, ep2.episode.episode_id)
        if fresh_consumer_standing.get("verdict") != "CONFORMANT_EVIDENCE_RECONSTRUCTED":
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, ep2, replay_report, fresh_consumer_standing,
                reason=f"fresh-consumer verdict {fresh_consumer_standing.get('verdict')!r}",
            )

        # --- Gap 2 (PRD §14 item 27): zero mandatory falsifiers survive. Composes
        # the real `FalsifierSuite` (admission/falsifiers.py) and the real
        # `SubjectResolver` (composition/resolver.py) -- never re-derives either.
        falsifier_verdict = run_falsifier_corpus()
        if not falsifier_verdict.all_mandatory_caught:
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, ep2, replay_report, fresh_consumer_standing,
                falsifier_corpus_verdict=falsifier_verdict,
                reason=(
                    "mandatory falsifier(s) survived: "
                    f"{list(falsifier_verdict.survived_falsifier_ids)}"
                ),
            )

        # --- Gap 3 (PRD §14 item 26 / ARD §64 item 15): mandatory Chicago gates
        # pass. Composes real, already-tested `ConsequenceCourt`/`AuthorityCourt`
        # methods against this crown's own journal/receipt-store infra and this
        # crown's own action_iri/target_resource/candidate identity.
        chicago_gates = self._run_chicago_court_gates(
            journal_path=journal_path,
            receipt_store_dir=receipt_store_dir,
            action_iri=action_iri,
            target_resource=episode2_target_resource,
            episode2_candidate=episode2_fresh_candidate,
        )
        failed_gates = [gate_id for gate_id, result in chicago_gates.items() if not result.passed]
        if failed_gates:
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, ep2, replay_report, fresh_consumer_standing,
                falsifier_corpus_verdict=falsifier_verdict,
                chicago_court_gates=chicago_gates,
                reason=f"mandatory Chicago court gate(s) failed: {failed_gates}",
            )

        self._goto(ReleaseState.EVIDENCE_VALIDATED)

        # --- CROWNED. Gap 1 (PRD §14 item 28 / ARD §64 item 16): construct the
        # real, standalone CompositionReceipt binding ExactSubject.composition_digest
        # to THIS run's own Episode 1 and Episode 2 final-receipt/OCEL digests --
        # tamper-evident evidence that all three were genuinely bound in ONE run.
        composition_receipt = build_composition_receipt(
            receipt_id=f"composition-receipt-{uuid.uuid4().hex[:12]}",
            release_id=exact_subject.release_id,
            composition_digest=exact_subject.composition_digest,
            episode1_id=ep1.episode.episode_id,
            episode1_final_receipt_digest=ep1.episode.final_receipt_digest,
            episode1_ocel_digest=ep1.episode.ocel_digest,
            episode2_id=ep2.episode.episode_id,
            episode2_final_receipt_digest=ep2.episode.final_receipt_digest,
            episode2_ocel_digest=ep2.episode.ocel_digest,
        )
        self._goto(ReleaseState.CROWNED)
        return ReleaseRunResult(
            self.state, exact_subject, ep1, ep2, replay_report, fresh_consumer_standing,
            composition_receipt=composition_receipt,
            falsifier_corpus_verdict=falsifier_verdict,
            chicago_court_gates=chicago_gates,
            reason="CROWNED",
        )

    # -------------------------------------------------------------------------
    # Gap 3: real Chicago court gates, composed (never re-derived) against this
    # crown's own evidence.
    # -------------------------------------------------------------------------

    #: Named, honest scope record (per this pass's own instructions: "do NOT force
    #: it -- name precisely which named CHI-* gates you wired for real and which
    #: remain not-applicable-to-this-crown"). Read by `StructuredOutput`/callers that
    #: want the exact scope decision without re-deriving it from the docstring above.
    CHICAGO_COURT_GATES_WIRED: tuple[str, ...] = (
        "CHI-BRCE-01-PREPARED-COMMIT",
        "CHI-BRCE-02-BYPASS-PREVENTION",
        "CHI-BRCE-03-ANTI-COLLUSION",
        "CHI-POST-01-INDEPENDENT-OBSERVATION",
        "CHI-BRCE-04-IDEMPOTENCY-REPLAY-REFUSAL",
        "SA2A-AUTH-AGENT-NOT-AUTHORITY",
        "SA2A-AUTH-PLAN-NOT-AUTHORITY",
        "SA2A-AUTH-PROOF-NOT-AUTHORITY",
        "SA2A-AUTH-CAPABILITY-NOT-AUTHORITY",
        "SA2A-AUTH-GRANT-REQUIRED",
        "SA2A-AUTH-CONFUSED-DEPUTY",
        "CHI-PLAN-AUTH-TOKEN-REBINDING",
        "SA2A-AUTH-LEGITIMATE-GRANT",
        "CHI-PLAN-AUTH-PLANNER-NON-AUTHORITY",
    )
    CHICAGO_COURT_GATES_NOT_APPLICABLE: Mapping[str, str] = {
        "CHI-ID-GIT-SHA": (
            "IdentityCourt.verify_git_sha() checks a DECLARED sha against a REAL "
            "local git repository's live HEAD. ExactSubject.repositories carries no "
            "marker distinguishing 'this local checkout' from an arbitrary declared "
            "sibling repository, and the existing demo/test manifests (cli.py, "
            "tests/sa2a/release/test_release_run_chicago.py) legitimately declare "
            "synthetic SHAs (e.g. 'a'*40) for repositories this checkout is not. "
            "Forcing this gate would either fabricate a match or falsely NONCONFORMANT "
            "every existing passing demo/test crown run."
        ),
        "CHI-ID-ARTIFACT-DIGEST": (
            "IdentityCourt.verify_artifact_digest() expects an ExecutableArtifact/"
            "Path/str/bytes; this crown's manufactured artifact is a "
            "CompiledDeterministicRule (experience/compiler.py), a different type "
            "with its own real fingerprint-based identity check already enforced at "
            "manufacture time."
        ),
        "CHI-ID-ROOT-MANIFEST": (
            "IdentityCourt.verify_root_manifest() expects a RootManifest dataclass "
            "instance; this crown's root_manifest_digest is a plain declared string "
            "on ExactSubject with no corresponding RootManifest object constructed "
            "anywhere in the crown path."
        ),
        "CHI-ID-COUNTERFEIT-TAG": (
            "IdentityCourt.verify_tag_resolution() expects an admitted-tags registry "
            "this crown never constructs (no tag-resolution concept in the "
            "Episode/MachineExperience/KnownRoute model)."
        ),
        "SA2A-ENV-STANDING-ESCALATION / SA2A-ENV-DIGEST-MISMATCH": (
            "IdentityCourt.verify_envelope_standing_escalation()/verify_envelope_digest() "
            "expect a SemanticEnvelope; this crown's Episode/MachineExperience "
            "objects are a different, already-lawful-transition-checked type "
            "(experience/types.py's own ExperienceState transitions, episode/"
            "types.py's Standing-valued Episode.standing)."
        ),
        "CHI-REPLAY-01 (ReplayCourt.verify_replay_chain_without_actuation)": (
            "ReplayCourt.__init__ always constructs a real (possibly empty) "
            "AuthorityBroker via `authority_broker or AuthorityBroker()` -- it can "
            "never reproduce the deliberate `authority_broker=None` (skip the "
            "per-receipt authority re-check) semantics `ReleaseRun` already relies on "
            "for Episode1Runner/Episode2Runner's real, randomly-generated per-run "
            "grant_ids, which are never surfaced back to ReleaseRun. Wiring it would "
            "either fabricate synthetic grants the crown never had, or spuriously "
            "NONCONFORMANT every real CROWNED run. The existing bare "
            "`ReplayEngine.verify_chain()` call (same underlying engine ReplayCourt "
            "wraps) is kept exactly as-is -- not weakened, not force-upgraded."
        ),
        "CHI-KNOWN-01 (ReplayCourt.verify_known_reflex_zero_inference)": (
            "Requires a KnowledgeHookEngine/ReactiveSemanticLoop reflex cycle; this "
            "crown's Episode1Runner/Episode2Runner never construct or invoke hooks."
        ),
        "AdmissionCourt (CHI-ADM-*/SA2A-SHEX-*/SA2A-SHACL-*/SA2A-SPARQL-*)": (
            "AdmissionCourt is a self-contained adversarial-attack suite that "
            "constructs its OWN fresh AdmissionPipeline per method against synthetic "
            "attack TTL payloads -- it does not consume this crown's own candidate/ "
            "admission evidence objects. Its 5 default SPARQL falsifiers ARE reused "
            "directly (not re-derived) via admission.falsifiers.FalsifierSuite in "
            "Gap 2's falsifier-corpus runner instead."
        ),
        "LogicHookCourt (CHI-AUTO-*, Datalog/N3/hook gates)": (
            "Requires DatalogEngine/N3RuleEngine/KnowledgeHookEngine/"
            "ReactiveSemanticLoop objects; this crown's Episode1Runner/Episode2Runner "
            "never construct any of them."
        ),
    }

    def _run_chicago_court_gates(
        self,
        *,
        journal_path: Path,
        receipt_store_dir: Path,
        action_iri: str,
        target_resource: str,
        episode2_candidate: CandidateResolution,
    ) -> dict[str, Any]:
        """Real, already-tested `ConsequenceCourt`/`AuthorityCourt` gates, composed
        (never re-derived) against THIS crown's own real journal/receipt-store infra
        (the exact `RealDiskJournalActuator`/`IndependentDiskJournalVerifier`/
        `DurableDiskReceiptStore` classes Episode1Runner/Episode2Runner already use)
        and THIS crown's own real action_iri/target_resource identity. Distinct
        actor/action/grant identities from Episode 1/Episode 2's own (never colliding
        with, never mutating, the crown's real episode receipts already on disk)."""
        gates: dict[str, Any] = {}

        # --- ConsequenceCourt: CHI-BRCE-01/02/03/04, CHI-POST-01, against the SAME
        # journal_path/receipt_store_dir the crown's own Episode1/Episode2 wrote to.
        consequence_court = ConsequenceCourt()
        audit_actor_id = "release-crown-consequence-audit"
        audit_action_iri = "urn:action:crown-consequence-audit"
        audit_target_resource = f"urn:audit:consequence:{self.work_dir.name}"
        audit_grant = AuthorityGrant(
            grant_id=f"grant-crown-audit-{uuid.uuid4().hex[:8]}",
            subject_id=audit_actor_id, action_iri=audit_action_iri, target_resource_iri=audit_target_resource,
        )
        consequence_broker = AuthorityBroker(grants=[audit_grant])
        receipt_store = DurableDiskReceiptStore(receipt_store_dir)
        audit_parameters = {"crown_audit": True}

        gates["CHI-BRCE-01-PREPARED-COMMIT"] = consequence_court.audit_prepared_commitment(
            broker=consequence_broker, receipt_store=receipt_store, journal_path=journal_path,
            actor_id=audit_actor_id, action_iri=audit_action_iri, target_resource=audit_target_resource,
            parameters=audit_parameters, idempotency_token=f"crown-audit-brce01-{uuid.uuid4().hex[:8]}",
        )
        gates["CHI-BRCE-02-BYPASS-PREVENTION"] = consequence_court.audit_bypass_prevention(
            broker=consequence_broker, receipt_store=receipt_store, journal_path=journal_path,
            actor_id=audit_actor_id, unauthorized_action_iri="urn:action:crown-consequence-audit-unauthorized",
            target_resource=audit_target_resource, parameters=audit_parameters,
            idempotency_token=f"crown-audit-brce02-{uuid.uuid4().hex[:8]}",
        )
        gates["CHI-BRCE-03-ANTI-COLLUSION"] = consequence_court.audit_anti_collusion(
            broker=consequence_broker,
            actuator=RealDiskJournalActuator(journal_path),
            verifier=IndependentDiskJournalVerifier(journal_path),
        )
        gates["CHI-POST-01-INDEPENDENT-OBSERVATION"] = consequence_court.audit_independent_postcondition_observation(
            broker=consequence_broker, receipt_store=receipt_store, journal_path=journal_path,
            actor_id=audit_actor_id, action_iri=audit_action_iri, target_resource=audit_target_resource,
            parameters=audit_parameters, idempotency_token=f"crown-audit-post01-{uuid.uuid4().hex[:8]}",
        )
        gates["CHI-BRCE-04-IDEMPOTENCY-REPLAY-REFUSAL"] = consequence_court.audit_idempotency_replay_refusal(
            broker=consequence_broker, receipt_store=receipt_store, journal_path=journal_path,
            actor_id=audit_actor_id, action_iri=audit_action_iri, target_resource=audit_target_resource,
            parameters=audit_parameters, idempotency_token=f"crown-audit-brce04-{uuid.uuid4().hex[:8]}",
        )

        # --- AuthorityCourt: SA2A-AUTH-*/CHI-PLAN-AUTH-*, against THIS crown's own
        # real action_iri/target_resource identity (the exact strings Episode 2
        # actuates), not a synthetic placeholder.
        authority_court = AuthorityCourt()
        auth_actor_id = "release-crown-authority-audit"
        gates["SA2A-AUTH-AGENT-NOT-AUTHORITY"] = authority_court.verify_agent_not_authority(
            AuthorityBroker(), auth_actor_id, action_iri, target_resource, fail_closed=False,
        )
        gates["SA2A-AUTH-PLAN-NOT-AUTHORITY"] = authority_court.verify_plan_not_authority(
            AuthorityBroker(), auth_actor_id, action_iri, target_resource, fail_closed=False,
        )
        gates["SA2A-AUTH-PROOF-NOT-AUTHORITY"] = authority_court.verify_proof_not_authority(
            AuthorityBroker(), auth_actor_id, action_iri, target_resource, fail_closed=False,
        )
        gates["SA2A-AUTH-CAPABILITY-NOT-AUTHORITY"] = authority_court.verify_capability_not_authority(
            AuthorityBroker(), auth_actor_id, action_iri, target_resource, fail_closed=False,
        )
        gates["SA2A-AUTH-GRANT-REQUIRED"] = authority_court.verify_grant_required_for_authorized(
            AuthorityBroker(), auth_actor_id, action_iri, target_resource, fail_closed=False,
        )
        gates["SA2A-AUTH-CONFUSED-DEPUTY"] = authority_court.verify_confused_deputy_prevented(
            broker=AuthorityBroker(), legitimate_actor_id=auth_actor_id,
            impersonating_actor_id=f"{auth_actor_id}-impersonator", action_iri=action_iri,
            target_resource=target_resource,
            grant=AuthorityGrant(
                grant_id=f"grant-crown-authority-audit-cd-{uuid.uuid4().hex[:8]}",
                subject_id=auth_actor_id, action_iri=action_iri, target_resource_iri=target_resource,
            ),
            fail_closed=False,
        )
        gates["CHI-PLAN-AUTH-TOKEN-REBINDING"] = authority_court.verify_token_rebinding_detected(
            broker=AuthorityBroker(), original_actor_id=auth_actor_id,
            rebound_actor_id=f"{auth_actor_id}-rebinder", action_iri=action_iri, target_resource=target_resource,
            grant=AuthorityGrant(
                grant_id=f"grant-crown-authority-audit-tr-{uuid.uuid4().hex[:8]}",
                subject_id=auth_actor_id, action_iri=action_iri, target_resource_iri=target_resource,
            ),
            fail_closed=False,
        )
        gates["SA2A-AUTH-LEGITIMATE-GRANT"] = authority_court.verify_legitimate_grant_authorized(
            broker=AuthorityBroker(),
            grant=AuthorityGrant(
                grant_id=f"grant-crown-authority-audit-legit-{uuid.uuid4().hex[:8]}",
                subject_id=auth_actor_id, action_iri=action_iri, target_resource_iri=target_resource,
            ),
            fail_closed=False,
        )
        # Real planner output (Episode 2's own fresh candidate), never a synthetic
        # stand-in: proves THIS crown's own candidate genuinely asserts no authority.
        candidate_payload = asdict(episode2_candidate) if is_dataclass(episode2_candidate) else episode2_candidate
        gates["CHI-PLAN-AUTH-PLANNER-NON-AUTHORITY"] = authority_court.verify_planner_non_authority(
            candidate_payload, fail_closed=False,
        )

        return gates

    @staticmethod
    def _load_receipt_records(receipt_store_dir: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if not receipt_store_dir.is_dir():
            return records
        for path in sorted(receipt_store_dir.glob("prep_*.json")) + sorted(receipt_store_dir.glob("final_*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return records

    @staticmethod
    def _run_fresh_consumer(
        state_dir: Path, episode1_id: str, episode2_id: str, *, timeout: float = 30.0
    ) -> dict[str, Any]:
        """Invokes the fresh-consumer verifier as a REAL, SEPARATE process (ARD §45) --
        never imported and called in-process, so producer in-memory state cannot leak.

        Hardening (2026-09-17): this call previously had no `timeout=` at all -- a
        hung `fresh_consumer.py` subprocess (e.g. triggered by a pathological state
        directory) would hang the entire `ReleaseRun.run()` call forever, since
        nothing here or in the caller ever interrupts `subprocess.run()`.
        `fresh_consumer.py` only does local file I/O (per its own docstring) so 30s is
        a generous bound, not a tight one -- a real timeout, distinguished from the
        already-handled `JSONDecodeError` path via its own typed verdict prefix.
        """
        try:
            result = subprocess.run(
                [sys.executable, "-m", "autofde_lab.sa2a.release.fresh_consumer", str(state_dir), episode1_id, episode2_id],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"verdict": f"UNKNOWN:SUBPROCESS_TIMEOUT:exceeded {timeout}s"}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"verdict": f"UNKNOWN:SUBPROCESS_OUTPUT_UNPARSEABLE:{result.stderr[:200]}"}
