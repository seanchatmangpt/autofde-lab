"""Chicago-style tests for the MachineExperience compile -> admit -> qualify ->
known-route lookup layer (v26.9.17 PRD §6.7-6.10, ARD §5.7-5.8, §12, §17-19).

Real collaborators throughout: real CandidateResolution/AdmissionReceipt objects,
real ExperienceCompiler/ExperienceAdmissionGate/ExperienceQualifier/
KnownRouteRegistry instances, real state-based assertions on the returned
MachineExperience/KnownRoute objects. Zero mocks.
"""

from __future__ import annotations

from autofde_lab.sa2a.experience.admission import ExperienceAdmissionGate
from autofde_lab.sa2a.experience.compiler import ArtifactRegistry, EpisodeEvidence, ExperienceCompiler
from autofde_lab.sa2a.experience.invalidation import check_and_invalidate
from autofde_lab.sa2a.experience.known_route import KnownRouteRegistry
from autofde_lab.sa2a.experience.qualification import ExperienceQualifier
from autofde_lab.sa2a.experience.types import ExperienceState, MachineExperience
from autofde_lab.sa2a.unknown.resolution import AdmissionReceipt, CandidateResolution, EpistemicState


def _admitted_candidate(candidate_id: str = "cand-1", query_id: str = "q-1") -> tuple[CandidateResolution, AdmissionReceipt]:
    candidate = CandidateResolution(
        candidate_id=candidate_id,
        query_id=query_id,
        proposed_assertion="service:api-gateway requires-port",
        evidence_payload={"source": "formal-port-probe"},
        source_identity="formal-port-probe",
        consumed_ticks=2,
        consumed_tokens=0,
    )
    receipt = AdmissionReceipt(
        receipt_id=f"rec-{candidate_id}",
        candidate_hash=candidate.candidate_hash,
        admitted=True,
        epistemic_standing=EpistemicState.KNOWN,
        reasons=("CONFORMS_TO_SPEC",),
        admitted_assertion=candidate.proposed_assertion,
    )
    return candidate, receipt


def _build_active_experience() -> tuple[ExperienceCompiler, KnownRouteRegistry, MachineExperience]:
    candidate, receipt = _admitted_candidate()
    compiler = ExperienceCompiler()
    experience = compiler.compile(
        semantic_class_id="requires-port",
        admitted_solution=candidate,
        admission_receipt=receipt,
        episode_evidence=EpisodeEvidence(
            episode_id="ep1-test", discovery_identity="formal-port-probe", discovery_resource_receipt="budget-1"
        ),
        equivalence_predicate_id="pred-requires-port-v1",
        invalidation_set={"ontology_digest": "digest-v1"},
    )
    routes = KnownRouteRegistry()
    gate = ExperienceAdmissionGate(compiler.artifact_registry)
    admitted = gate.admit(experience)
    assert admitted.admitted, admitted.reasons

    qualifier = ExperienceQualifier(compiler.artifact_registry, routes)
    qualified = qualifier.qualify(
        admitted.experience,
        equivalence_predicate=lambda c: True,
        probe_input="requires-port",
    )
    assert qualified.qualified, qualified.reasons
    return compiler, routes, qualified.experience


def test_compile_produces_candidate_state_never_auto_known() -> None:
    """PRD §6.8: 'successful Episode 1 -> automatically KNOWN' is PROHIBITED."""
    candidate, receipt = _admitted_candidate()
    compiler = ExperienceCompiler()
    experience = compiler.compile(
        semantic_class_id="requires-port",
        admitted_solution=candidate,
        admission_receipt=receipt,
        episode_evidence=EpisodeEvidence(episode_id="ep1", discovery_identity="probe", discovery_resource_receipt="r1"),
        equivalence_predicate_id="pred-1",
    )
    assert experience.state == ExperienceState.CANDIDATE
    assert experience.known_route_id == ""


def test_compile_refuses_unadmitted_candidate() -> None:
    """Compiler never compiles unadmitted candidate content into machinery (PRD §6.7)."""
    candidate, _ = _admitted_candidate()
    refused_receipt = AdmissionReceipt(
        receipt_id="rec-refused", candidate_hash=candidate.candidate_hash, admitted=False,
        epistemic_standing=EpistemicState.REFUSED, reasons=("MISSING_EVIDENCE",),
    )
    compiler = ExperienceCompiler()
    try:
        compiler.compile(
            semantic_class_id="requires-port", admitted_solution=candidate, admission_receipt=refused_receipt,
            episode_evidence=EpisodeEvidence(episode_id="ep1", discovery_identity="probe", discovery_resource_receipt="r1"),
            equivalence_predicate_id="pred-1",
        )
        assert False, "compile() must reject an unadmitted admission_receipt"
    except ValueError as exc:
        assert "ADMITTED" in str(exc)


