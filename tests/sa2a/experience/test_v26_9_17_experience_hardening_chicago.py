"""Chicago-style adversarial regression tests for the 2026-09-17 QUALIFICATION-mode
hardening pass over the compile -> admit -> qualify -> known-route lifecycle
(v26.9.17 PRD/ARD, `experience/` package).

Each test pins ONE real bug found by adversarial attack (not fuzzing) and fixed the
same session, OR confirms a suspected edge case already behaves correctly. Real
collaborators throughout -- real CandidateResolution/AdmissionReceipt/
CompiledDeterministicRule objects, real ExperienceCompiler/ExperienceAdmissionGate/
ExperienceQualifier/KnownRouteRegistry instances, real state-based assertions. Zero
mocks.
"""

from __future__ import annotations

import time

from autofde_lab.sa2a.experience.admission import ExperienceAdmissionGate
from autofde_lab.sa2a.experience.compiler import ArtifactRegistry, EpisodeEvidence, ExperienceCompiler
from autofde_lab.sa2a.experience.invalidation import check_and_invalidate
from autofde_lab.sa2a.experience.known_route import KnownRoute, KnownRouteRegistry
from autofde_lab.sa2a.experience.qualification import REFUSED_ALREADY_QUALIFIED, ExperienceQualifier
from autofde_lab.sa2a.experience.types import ExperienceState, MachineExperience
from autofde_lab.sa2a.unknown.compilation import CompiledDeterministicRule
from autofde_lab.sa2a.unknown.resolution import AdmissionReceipt, CandidateResolution, EpistemicState


def _admitted_candidate(candidate_id: str = "cand-h1", query_id: str = "q-h1") -> tuple[CandidateResolution, AdmissionReceipt]:
    candidate = CandidateResolution(
        candidate_id=candidate_id, query_id=query_id, proposed_assertion="service:api-gateway requires-port",
        evidence_payload={"source": "formal-port-probe"}, source_identity="formal-port-probe",
        consumed_ticks=2, consumed_tokens=0,
    )
    receipt = AdmissionReceipt(
        receipt_id=f"rec-{candidate_id}", candidate_hash=candidate.candidate_hash, admitted=True,
        epistemic_standing=EpistemicState.KNOWN, reasons=("CONFORMS_TO_SPEC",),
        admitted_assertion=candidate.proposed_assertion,
    )
    return candidate, receipt


# --- 2.1: ExperienceCompiler.compile() vs. a non-JSON-serializable evidence_payload ---


def test_compile_refuses_typed_valueerror_when_candidate_hash_cannot_be_computed() -> None:
    """Adversarial: `CandidateResolution.candidate_hash` (owned by
    unknown/resolution.py) JSON-dumps `evidence_payload` -- a field typed
    `Mapping[str, Any]` with no serializability constraint. Confirmed live
    pre-fix: a candidate whose evidence_payload holds a `set` made
    `ExperienceCompiler.compile()` itself raise a raw, uncaught `TypeError` (at
    its own hash-consistency check, `admitted_solution.candidate_hash`) rather
    than the typed `ValueError` refusal compile() uses for every other
    provenance-integrity failure. compile() must now convert that into the same
    typed ValueError family, never let a raw TypeError escape its own boundary."""
    candidate = CandidateResolution(
        candidate_id="cand-nonserializable", query_id="q-1", proposed_assertion="x",
        evidence_payload={"weird": {1, 2, 3}},  # a set: json.dumps cannot serialize this
        source_identity="probe", consumed_ticks=1, consumed_tokens=0,
    )
    # A hand-constructed receipt whose candidate_hash was NOT derived by calling
    # candidate.candidate_hash (a caller using a custom, non-default admission
    # court that never touches the property) -- so the ONLY place the property
    # gets evaluated is inside compile() itself.
    receipt = AdmissionReceipt(
        receipt_id="rec-1", candidate_hash="precomputed-not-from-property", admitted=True,
        epistemic_standing=EpistemicState.KNOWN, reasons=("OK",), admitted_assertion="x",
    )
    compiler = ExperienceCompiler()
    try:
        compiler.compile(
            semantic_class_id="c", admitted_solution=candidate, admission_receipt=receipt,
            episode_evidence=EpisodeEvidence(episode_id="ep1", discovery_identity="probe", discovery_resource_receipt="r"),
            equivalence_predicate_id="pred-1",
        )
        assert False, "compile() must refuse cleanly, never crash with a raw TypeError"
    except ValueError as exc:
        assert "JSON-serializable" in str(exc)
        assert "cand-nonserializable" in str(exc)


