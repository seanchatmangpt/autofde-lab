from autofde_lab.companion.osiris import (
    ActionCandidate,
    CompanionDecision,
    EcosystemRouter,
    Event,
    EventPriority,
    IntentKind,
    Observation,
    OSIRIS,
    OSIRIS_EXPANSION,
    ResponsePolicy,
    SpeechCandidate,
    Standing,
    Surface,
    VoiceProfile,
    default_event,
)


def test_thin_air_identity_and_voice_profile_are_explicit():
    assert OSIRIS_EXPANSION == "Onboard Situational Insight and Resource Interface Support"


def test_voice_profile_is_exact_0_2_6_6():
    profile = VoiceProfile()
    assert (
        profile.dominance,
        profile.influence,
        profile.steadiness,
        profile.conscientiousness,
    ) == (0, 2, 6, 6)
    assert profile.max_words == 72
    assert any("UNKNOWN" in item for item in profile.directives())


def test_router_covers_every_intent_and_reserves_actuation_for_brce():
    router = EcosystemRouter()
    assert {intent: router.target_for(intent) for intent in IntentKind} == {
        IntentKind.PLAN: Surface.AUTOFDE_LAB,
        IntentKind.MESSAGE: Surface.SA2A,
        IntentKind.WORK: Surface.SJIRA,
        IntentKind.REUSE: Surface.GGEN_MARKETPLACE,
        IntentKind.MANUFACTURE: Surface.GGEN,
        IntentKind.REHEARSE: Surface.GYMACT,
        IntentKind.CLOUD_CAPABILITY: Surface.ASH_KUDZU,
        IntentKind.AGENT_INTEROP: Surface.ASH_A2A,
        IntentKind.PROCESS_EVIDENCE: Surface.WASM4PM,
        IntentKind.DELIVER: Surface.XAAS,
        IntentKind.LIFE: Surface.LIFEGYM,
        IntentKind.DOCTRINE: Surface.GODSLAW,
        IntentKind.MARKETPLACE: Surface.ZOE_MARKETPLACE,
        IntentKind.ACTUATE: Surface.BRCE,
    }


def test_priority_batching_and_bounded_queue():
    kernel = OSIRIS(subject="sean", max_pending=2, batch_size=2)
    kernel.ingest(default_event("bg", "background.idle", 1))
    kernel.ingest(default_event("direct", "voice.user", 2))
    kernel.ingest(default_event("safety", "runtime.failure", 3))

    assert kernel.pending_event_ids == ("safety", "direct")
    assert tuple(event.event_id for event in kernel.context(4).events) == (
        "safety",
        "direct",
    )


def test_stale_observation_claim_is_refused_not_guessed():
    kernel = OSIRIS(subject="sean")
    kernel.ingest(default_event("voice-1", "voice.user", 1_000))
    kernel.observe(
        Observation(
            key="repo.head",
            value="deadbeef",
            observed_at_ms=0,
            ttl_ms=10,
            provenance="github",
        )
    )

    def choose(context):
        assert "repo.head" not in context.observations
        return CompanionDecision(
            speech=SpeechCandidate(
                text="The repository head is deadbeef.",
                claims=("repo.head",),
            )
        )

    output = kernel.cycle(now_ms=1_001, deliberator=choose)
    assert output.speech is None
    assert output.brce_request is None
    assert output.receipt.standing is Standing.REFUSED
    assert output.receipt.reason == (
        "REFUSED:STALE_OR_MISSING_OBSERVATION:repo.head"
    )


def test_action_is_a_candidate_brce_request_not_do():
    kernel = OSIRIS(subject="sean")
    kernel.ingest(default_event("voice-1", "voice.user", 1_000))

    output = kernel.cycle(
        now_ms=1_001,
        deliberator=lambda _context: CompanionDecision(
            speech=SpeechCandidate(text="Manufacture the admitted projection."),
            action=ActionCandidate(
                intent=IntentKind.MANUFACTURE,
                capability="ggen.manufacture",
                parameters={"pack": "osiris-voice-companion"},
            ),
            carry_plan=("verify manufactured artifact",),
        ),
    )

    assert output.speech is not None
    assert output.brce_request is not None
    assert output.brce_request.route_surface is Surface.BRCE
    assert output.brce_request.target_surface is Surface.GGEN
    assert output.brce_request.standing is Standing.CANDIDATE
    assert output.receipt.standing is Standing.CANDIDATE
    assert output.receipt.reason == "CANDIDATE_ONLY:NO_DO"


