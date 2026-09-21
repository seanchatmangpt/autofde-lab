"""AFDE-2612 / A2A-2612 Chicago falsifier #2, exercised directly.

Upstream Chicago falsifier #2 (`A2A-2612-machine-experience-compile-back.md`):
    "An admitted promotion creates a new deterministic route and the next
    matching episode makes zero LLM calls."

`tests/sa2a/test_autonomic_closed_loop_lifecycle.py` (read in full before writing this
file) demonstrates promotion (Cycle 0 -> Lab -> hook synthesis -> registration) followed
by exactly ONE reflex cycle (Cycle 1). It never submits a SECOND, later episode after
promotion, and its zero-inference claim for Cycle 1
(``runtime_tokens_cycle1 = 0``, line 192) is a hardcoded literal asserted less than
another hardcoded literal (``lab_tokens_spent = 2500``) -- no call site is instrumented
or counted anywhere in that test. So the existing test proves promotion and one reflex
firing; it does not prove the falsifier's actual claim, which is specifically about the
*next* episode after the one that caused promotion.

This file closes that gap with a real, counted measurement: it wraps the real
``HookSynthesizer`` and the real ``KnowledgeHookEngine`` in trivial counting subclasses
(real objects, real delegation to the real parent implementation -- not
``unittest.mock``/``Mock``/interaction verification; the counters are read as final
state, the same way ``MockClusterActuator.restarted_pods`` is read as final state in the
existing lifecycle test) and asserts on the real resulting call counts after a second,
matching episode -- never on "was synthesize_from_resolution called," only on the real
integer it left behind.

Per ``.claude/rules/ecosystem-boundary.md`` this exercises only this repo's local
``sa2a/`` testbed. Nothing here is, or is claimed to be, the ecosystem
admission/broker/actuation authority ``mfw`` owns.

Local closure fix (this pass): the first session's closure notes (see
``docs/jira/v26.9.16/AFDE-2612-machine-experience-compile-back-closure.md``, "2026-09-16
-- Chicago falsifier #2" entry) named a real, confirmed gap: ``KnowledgeHookEngine``'s
local Python fallback (``hooks/engine.py``, used whenever the WASM verdict lookup misses
a hook's IRI -- which is every synthesized hook, since ``condition_query`` was never
populated and no synthesized hook's GraphLaw rule was ever merged into the graph
``run_hooks`` evaluates) fired ANY registered ``ASSERT`` hook on ANY non-empty event
delta, with zero content check. ``KnowledgeHookDefinition`` now carries real
``trigger_predicate``/``trigger_value`` fields (populated by ``HookSynthesizer`` from
the exact values it already received), and the local fallback in ``hooks/engine.py``
requires the event delta to actually contain a triple matching those fields before
firing. ``test_second_matching_episode_via_reflex_loop_makes_zero_further_synthesis_calls``
below still passes -- because episode 2 genuinely re-asserts the SAME
``ex:status 'CRASH_LOOP'`` pattern episode 1 was promoted from, not because the fallback
is content-blind anymore. ``test_unrelated_event_does_not_fire_promoted_hook`` is the new
falsifier this fix makes possible: submitting an event with no relation to the promoted
hook's trigger condition through the same real reflex loop now measurably does NOT fire
it -- the exact gap the prior session's ad hoc, non-committed check (documented in the
closure notes but never added as a pytest test) identified as missing.
"""

from __future__ import annotations