def test_compile_succeeds_for_a_genuinely_json_serializable_evidence_payload() -> None:
    """Non-adversarial control: the guard above must not reject ordinary,
    serializable evidence -- only the genuinely unserializable case."""
    candidate, receipt = _admitted_candidate()
    compiler = ExperienceCompiler()
    experience = compiler.compile(
        semantic_class_id="requires-port", admitted_solution=candidate, admission_receipt=receipt,
        episode_evidence=EpisodeEvidence(episode_id="ep1", discovery_identity="probe", discovery_resource_receipt="r"),
        equivalence_predicate_id="pred-1",
    )
    assert experience.state == ExperienceState.CANDIDATE
    assert experience.source_candidate_digest == candidate.candidate_hash


# --- 2.2: ExperienceQualifier.qualify() called twice on the same ADMITTED experience ---


def test_qualify_called_twice_on_same_admitted_object_refuses_second_call_not_a_silent_double_registration() -> None:
    """Adversarial: MachineExperience is immutable, so `with_state()` never
    mutates the caller's reference -- calling qualify() a second time with the
    SAME still-ADMITTED object passes qualify()'s own `state == ADMITTED` check
    both times. Confirmed live pre-fix: this silently registered TWO separate
    ACTIVE KnownRoutes for the SAME experience_id under two different route_ids,
    with no error anywhere. Must now refuse the second call with a typed
    REFUSED_EXPERIENCE_ALREADY_QUALIFIED result and leave exactly one ACTIVE
    route registered."""
    candidate, receipt = _admitted_candidate()
    compiler = ExperienceCompiler()
    experience = compiler.compile(
        semantic_class_id="requires-port", admitted_solution=candidate, admission_receipt=receipt,
        episode_evidence=EpisodeEvidence(episode_id="ep1", discovery_identity="probe", discovery_resource_receipt="r"),
        equivalence_predicate_id="pred-1",
    )
    gate = ExperienceAdmissionGate(compiler.artifact_registry)
    admitted = gate.admit(experience)
    assert admitted.admitted

    routes = KnownRouteRegistry()
    qualifier = ExperienceQualifier(compiler.artifact_registry, routes)

    result1 = qualifier.qualify(admitted.experience, equivalence_predicate=lambda c: True, probe_input="requires-port")
    result2 = qualifier.qualify(admitted.experience, equivalence_predicate=lambda c: True, probe_input="requires-port")

    assert result1.qualified
    assert not result2.qualified
    assert result2.refusal_code == REFUSED_ALREADY_QUALIFIED

    active_routes = [r for r in routes.routes_for_class("requires-port") if r.state == "ACTIVE"]
    assert len(active_routes) == 1, "exactly one ACTIVE route must survive a repeated qualify() call"
    assert active_routes[0].route_id == result1.known_route.route_id


def test_known_route_registry_allows_requalification_after_invalidation() -> None:
    """Control: the duplicate guard must be scoped to ACTIVE routes for the SAME
    experience_id, never block the lawful INVALIDATED -> requalify -> new ACTIVE
    route cycle ARD §12 requires."""
    candidate, receipt = _admitted_candidate()
    compiler = ExperienceCompiler()
    experience = compiler.compile(
        semantic_class_id="requires-port", admitted_solution=candidate, admission_receipt=receipt,
        episode_evidence=EpisodeEvidence(episode_id="ep1", discovery_identity="probe", discovery_resource_receipt="r"),
        equivalence_predicate_id="pred-1", invalidation_set={"ontology_digest": "v1"},
    )
    gate = ExperienceAdmissionGate(compiler.artifact_registry)
    admitted = gate.admit(experience)
    routes = KnownRouteRegistry()
    qualifier = ExperienceQualifier(compiler.artifact_registry, routes)
    first = qualifier.qualify(admitted.experience, equivalence_predicate=lambda c: True, probe_input="requires-port")
    assert first.qualified

    invalidation = check_and_invalidate(first.experience, {"ontology_digest": "v2"}, routes)
    assert invalidation.invalidated
    # Requalification re-enters at ADMITTED (types.py's own transition table).
    re_admitted = invalidation.experience.with_state(ExperienceState.ADMITTED)
    second = qualifier.qualify(re_admitted, equivalence_predicate=lambda c: True, probe_input="requires-port")
    assert second.qualified, second.reasons
    assert second.known_route.route_id != first.known_route.route_id

    active_routes = [r for r in routes.routes_for_class("requires-port") if r.state == "ACTIVE"]
    assert len(active_routes) == 1
    assert active_routes[0].route_id == second.known_route.route_id