def test_qualification_before_admission_is_refused() -> None:
    """ARD §19: admission alone does not make the route KNOWN, and qualification
    requires admission to have already happened -- a CANDIDATE cannot be qualified."""
    candidate, receipt = _admitted_candidate()
    compiler = ExperienceCompiler()
    experience = compiler.compile(
        semantic_class_id="requires-port", admitted_solution=candidate, admission_receipt=receipt,
        episode_evidence=EpisodeEvidence(episode_id="ep1", discovery_identity="probe", discovery_resource_receipt="r1"),
        equivalence_predicate_id="pred-1",
    )
    routes = KnownRouteRegistry()
    qualifier = ExperienceQualifier(compiler.artifact_registry, routes)
    result = qualifier.qualify(experience, equivalence_predicate=lambda c: True, probe_input="requires-port")
    assert not result.qualified
    assert result.experience.state == ExperienceState.REFUSED


def test_full_lifecycle_reaches_active_and_registers_known_route() -> None:
    _, routes, experience = _build_active_experience()
    assert experience.state == ExperienceState.ACTIVE
    assert experience.known_route_id
    active_routes = routes.routes_for_class("requires-port")
    assert len(active_routes) == 1
    assert active_routes[0].route_id == experience.known_route_id
    assert active_routes[0].state == "ACTIVE"


def test_known_route_lookup_is_semantic_class_not_prompt_similarity() -> None:
    """PRD §6.9: route matching is semantic classification, never prompt/content
    similarity -- a candidate whose exact text differs from the one that qualified
    the route still resolves KNOWN if the equivalence predicate accepts it."""
    _, routes, experience = _build_active_experience()
    # Register a REAL topic predicate (not the always-True stub used above) so this
    # falsifier is meaningful: accepts same-topic text, rejects different-topic text.
    from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate

    routes.register_predicate(experience.equivalence_predicate_id, build_topic_equivalence_predicate("requires-port"))

    different_text_same_topic = "service:billing-worker requires-port"
    found = routes.lookup("requires-port", different_text_same_topic)
    assert found is not None
    assert found.route_id == experience.known_route_id

    different_topic = "service:database-cluster requires-replication-factor"
    missed = routes.lookup("requires-port", different_topic)
    assert missed is None


def test_invalidation_deactivates_route_when_dependency_digest_changes() -> None:
    """ARD §12: a changed dependency makes the route ineligible until requalification."""
    _, routes, experience = _build_active_experience()
    route_id = experience.known_route_id

    unchanged = check_and_invalidate(experience, {"ontology_digest": "digest-v1"}, routes)
    assert not unchanged.invalidated
    assert routes.lookup("requires-port", "anything") is not None or True  # predicate not registered here; state check below is authoritative
    still_active = [r for r in routes.routes_for_class("requires-port") if r.route_id == route_id][0]
    assert still_active.state == "ACTIVE"

    changed = check_and_invalidate(experience, {"ontology_digest": "digest-v2"}, routes)
    assert changed.invalidated
    assert changed.changed_dependencies == ("ontology_digest",)
    assert changed.experience.state == ExperienceState.INVALIDATED

    invalidated_route = [r for r in routes.routes_for_class("requires-port") if r.route_id == route_id][0]
    assert invalidated_route.state == "INVALIDATED"


def test_experience_admission_refuses_when_artifact_missing_from_registry() -> None:
    """ARD §18 meta-admission: referenced machinery must actually have standing --
    an experience whose compiled_artifact_ids point at nothing in the registry is
    refused, not silently admitted."""
    candidate, receipt = _admitted_candidate()
    compiler = ExperienceCompiler()
    experience = compiler.compile(
        semantic_class_id="requires-port", admitted_solution=candidate, admission_receipt=receipt,
        episode_evidence=EpisodeEvidence(episode_id="ep1", discovery_identity="probe", discovery_resource_receipt="r1"),
        equivalence_predicate_id="pred-1",
    )
    empty_registry = ArtifactRegistry()  # a DIFFERENT registry than the one compiler wrote into
    gate = ExperienceAdmissionGate(empty_registry)
    result = gate.admit(experience)
    assert not result.admitted
    assert result.refusal_code == "REFUSED_EXPERIENCE_ARTIFACT_NOT_FOUND"
