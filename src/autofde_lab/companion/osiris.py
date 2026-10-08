"""OSIRIS: bounded, receipt-first voice companion control kernel.

This module deliberately does *not* implement speech recognition, speech synthesis,
an LLM client, or world actuation. It turns admitted conversational/runtime events
into bounded context for a replaceable deliberator, validates the resulting speech
and action candidates, and emits a candidate BRCE request plus a deterministic
receipt.

The authority boundary is structural:

    OBSERVE -> SELECT/CONSTRUCT -> BRCE request
                                  |
                                  +-- no DO in this module

That makes the slow deliberator replaceable and keeps the real-time loop
deterministic, replayable, and suitable for later retirement into formal machinery.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from hashlib import sha256
from typing import Any, Mapping, Protocol

OSIRIS_EXPANSION = "Onboard Situational Insight and Resource Interface Support"


class Standing(str, Enum):
    """Evidence/authority standing emitted by this kernel."""

    UNKNOWN = "UNKNOWN"
    CANDIDATE = "CANDIDATE"
    REFUSED = "REFUSED"


class EventPriority(IntEnum):
    """Priority bands for real-time batching and preemption."""

    BACKGROUND = 10
    ROUTINE = 20
    DIRECT = 40
    URGENT = 80
    SAFETY = 100


class ResponsePolicy(str, Enum):
    """Per-modality event response policy."""

    REQUIRE = "REQUIRE"
    RECOMMEND = "RECOMMEND"
    OPTIONAL = "OPTIONAL"
    DO_NOT = "DO_NOT"


class Surface(str, Enum):
    """Chatman ecosystem surfaces known to the companion router."""

    AUTOFDE_LAB = "autofde-lab"
    SA2A = "sa2a"
    SJIRA = "sjira"
    GGEN_MARKETPLACE = "ggen-marketplace"
    GGEN = "ggen"
    GYMACT = "gymact"
    ASH_KUDZU = "ash_kudzu"
    ASH_A2A = "ash_a2a"
    WASM4PM = "wasm4pm"
    XAAS = "xaas"
    BRCE = "brce"
    LIFEGYM = "lifegym"
    GODSLAW = "godslaw"
    ZOE_MARKETPLACE = "zoe-marketplace"


class IntentKind(str, Enum):
    """Typed intents route to one primary ecosystem surface."""

    PLAN = "plan"
    MESSAGE = "message"
    WORK = "work"
    REUSE = "reuse"
    MANUFACTURE = "manufacture"
    REHEARSE = "rehearse"
    CLOUD_CAPABILITY = "cloud-capability"
    AGENT_INTEROP = "agent-interop"
    PROCESS_EVIDENCE = "process-evidence"
    DELIVER = "deliver"
    LIFE = "life"
    DOCTRINE = "doctrine"
    MARKETPLACE = "marketplace"
    ACTUATE = "actuate"


DEFAULT_ROUTES: dict[IntentKind, Surface] = {
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


@dataclass(frozen=True)
class VoiceProfile:
    """The requested 0/2/6/6 companion voice as executable constraints."""

    dominance: int = 0
    influence: int = 2
    steadiness: int = 6
    conscientiousness: int = 6
    max_words: int = 72

    def directives(self) -> tuple[str, ...]:
        return (
            "lead with changed state, changed edge, or next executable step",
            "use compact plainspoken language with low social filler",
            "do not infer emotion or motivation",
            "preserve candidate/truth/authority/DO/standing distinctions",
            "name UNKNOWN rather than filling evidence gaps",
            "prefer a falsifier or reusable mechanism over explanation",
        )


@dataclass(frozen=True)
class Event:
    event_id: str
    kind: str
    observed_at_ms: int
    ttl_ms: int
    priority: EventPriority
    speech_policy: ResponsePolicy
    action_policy: ResponsePolicy
    payload: Mapping[str, Any] = field(default_factory=dict)

    def is_fresh(self, now_ms: int) -> bool:
        return now_ms <= self.observed_at_ms + self.ttl_ms


@dataclass(frozen=True)
class Observation:
    key: str
    value: Any
    observed_at_ms: int
    ttl_ms: int
    provenance: str

    def is_fresh(self, now_ms: int) -> bool:
        return now_ms <= self.observed_at_ms + self.ttl_ms


@dataclass(frozen=True)
class SpeechCandidate:
    text: str
    claims: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionCandidate:
    intent: IntentKind
    capability: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    target_surface: Surface | None = None


@dataclass(frozen=True)
class CompanionDecision:
    speech: SpeechCandidate | None = None
    action: ActionCandidate | None = None
    carry_plan: tuple[str, ...] = ()


@dataclass(frozen=True)
class TurnContext:
    subject: str
    events: tuple[Event, ...]
    observations: Mapping[str, Observation]
    carry_plan: tuple[str, ...]
    voice: VoiceProfile


@dataclass(frozen=True)
class BRCERequest:
    request_id: str
    subject: str
    capability: str
    target_surface: Surface
    parameters: Mapping[str, Any]
    cause_event_ids: tuple[str, ...]
    context_digest: str
    decision_digest: str
    route_surface: Surface = Surface.BRCE
    standing: Standing = Standing.CANDIDATE
    authority_claim: str = "NONE"


@dataclass(frozen=True)
class CompanionReceipt:
    receipt_id: str
    subject: str
    event_ids: tuple[str, ...]
    context_digest: str
    decision_digest: str
    standing: Standing
    reason: str
    speech_emitted: bool
    brce_request_id: str | None

    def to_ocel_event(self) -> dict[str, Any]:
        """Project the turn into a stable OCEL-shaped event."""

        relationships = [
            {"objectId": event_id, "qualifier": "caused-by"}
            for event_id in self.event_ids
        ]
        if self.brce_request_id is not None:
            relationships.append(
                {"objectId": self.brce_request_id, "qualifier": "candidate-request"}
            )
        return {
            "id": self.receipt_id,
            "type": "osiris.CompanionTurn",
            "attributes": {
                "subject": self.subject,
                "context_digest": self.context_digest,
                "decision_digest": self.decision_digest,
                "standing": self.standing.value,
                "authority": "NONE",
                "reason": self.reason,
                "speech_emitted": self.speech_emitted,
            },
            "relationships": relationships,
        }


@dataclass(frozen=True)
class CompanionOutput:
    speech: SpeechCandidate | None
    brce_request: BRCERequest | None
    receipt: CompanionReceipt


class Deliberator(Protocol):
    def __call__(self, context: TurnContext) -> CompanionDecision: ...


class EcosystemRouter:
    """Typed deterministic routing; no semantic guessing at the DO boundary."""

    def __init__(self, routes: Mapping[IntentKind, Surface] | None = None) -> None:
        self._routes = dict(routes or DEFAULT_ROUTES)

    def target_for(self, intent: IntentKind) -> Surface:
        try:
            return self._routes[intent]
        except KeyError as exc:
            raise ValueError(f"UNSUPPORTED:INTENT:{intent.value}") from exc


def default_event(
    event_id: str,
    kind: str,
    observed_at_ms: int,
    *,
    ttl_ms: int = 5_000,
    payload: Mapping[str, Any] | None = None,
) -> Event:
    """Manufacture an event using the paper-inspired response policy lattice."""

    policies: dict[str, tuple[EventPriority, ResponsePolicy, ResponsePolicy]] = {
        "voice.user": (
            EventPriority.DIRECT,
            ResponsePolicy.REQUIRE,
            ResponsePolicy.RECOMMEND,
        ),
        "work.blocked": (
            EventPriority.URGENT,
            ResponsePolicy.RECOMMEND,
            ResponsePolicy.REQUIRE,
        ),
        "runtime.failure": (
            EventPriority.SAFETY,
            ResponsePolicy.OPTIONAL,
            ResponsePolicy.REQUIRE,
        ),
        "background.idle": (
            EventPriority.BACKGROUND,
            ResponsePolicy.OPTIONAL,
            ResponsePolicy.OPTIONAL,
        ),
    }
    priority, speech, action = policies.get(
        kind,
        (
            EventPriority.ROUTINE,
            ResponsePolicy.OPTIONAL,
            ResponsePolicy.OPTIONAL,
        ),
    )
    return Event(
        event_id=event_id,
        kind=kind,
        observed_at_ms=observed_at_ms,
        ttl_ms=ttl_ms,
        priority=priority,
        speech_policy=speech,
        action_policy=action,
        payload=dict(payload or {}),
    )


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _context_payload(context: TurnContext) -> dict[str, Any]:
    return {
        "subject": context.subject,
        "events": [
            {
                "event_id": event.event_id,
                "kind": event.kind,
                "observed_at_ms": event.observed_at_ms,
                "ttl_ms": event.ttl_ms,
                "priority": int(event.priority),
                "speech_policy": event.speech_policy.value,
                "action_policy": event.action_policy.value,
                "payload": dict(event.payload),
            }
            for event in context.events
        ],
        "observations": {
            key: {
                "value": observation.value,
                "observed_at_ms": observation.observed_at_ms,
                "ttl_ms": observation.ttl_ms,
                "provenance": observation.provenance,
            }
            for key, observation in sorted(context.observations.items())
        },
        "carry_plan": list(context.carry_plan),
        "voice": {
            "dominance": context.voice.dominance,
            "influence": context.voice.influence,
            "steadiness": context.voice.steadiness,
            "conscientiousness": context.voice.conscientiousness,
            "max_words": context.voice.max_words,
        },
    }


def _decision_payload(decision: CompanionDecision) -> dict[str, Any]:
    speech = None
    if decision.speech is not None:
        speech = {
            "text": decision.speech.text,
            "claims": list(decision.speech.claims),
        }

    action = None
    if decision.action is not None:
        action = {
            "intent": decision.action.intent.value,
            "capability": decision.action.capability,
            "parameters": dict(decision.action.parameters),
            "target_surface": (
                decision.action.target_surface.value
                if decision.action.target_surface is not None
                else None
            ),
        }

    return {
        "speech": speech,
        "action": action,
        "carry_plan": list(decision.carry_plan),
    }


class OSIRIS:
    """Fast-loop companion kernel around a replaceable slow deliberator."""

    def __init__(
        self,
        *,
        subject: str,
        voice: VoiceProfile | None = None,
        router: EcosystemRouter | None = None,
        max_pending: int = 32,
        batch_size: int = 8,
    ) -> None:
        if max_pending < 1:
            raise ValueError("max_pending must be >= 1")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.subject = subject
        self.voice = voice or VoiceProfile()
        self.router = router or EcosystemRouter()
        self.max_pending = max_pending
        self.batch_size = batch_size
        self._pending: list[Event] = []
        self._observations: dict[str, Observation] = {}
        self._carry_plan: tuple[str, ...] = ()

    @property
    def pending_event_ids(self) -> tuple[str, ...]:
        return tuple(event.event_id for event in self._pending)

    def ingest(self, event: Event) -> None:
        """Insert/replace an event, then keep the bounded highest-priority frontier."""

        self._pending = [
            existing
            for existing in self._pending
            if existing.event_id != event.event_id
        ]
        self._pending.append(event)
        self._pending.sort(
            key=lambda item: (
                -int(item.priority),
                item.observed_at_ms,
                item.event_id,
            )
        )
        del self._pending[self.max_pending :]

    def observe(self, observation: Observation) -> None:
        """Keep the newest observation for a key; stale values never win."""

        current = self._observations.get(observation.key)
        if current is None or observation.observed_at_ms >= current.observed_at_ms:
            self._observations[observation.key] = observation

    def context(self, now_ms: int) -> TurnContext:
        """Build bounded context and purge expired events."""

        self._pending = [event for event in self._pending if event.is_fresh(now_ms)]
        events = tuple(self._pending[: self.batch_size])
        observations = {
            key: observation
            for key, observation in sorted(self._observations.items())
            if observation.is_fresh(now_ms)
        }
        return TurnContext(
            subject=self.subject,
            events=events,
            observations=observations,
            carry_plan=self._carry_plan,
            voice=self.voice,
        )

    def cycle(
        self,
        *,
        now_ms: int,
        deliberator: Deliberator,
    ) -> CompanionOutput:
        """Run one bounded companion turn.

        The deliberator may SELECT/CONSTRUCT speech and an action candidate.
        This method can only manufacture a BRCERequest. It has no DO edge.
        """

        context = self.context(now_ms)
        context_digest = _digest(_context_payload(context))
        decision = deliberator(context)
        decision_digest = _digest(_decision_payload(decision))
        event_ids = tuple(event.event_id for event in context.events)

        speech_refusal = self._validate_speech(context, decision.speech)
        action_refusal = self._validate_action(context, decision.action)
        emitted_speech = (
            decision.speech
            if decision.speech is not None and speech_refusal is None
            else None
        )

        brce_request: BRCERequest | None = None
        if decision.action is not None and action_refusal is None:
            target = decision.action.target_surface or self.router.target_for(
                decision.action.intent
            )
            request_payload = {
                "subject": self.subject,
                "capability": decision.action.capability,
                "target_surface": target.value,
                "parameters": dict(decision.action.parameters),
                "cause_event_ids": list(event_ids),
                "context_digest": context_digest,
                "decision_digest": decision_digest,
                "authority": "NONE",
            }
            brce_request = BRCERequest(
                request_id=f"osiris-brce-{_digest(request_payload)[:24]}",
                subject=self.subject,
                capability=decision.action.capability,
                target_surface=target,
                parameters=dict(decision.action.parameters),
                cause_event_ids=event_ids,
                context_digest=context_digest,
                decision_digest=decision_digest,
            )

        refusals = tuple(
            item
            for item in (
                f"SPEECH:{speech_refusal}" if speech_refusal is not None else None,
                f"ACTION:{action_refusal}" if action_refusal is not None else None,
            )
            if item is not None
        )
        standing = Standing.REFUSED if refusals else Standing.CANDIDATE
        reason = ";".join(refusals) if refusals else "CANDIDATE_ONLY:NO_DO"

        # Only compact obligations/plan. Raw events are consumed, and stale
        # observations are reconstructed on the next context call.
        self._carry_plan = tuple(decision.carry_plan)
        selected = set(event_ids)
        self._pending = [
            event for event in self._pending if event.event_id not in selected
        ]

        receipt_payload = {
            "subject": self.subject,
            "event_ids": list(event_ids),
            "context_digest": context_digest,
            "decision_digest": decision_digest,
            "standing": standing.value,
            "reason": reason,
            "speech_emitted": emitted_speech is not None,
            "brce_request_id": (
                brce_request.request_id if brce_request is not None else None
            ),
        }
        receipt = CompanionReceipt(
            receipt_id=f"osiris-receipt-{_digest(receipt_payload)[:24]}",
            subject=self.subject,
            event_ids=event_ids,
            context_digest=context_digest,
            decision_digest=decision_digest,
            standing=standing,
            reason=reason,
            speech_emitted=emitted_speech is not None,
            brce_request_id=(
                brce_request.request_id if brce_request is not None else None
            ),
        )
        return CompanionOutput(
            speech=emitted_speech,
            brce_request=brce_request,
            receipt=receipt,
        )

    def _validate_speech(
        self,
        context: TurnContext,
        speech: SpeechCandidate | None,
    ) -> str | None:
        if speech is None:
            return None

        missing = sorted(
            claim for claim in speech.claims if claim not in context.observations
        )
        if missing:
            return "REFUSED:STALE_OR_MISSING_OBSERVATION:" + ",".join(missing)

        if len(speech.text.split()) > self.voice.max_words:
            return "REFUSED:VOICE_BUDGET_EXCEEDED"

        if context.events and all(
            event.speech_policy is ResponsePolicy.DO_NOT for event in context.events
        ):
            return "REFUSED:EVENT_POLICY_DO_NOT_SPEAK"
        return None

    def _validate_action(
        self,
        context: TurnContext,
        action: ActionCandidate | None,
    ) -> str | None:
        if action is None:
            return None
        if not action.capability.strip():
            return "REFUSED:EMPTY_CAPABILITY"
        expected_target = self.router.target_for(action.intent)
        if (
            action.target_surface is not None
            and action.target_surface is not expected_target
        ):
            return (
                "REFUSED:TARGET_ROUTE_MISMATCH:"
                f"{action.target_surface.value}!={expected_target.value}"
            )
        if not context.events:
            return "REFUSED:NO_TRIGGER_EVENT"
        if all(
            event.action_policy is ResponsePolicy.DO_NOT for event in context.events
        ):
            return "REFUSED:EVENT_POLICY_DO_NOT_ACT"
        return None