# --- 2.3: KnownRouteRegistry.lookup() timing at 1000+ routes across 50+ classes ---


def test_lookup_timing_scales_with_routes_in_the_target_class_not_total_routes() -> None:
    """Real timing check (not a strict wall-clock pass/fail): register 1050 routes
    across 50 semantic classes (21 routes each), then confirm lookup() against one
    class stays fast regardless of how many OTHER classes/routes exist -- the
    dict-of-lists structure means lookup() only ever iterates
    `_routes_by_class[semantic_class_id]`, never the full registry. Reports real
    wall-clock numbers; the only assertion is a generous upper bound (guards
    against an accidental O(all routes) regression, not a tight perf budget)."""
    routes = KnownRouteRegistry()
    n_classes = 50
    routes_per_class = 21  # 1050 total, comfortably over the task's "1000+" bar

    def _accept_everything(_candidate: object) -> bool:
        return False  # never matches -- forces lookup() to scan every route in the class

    for class_idx in range(n_classes):
        class_id = f"semantic-class-{class_idx}"
        predicate_id = f"pred-{class_id}"
        routes.register_predicate(predicate_id, _accept_everything)
        for route_idx in range(routes_per_class):
            routes.register_route(
                KnownRoute(
                    route_id=f"route-{class_id}-{route_idx}", semantic_class_id=class_id,
                    experience_id=f"exp-{class_id}-{route_idx}", equivalence_predicate_id=predicate_id,
                    required_preconditions=(), planner_or_policy_identity="p", manufacturer_identity="m",
                    expected_capabilities=(), resource_envelope={"max_probe_calls": 1},
                    qualification_receipt=f"rcpt-{class_id}-{route_idx}", state="ACTIVE",
                )
            )

    total_routes = sum(
        len(routes.routes_for_class(f"semantic-class-{i}")) for i in range(n_classes)
    )  # via the public API, not private state
    assert total_routes == n_classes * routes_per_class == 1050

    n_lookups = 500
    start = time.perf_counter()
    for _ in range(n_lookups):
        result = routes.lookup("semantic-class-25", "anything")
    elapsed = time.perf_counter() - start
    per_lookup_us = (elapsed / n_lookups) * 1_000_000

    print(
        f"\n[timing] {n_lookups} lookups against one class (of {n_classes} classes, "
        f"{total_routes} routes total, {routes_per_class} routes in the target class): "
        f"{elapsed:.4f}s total, {per_lookup_us:.2f}us/lookup"
    )
    assert result is None  # the always-False predicate means UNKNOWN is the correct outcome
    # Generous bound: each lookup scans at most routes_per_class (21) entries, not
    # all 1050 -- even a slow interpreter should clear 500 such lookups well under
    # a second. This is a regression guard against O(all routes ever registered),
    # not a performance target.
    assert elapsed < 2.0, f"lookup() took {elapsed:.3f}s for {n_lookups} calls -- looks O(all routes), not O(class)"


# --- 2.4: is_invalidated_by() / check_and_invalidate() with an EMPTY current_digests ---