from datetime import datetime, timezone

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline, AdmissionResult
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker
from autofde_lab.sa2a.brce.boundary import (
    BoundaryExecutionResult,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.reactive_loop import ReactiveSemanticLoop
from autofde_lab.sa2a.hooks.synthesis import HookSynthesizer, SynthesizedHookArtifact
from autofde_lab.sa2a.unknown.novelty_ingest import NoveltyIngestionGateway

# AFDE-2604 fail-secure closure (2026-09-17, applied to this file): ConsequenceBoundary's
# `require_admission` class-level default flipped False -> True, and
# ReactiveSemanticLoop's `admission_pipeline` now defaults to a real, constructed
# `AdmissionPipeline()` when omitted (see boundary.py/reactive_loop.py). Admission is
# INCIDENTAL to what this file actually falsifies (repeat-episode zero-inference), so
# every envelope/reflex-cycle below is wired with a real, valid, Standing.ADMITTED
# AdmissionResult -- never `require_admission=False`/`admission_pipeline=None` -- so
# each test still reaches the exact code path (grant check, hook firing, actuation) it
# always exercised, now behind the real admission fence this repo actually enforces.


def _admitted_result(
    action_iri: str, target_resource: str, actor_id: str
) -> AdmissionResult:
    """Construct a real, valid, Standing.ADMITTED AdmissionResult binding `action_iri`
    to `target_resource` via the real `urn:autofde-lab:targetResource` predicate
    `ConsequenceBoundary._admission_covers_action_target()` requires (boundary.py).

    Real `AdmissionPipeline().admit()` call against real Turtle content -- not a mock:
    the default pipeline's real Identity/Provenance/Meta-Admission stages all run for
    real against this content, and a genuinely malformed/unbound candidate would be
    genuinely REFUSED here (the `assert` below is a real check, not decoration).
    """
    pipeline = AdmissionPipeline()
    ttl = (
        "@prefix afl: <urn:autofde-lab:> .\n"
        f"<{action_iri}> afl:targetResource <{target_resource}> .\n"
    )
    admitted = pipeline.admit(
        ttl,
        provenance_record={
            "issuer": actor_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert admitted.standing == Standing.ADMITTED, (
        f"real AdmissionPipeline().admit() unexpectedly refused a well-formed "
        f"targetResource-binding candidate: {admitted.refusal_code} {admitted.reasons}"
    )
    return admitted


class RealClusterActuator:
    """Real actuator with real, observable state.

    Not a mock: no call is ever asserted against; only the ``restarted_pods`` list this
    object actually appends to is read afterward, exactly like
    ``MockClusterActuator.restarted_pods`` in the existing closed-loop lifecycle test.
    """

    def __init__(self) -> None:
        self.restarted_pods: list[str] = []

    def actuate(self, action_iri: str, target_resource: str, parameters: dict) -> dict:
        pod = parameters.get("pod_id", "unknown-pod")
        self.restarted_pods.append(pod)
        return {"restarted": True, "pod_id": pod, "action": action_iri}

    def actuator_digest(self) -> str:
        return "actuator:k8s:v1"


class RealClusterVerifier:
    """Real, independent postcondition verifier (distinct object from the actuator)."""

    def verify_postcondition(
        self,
        action_iri: str,
        target_resource: str,
        parameters: dict,
        evidence: dict | None,
    ) -> bool:
        return evidence is not None and evidence.get("restarted") is True

    def verifier_digest(self) -> str:
        return "verifier:k8s:v1"


class CountingHookSynthesizer(HookSynthesizer):
    """Real ``HookSynthesizer`` subclass that counts real invocations.

    Every call is delegated to the real parent implementation -- the returned
    ``SynthesizedHookArtifact`` is the real one, never a canned/faked value. The counter
    is the only thing this subclass adds, and it is read as final integer state, not
    asserted as "was called."
    """

    def __init__(self) -> None:
        super().__init__()
        self.call_count = 0

    def synthesize_from_resolution(self, **kwargs) -> SynthesizedHookArtifact:
        self.call_count += 1
        return super().synthesize_from_resolution(**kwargs)


class CountingHookEngine(KnowledgeHookEngine):
    """Real ``KnowledgeHookEngine`` subclass that counts real ``.evaluate()`` calls."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.evaluate_call_count = 0

    def evaluate(self, *args, **kwargs):
        self.evaluate_call_count += 1
        return super().evaluate(*args, **kwargs)


def _run_first_episode_and_promote(
    *,
    boundary: ConsequenceBoundary,
    gateway: NoveltyIngestionGateway,
    synthesizer: CountingHookSynthesizer,
    actor_id: str,
    action_iri: str,
    target_cap: str,
    idempotency_token: str,
    pod_id: str,
    hook_name: str,
) -> SynthesizedHookArtifact:
    """Run ONE real UNKNOWN episode through the real promotion path used by the
    existing closed-loop lifecycle test: refuse (no grant) -> ingest into the Lab
    candidate frontier -> synthesize a hook + grant. Returns the real artifact; the
    caller registers it into the production hook engine / authority broker.

    AFDE-2604 fail-secure closure: `boundary` is constructed with the class default
    `require_admission=True`, so this envelope carries a real, valid, Standing.ADMITTED
    `AdmissionResult` binding `action_iri` to `target_cap` -- otherwise `boundary.execute`
    would refuse `REFUSED_NOT_ADMITTED` before ever reaching the grant check this
    episode is actually meant to exercise (no grant has been registered yet).
    """
    envelope = ExecutionEnvelope(
        idempotency_token=idempotency_token,
        action_iri=action_iri,
        target_resource=target_cap,
        parameters={"pod_id": pod_id},
        actor_id=actor_id,
        admission_result=_admitted_result(action_iri, target_cap, actor_id),
    )
    result: BoundaryExecutionResult = boundary.execute(envelope)
    assert result.success is False
    assert result.state == TerminalReceiptState.REFUSED
    assert result.refusal_code == "REFUSED_NO_GRANT"

    candidate = gateway.ingest_refusal_receipt(
        result.final_receipt,
        action_iri=action_iri,
        target_resource=target_cap,
        observed_state_ttl="@prefix ex: <http://example.org/> . ex:pod ex:status 'CRASH_LOOP' .",
        parameters={"pod_id": pod_id},
    )
    assert candidate.item_id.startswith("novelty-")

    artifact = synthesizer.synthesize_from_resolution(
        hook_name=hook_name,
        trigger_predicate="ex:status",
        trigger_value="CRASH_LOOP",
        action_iri=action_iri,
        target_capability_iri=target_cap,
        goal_iri="urn:goal:cluster_stabilized",
        authorized_actor=actor_id,
    )
    return artifact


def test_second_matching_episode_via_reflex_loop_makes_zero_further_synthesis_calls():
    """The falsifier as literally stated, exercised via ``ReactiveSemanticLoop`` -- the
    only local code path that actually consults ``KnowledgeHookEngine``.

    Episode 1: novel incident, refused, ingested, synthesized, promoted (registered
    hook + grant) -- exactly the existing lifecycle test's Cycle 0 -> Lab pipeline.
    Episode 2: a SECOND, matching incident (same action/target/actor, same
    trigger-predicate content), submitted through ``ReactiveSemanticLoop.run_reflex_cycle``.

    Real, counted result asserted: ``HookSynthesizer.synthesize_from_resolution`` is
    called exactly once in total (episode 1 only); episode 2 fires the promoted hook and
    produces a real EXECUTED receipt with zero additional synthesis calls.

    Post AFDE-2612 local fix, this now holds for the right reason: episode 2's delta
    (``ex:pod ex:status 'CRASH_LOOP'``) genuinely matches the promoted hook's own
    ``trigger_predicate``/``trigger_value`` (``ex:status`` / ``CRASH_LOOP``, the exact
    values episode 1's promotion was synthesized from), which
    ``KnowledgeHookEngine.evaluate``'s local fallback now checks for real before firing
    -- not because that fallback fires on any non-empty delta regardless of content (the
    pre-fix behavior; see ``test_unrelated_event_does_not_fire_promoted_hook`` below for
    the falsifier proving the old, content-blind behavior no longer holds).
    """
    actor_id = "urn:agent:autonomic-controller"
    action_iri = "urn:action:restart_pod"
    target_cap = "urn:cap:cluster:pods"

    actuator = RealClusterActuator()
    verifier = RealClusterVerifier()
    broker = AuthorityBroker()
    boundary = ConsequenceBoundary(
        authority_broker=broker, actuator=actuator, verifier=verifier
    )
    gateway = NoveltyIngestionGateway()
    synthesizer = CountingHookSynthesizer()

    artifact = _run_first_episode_and_promote(
        boundary=boundary,
        gateway=gateway,
        synthesizer=synthesizer,
        actor_id=actor_id,
        action_iri=action_iri,
        target_cap=target_cap,
        idempotency_token="idemp-repeat-a-episode-1",
        pod_id="payment-api-pod-42",
        hook_name="crash_loop_remediation_hook_repeat_a",
    )
    assert synthesizer.call_count == 1

    hook_engine = CountingHookEngine()
    hook_engine.register_hook(artifact.hook)
    broker.register_grant(artifact.suggested_grant)

    loop = ReactiveSemanticLoop(
        hook_engine=hook_engine,
        authority_broker=broker,
        consequence_boundary=boundary,
        max_cascade_depth=3,
    )

    base_ttl = "@prefix ex: <http://example.org/> . ex:cluster ex:status 'OK' ."
    # AFDE-2604 fail-secure closure: `loop` was constructed with `admission_pipeline`
    # omitted, so it now builds a real `AdmissionPipeline()` and admits THIS exact
    # `current_event` content once per cascade depth (reactive_loop.py). The event
    # delta must therefore carry BOTH the real trigger content the promoted hook's
    # local-fallback content check requires (`ex:status 'CRASH_LOOP'`) AND the real
    # `afl:targetResource` triple binding `action_iri` to `target_cap` that
    # `ConsequenceBoundary.execute_admitted()`'s admission gate requires -- otherwise
    # the second episode would be refused REFUSED_ADMISSION_CONTENT_NOT_BOUND before
    # ever reaching the hook/synthesis machinery this test actually measures.
    matching_event_ttl = (
        "@prefix ex: <http://example.org/> .\n"
        "@prefix afl: <urn:autofde-lab:> .\n"
        "ex:pod ex:status 'CRASH_LOOP' .\n"
        f"<{action_iri}> afl:targetResource <{target_cap}> .\n"
    )

    trace = loop.run_reflex_cycle(
        base_ttl,
        matching_event_ttl,
        actor_id=actor_id,
        delta_generator=lambda r: "",
    )

    assert trace.quiescence_reached is True
    assert len(trace.steps) == 1
    step = trace.steps[0]
    assert "crash_loop_remediation_hook_repeat_a" in step.triggered_hooks
    assert len(step.final_receipts) == 1
    assert step.final_receipts[0].state == TerminalReceiptState.EXECUTED
    assert step.final_receipts[0].postcondition_verified is True
    assert len(actuator.restarted_pods) == 1

    # THE FALSIFIER, exercised for real: the second, matching episode must call
    # HookSynthesizer.synthesize_from_resolution zero additional times.
    assert synthesizer.call_count == 1, (
        f"expected exactly 1 total synthesis call across both episodes (episode 1 "
        f"only); observed {synthesizer.call_count} -- the second matching episode "
        f"triggered another synthesis call, contradicting falsifier #2."
    )
    # run_reflex_cycle's while loop calls KnowledgeHookEngine.evaluate() once per
    # cascade depth: depth 0 fires the hook and produces the (empty, per
    # delta_generator) resulting delta; depth 1 re-evaluates that empty delta, finds
    # nothing fired, and sets quiescence_reached -- real, observed count, not assumed.
    assert hook_engine.evaluate_call_count == 2


def test_second_matching_episode_via_original_entry_point_bypasses_hook_entirely():
    """Falsifies the literal "routes through the newly promoted deterministic hook"
    framing for the OTHER real local entry point: resubmitting through
    ``ConsequenceBoundary.execute`` -- the exact same call the original episode used
    when it was refused (Cycle 0 in the existing lifecycle test) -- with a hook engine
    that is constructed but deliberately never registered with the promoted hook.

    Real, counted result: the second episode still succeeds (EXECUTED), with zero
    further synthesis calls -- but ``CountingHookEngine.evaluate`` is called ZERO times.
    ``ConsequenceBoundary.execute`` never references a hook engine at all (confirmed by
    reading ``src/autofde_lab/sa2a/brce/boundary.py`` in full); the second episode is
    authorized purely by ``AuthorityBroker.evaluate`` finding a matching registered
    ``AuthorityGrant`` (``authority/broker.py:206-214``). So on this route the "newly
    promoted deterministic hook" object is never consulted at all -- the zero-inference
    property holds, but not because the episode was "routed through the hook"; it holds
    because the authority grant alone is sufficient for this entry point.
    """
    actor_id = "urn:agent:autonomic-controller"
    action_iri = "urn:action:restart_pod"
    target_cap = "urn:cap:cluster:pods"

    actuator = RealClusterActuator()
    verifier = RealClusterVerifier()
    broker = AuthorityBroker()
    boundary = ConsequenceBoundary(
        authority_broker=broker, actuator=actuator, verifier=verifier
    )
    gateway = NoveltyIngestionGateway()
    synthesizer = CountingHookSynthesizer()

    artifact = _run_first_episode_and_promote(
        boundary=boundary,
        gateway=gateway,
        synthesizer=synthesizer,
        actor_id=actor_id,
        action_iri=action_iri,
        target_cap=target_cap,
        idempotency_token="idemp-repeat-b-episode-1",
        pod_id="payment-api-pod-43",
        hook_name="crash_loop_remediation_hook_repeat_b",
    )
    assert synthesizer.call_count == 1

    # Deliberately NOT registered into any hook engine -- this test isolates whether
    # ConsequenceBoundary.execute alone, with only the AuthorityGrant registered,
    # already produces a deterministic zero-inference second episode.
    broker.register_grant(artifact.suggested_grant)
    hook_engine = CountingHookEngine()  # constructed but never wired into `boundary`

    second_envelope = ExecutionEnvelope(
        idempotency_token="idemp-repeat-b-episode-2",  # distinct token: not an idempotency replay
        action_iri=action_iri,
        target_resource=target_cap,
        parameters={"pod_id": "payment-api-pod-43"},
        actor_id=actor_id,
        # AFDE-2604 fail-secure closure: `boundary` requires admission (class default
        # `require_admission=True`); without a real, bound AdmissionResult here this
        # second episode would be refused REFUSED_NOT_ADMITTED at Step 0, never
        # reaching the AuthorityGrant-only code path this test is isolating.
        admission_result=_admitted_result(action_iri, target_cap, actor_id),
    )
    result: BoundaryExecutionResult = boundary.execute(second_envelope)

    assert result.success is True
    assert result.state == TerminalReceiptState.EXECUTED
    assert result.replayed is False  # real second episode, not an idempotency cache hit
    assert len(actuator.restarted_pods) == 1

    assert synthesizer.call_count == 1
    assert hook_engine.evaluate_call_count == 0, (
        "KnowledgeHookEngine.evaluate was called on the ConsequenceBoundary.execute "
        "route, contradicting the finding that this route never consults the hook."
    )


def test_unrelated_event_does_not_fire_promoted_hook():
    """AFDE-2612 local fix, falsifier: an unrelated event delta must NOT fire a
    promoted hook.

    This is the exact falsifier the prior session's closure notes named as missing
    (``docs/jira/v26.9.16/AFDE-2612-machine-experience-compile-back-closure.md``,
    "2026-09-16" entry, "A third, exploratory, non-committed check"): that earlier pass
    ran an ad hoc ``.venv/bin/python -c ...`` snippet (never added as a pytest test)
    submitting an event delta with no relation at all to the promoted hook's
    ``trigger_predicate``/``trigger_value`` (``ex:otherthing ex:unrelated 'X'`` instead
    of ``ex:status 'CRASH_LOOP'``) and observed the hook fire anyway --
    ``KnowledgeHookEngine.evaluate``'s local fallback (``hooks/engine.py``) fired ANY
    registered ``ASSERT`` hook on ANY non-empty event delta, with no check against the
    hook's own trigger condition.

    Real promotion (identical to the other two tests in this file): episode 1 is a
    novel incident, refused, ingested, synthesized (with
    ``trigger_predicate="ex:status"``, ``trigger_value="CRASH_LOOP"``), and promoted
    (registered hook + grant). Episode 2 here is a SECOND, real incident submitted
    through the same real ``ReactiveSemanticLoop.run_reflex_cycle`` the matching-episode
    test above uses -- but its event delta asserts a genuinely unrelated predicate/value
    pair (``ex:otherthing`` / ``'UNRELATED_SIGNAL'``), sharing no content with the
    promoted hook's trigger condition.

    Real, counted result asserted: the promoted hook does NOT fire
    (``hook_engine.evaluate_call_count == 1`` -- evaluated exactly once, found nothing
    fired, and the loop reaches quiescence immediately without a second cascade-depth
    call), ``trace.steps`` stays empty (no cascade step was ever produced), no further
    synthesis call happens, and the real actuator's ``restarted_pods`` list stays empty
    -- no consequence occurred for the unrelated event. This is the negative control
    ``test_second_matching_episode_via_reflex_loop_makes_zero_further_synthesis_calls``
    needs to prove its own zero-inference result comes from real pattern matching and
    not from a fallback that would have fired on anything.
    """
    actor_id = "urn:agent:autonomic-controller"
    action_iri = "urn:action:restart_pod"
    target_cap = "urn:cap:cluster:pods"

    actuator = RealClusterActuator()
    verifier = RealClusterVerifier()
    broker = AuthorityBroker()
    boundary = ConsequenceBoundary(
        authority_broker=broker, actuator=actuator, verifier=verifier
    )
    gateway = NoveltyIngestionGateway()
    synthesizer = CountingHookSynthesizer()

    artifact = _run_first_episode_and_promote(
        boundary=boundary,
        gateway=gateway,
        synthesizer=synthesizer,
        actor_id=actor_id,
        action_iri=action_iri,
        target_cap=target_cap,
        idempotency_token="idemp-repeat-c-episode-1",
        pod_id="payment-api-pod-44",
        hook_name="crash_loop_remediation_hook_repeat_c",
    )
    assert synthesizer.call_count == 1
    assert artifact.hook.trigger_predicate == "ex:status"
    assert artifact.hook.trigger_value == "CRASH_LOOP"

    hook_engine = CountingHookEngine()
    hook_engine.register_hook(artifact.hook)
    broker.register_grant(artifact.suggested_grant)

    loop = ReactiveSemanticLoop(
        hook_engine=hook_engine,
        authority_broker=broker,
        consequence_boundary=boundary,
        max_cascade_depth=3,
    )

    base_ttl = "@prefix ex: <http://example.org/> . ex:cluster ex:status 'OK' ."
    # Genuinely unrelated to the promoted hook's ex:status/CRASH_LOOP trigger -- same
    # shape (a predicate/quoted-literal-value pair) so this is a real content check,
    # not merely an empty-vs-non-empty check.
    unrelated_event_ttl = (
        "@prefix ex: <http://example.org/> . ex:node ex:otherthing 'UNRELATED_SIGNAL' ."
    )

    trace = loop.run_reflex_cycle(
        base_ttl,
        unrelated_event_ttl,
        actor_id=actor_id,
        delta_generator=lambda r: "",
    )

    # THE FALSIFIER, exercised for real: an unrelated event must not fire the promoted
    # hook -- the exact gap the prior session's ad hoc, non-committed check found.
    assert trace.quiescence_reached is True
    assert len(trace.steps) == 0, (
        f"expected zero cascade steps for an unrelated event delta; observed "
        f"{len(trace.steps)} -- the promoted hook fired on content it was never "
        f"synthesized to match, contradicting the AFDE-2612 local fix."
    )
    assert hook_engine.evaluate_call_count == 1, (
        f"expected exactly 1 evaluate() call (the loop should reach quiescence "
        f"immediately on the first, non-matching delta); observed "
        f"{hook_engine.evaluate_call_count}."
    )
    assert synthesizer.call_count == 1
    assert len(actuator.restarted_pods) == 0, (
        "the real actuator recorded a restart for an event that never matched the "
        "promoted hook's trigger condition -- an unreceipted, unwarranted consequence."
    )