def test_event_policy_can_forbid_action():
    kernel = OSIRIS(subject="sean")
    kernel.ingest(
        Event(
            event_id="observe-only",
            kind="external.observation",
            observed_at_ms=100,
            ttl_ms=1_000,
            priority=EventPriority.ROUTINE,
            speech_policy=ResponsePolicy.OPTIONAL,
            action_policy=ResponsePolicy.DO_NOT,
        )
    )

    output = kernel.cycle(
        now_ms=101,
        deliberator=lambda _context: CompanionDecision(
            action=ActionCandidate(
                intent=IntentKind.WORK,
                capability="sjira.create-work-item",
            )
        ),
    )
    assert output.brce_request is None
    assert output.receipt.standing is Standing.REFUSED
    assert output.receipt.reason == "REFUSED:EVENT_POLICY_DO_NOT_ACT"


def test_proactive_action_requires_an_admitted_trigger_event():
    kernel = OSIRIS(subject="sean")
    output = kernel.cycle(
        now_ms=100,
        deliberator=lambda _context: CompanionDecision(
            action=ActionCandidate(
                intent=IntentKind.PLAN,
                capability="autofde.plan",
            )
        ),
    )
    assert output.brce_request is None
    assert output.receipt.reason == "REFUSED:NO_TRIGGER_EVENT"


def test_plan_compaction_persists_obligations_not_consumed_events():
    kernel = OSIRIS(subject="sean")
    kernel.ingest(default_event("voice-1", "voice.user", 1_000))

    first = kernel.cycle(
        now_ms=1_001,
        deliberator=lambda _context: CompanionDecision(
            carry_plan=("verify exact head", "emit receipt")
        ),
    )
    assert first.receipt.standing is Standing.CANDIDATE
    assert kernel.pending_event_ids == ()

    second_context = kernel.context(1_002)
    assert second_context.carry_plan == ("verify exact head", "emit receipt")
    assert second_context.events == ()


def test_receipt_and_ocel_projection_are_deterministic():
    def run_once():
        kernel = OSIRIS(subject="sean")
        kernel.ingest(default_event("voice-1", "voice.user", 1_000))
        return kernel.cycle(
            now_ms=1_001,
            deliberator=lambda _context: CompanionDecision(
                speech=SpeechCandidate(text="Route the work through sJira."),
                action=ActionCandidate(
                    intent=IntentKind.WORK,
                    capability="sjira.route",
                    parameters={"issue": "OSIRIS-001"},
                ),
            ),
        )

    left = run_once()
    right = run_once()
    assert left.receipt.receipt_id == right.receipt.receipt_id
    assert left.brce_request is not None
    assert right.brce_request is not None
    assert left.brce_request.request_id == right.brce_request.request_id

    event = left.receipt.to_ocel_event()
    assert event["id"] == left.receipt.receipt_id
    assert event["type"] == "osiris.CompanionTurn"
    assert event["attributes"]["standing"] == "CANDIDATE"
    assert any(
        relation["qualifier"] == "candidate-request"
        for relation in event["relationships"]
    )


def test_voice_budget_is_enforced_by_fast_loop():
    kernel = OSIRIS(subject="sean", voice=VoiceProfile(max_words=3))
    kernel.ingest(default_event("voice-1", "voice.user", 1_000))
    output = kernel.cycle(
        now_ms=1_001,
        deliberator=lambda _context: CompanionDecision(
            speech=SpeechCandidate(text="one two three four")
        ),
    )
    assert output.speech is None
    assert output.receipt.reason == "REFUSED:VOICE_BUDGET_EXCEEDED"