def test_empty_current_digests_against_a_nonempty_invalidation_set_reports_invalidated() -> None:
    """Confirmed ALREADY CORRECT (read MachineExperience.is_invalidated_by()'s exact
    comparison, `current_digests.get(key) != expected`): with an EMPTY
    current_digests dict, `.get(key)` returns None for every declared dependency,
    and `None != expected` is True for every real digest string -- so an empty
    snapshot of current digests against a non-empty invalidation_set correctly
    reports invalidated=True with EVERY tracked dependency listed as changed. This
    is the fail-closed reading required by `.claude/rules/absence-is-not-evidence.md`:
    absence of current evidence about a dependency is treated as "changed," never
    silently coerced into "unchanged." No code change was needed; this test pins
    the behavior as a permanent regression guard."""
    candidate, receipt = _admitted_candidate()
    compiler = ExperienceCompiler()
    experience = compiler.compile(
        semantic_class_id="requires-port", admitted_solution=candidate, admission_receipt=receipt,
        episode_evidence=EpisodeEvidence(episode_id="ep1", discovery_identity="probe", discovery_resource_receipt="r"),
        equivalence_predicate_id="pred-1", invalidation_set={"ontology_digest": "v1", "rule_digest": "v2"},
    )
    gate = ExperienceAdmissionGate(compiler.artifact_registry)
    admitted = gate.admit(experience)
    routes = KnownRouteRegistry()
    qualifier = ExperienceQualifier(compiler.artifact_registry, routes)
    qualified = qualifier.qualify(admitted.experience, equivalence_predicate=lambda c: True, probe_input="requires-port")
    assert qualified.qualified

    invalidated, changed = qualified.experience.is_invalidated_by({})
    assert invalidated is True
    assert set(changed) == {"ontology_digest", "rule_digest"}

    result = check_and_invalidate(qualified.experience, {}, routes)
    assert result.invalidated
    assert result.experience.state == ExperienceState.INVALIDATED
    route = [r for r in routes.routes_for_class("requires-port") if r.route_id == qualified.known_route.route_id][0]
    assert route.state == "INVALIDATED"


def test_empty_invalidation_set_is_never_invalidated_by_an_empty_current_digests() -> None:
    """Boundary control for the same comparison: an experience that declared NO
    dependencies (empty invalidation_set) has nothing to check -- an empty
    current_digests must not spuriously invalidate it. `is_invalidated_by`'s
    generator iterates `self.invalidation_set.items()`, so an empty
    invalidation_set yields zero comparisons regardless of current_digests."""
    exp = MachineExperience(
        experience_id="e1", semantic_class_id="c1", source_episode_id="ep1", source_candidate_digest="d1",
        source_admission_receipt="r1", discovery_identity="di", discovery_resource_receipt="dr",
        solution_candidate_digest="d1", solution_admission_receipt="r1", compiled_artifact_ids=("a1",),
        equivalence_predicate_id="p1", invalidation_set={}, state=ExperienceState.ACTIVE,
    )
    invalidated, changed = exp.is_invalidated_by({})
    assert invalidated is False
    assert changed == ()


# --- 2.5: ArtifactRegistry.store() on a genuine rule_id collision ---


def test_artifact_registry_store_refuses_a_genuine_rule_id_collision() -> None:
    """Adversarial: `rule_id` is `sha256(candidate_id)[:12]` -- 48 bits of a
    content-addressed digest, not a guaranteed-unique identity. Confirmed live
    pre-fix: storing a SECOND, genuinely different CompiledDeterministicRule under
    an already-occupied rule_id silently overwrote the first with no detection --
    which would corrupt requalification for any MachineExperience already admitted
    against the original artifact (ExperienceQualifier re-reads by rule_id on every
    qualify() call). store() must now refuse a genuine collision."""
    registry = ArtifactRegistry()
    rule_a = CompiledDeterministicRule(rule_id="rule_collision01", pattern="pattern-A", deterministic_output="output-A", fingerprint="fpA")
    rule_b = CompiledDeterministicRule(rule_id="rule_collision01", pattern="pattern-B", deterministic_output="output-B", fingerprint="fpB")
    registry.store(rule_a)
    try:
        registry.store(rule_b)
        assert False, "store() must refuse a genuine key collision with different content, never silently overwrite"
    except ValueError as exc:
        assert "rule_collision01" in str(exc)
    # The original artifact must survive the refused collision untouched.
    assert registry.get("rule_collision01") == rule_a


def test_artifact_registry_store_is_idempotent_for_byte_identical_content() -> None:
    """Control: a retry storing the EXACT same artifact (same rule_id, same every
    field) under the same key must NOT be refused -- only a genuine content
    mismatch under a shared key is a real collision."""
    registry = ArtifactRegistry()
    rule = CompiledDeterministicRule(rule_id="rule_idempotent", pattern="pattern-A", deterministic_output="output-A", fingerprint="fpA")
    registry.store(rule)
    registry.store(rule)  # same object, same content -- must not raise
    rule_again = CompiledDeterministicRule(rule_id="rule_idempotent", pattern="pattern-A", deterministic_output="output-A", fingerprint="fpA")
    registry.store(rule_again)  # different object, byte-identical content -- must not raise
    assert registry.get("rule_idempotent") == rule
