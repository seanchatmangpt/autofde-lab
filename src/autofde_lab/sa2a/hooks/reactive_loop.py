"""Reactive Semantic Network Loop closing the autonomic reflex cycle.

RFC-SA2A-001 v26.9.16:
    O* -> Δ -> KnowledgeHook -> SELECT/CONSTRUCT -> Intent -> Authority -> BRCE -> DO -> Receipt -> ΔO*
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Callable, Mapping, Optional, Sequence

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline, AdmissionResult
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityDecision,
    AuthorityGrant,
    ConsequenceRequest,
)
from autofde_lab.sa2a.brce.boundary import (
    REFUSED_NOT_ADMITTED,
    ConsequenceActuator,
    ConsequenceBoundary,
    ConsequenceVerifier,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import FinalReceipt, TerminalReceiptState
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.model import HookExecutionRecord, HookVerdict, SemanticIntent


class _NotSet:
    """Sentinel distinguishing an omitted constructor argument from an explicit
    `None` -- AFDE-2604 fail-secure closure needs to tell "caller said nothing"
    (-> secure real `AdmissionPipeline()`) apart from "caller explicitly opted
    out" (-> `None`, honored as-is), which a plain `= None` default cannot do."""


_NOT_SET = _NotSet()


@dataclass(frozen=True)
class ReactiveCycleStep:
    """One discrete step of the autonomic semantic reaction loop."""

    depth: int
    event_delta_ttl: str
    triggered_hooks: tuple[str, ...]
    intents_synthesized: tuple[SemanticIntent, ...]
    authority_decisions: tuple[AuthorityDecision, ...]
    final_receipts: tuple[FinalReceipt, ...]
    resulting_delta_ttl: str


@dataclass
class ReactiveSemanticTrace:
    """Complete causal execution trace of an autonomic reflex reaction."""

    initial_base_ttl: str
    initial_event_ttl: str
    steps: list[ReactiveCycleStep] = field(default_factory=list)
    quiescence_reached: bool = False
    stopped_by_bound: bool = False

    @property
    def total_receipts(self) -> int:
        return sum(len(s.final_receipts) for s in self.steps)


class ReactiveSemanticLoop:
    """Closed autonomic reflex loop driving Hook -> Intent -> Authority -> BRCE -> Delta.

    AFDE-2604 (local closure of A2A-2604, "wire semantic admission into the live
    consequence path"): accepts an OPTIONAL `admission_pipeline`. When configured, this
    is the one real composed entry point that enforces
    `candidate -> ADMIT -> SELECT -> CONSTRUCT -> authority grant -> DO` for the live
    semantic-dispatch path -- the candidate content driving each reflex cycle is
    admitted via a real `AdmissionPipeline.admit()` call, and the resulting
    `AdmissionResult` gates every intent synthesized from it before
    `AuthorityBroker.evaluate()` is ever consulted for that intent.

    AFDE-2604 fail-secure closure (this pass, closing UE-2 alongside
    `ConsequenceBoundary`'s own default flip): a real `AdmissionPipeline()` is now
    constructed by default when `admission_pipeline` is omitted, so this loop's own
    gating (`run_reflex_cycle()`'s per-cycle `admit()` call, checked before
    `AuthorityBroker.evaluate()` for every intent) and `ConsequenceBoundary`'s own
    `require_admission` default are no longer two independently-configured knobs
    that could silently drift apart (the real, adversarially confirmed UE-2 gap:
    a loop constructed with its own bare defaults reached real actuation for
    content an admission-configured sibling instance would have refused).
    `admission_pipeline=None` explicitly, passed at construction, still restores the
    old `candidate -> authority -> DO` behavior for a caller that genuinely needs
    it -- an affirmative, visible choice, never a silent default.
    """

    def __init__(
        self,
        hook_engine: KnowledgeHookEngine,
        authority_broker: AuthorityBroker,
        consequence_boundary: ConsequenceBoundary,
        *,
        max_cascade_depth: int = 5,
        admission_pipeline: Optional[AdmissionPipeline] | _NotSet = _NOT_SET,
    ) -> None:
        self.hook_engine = hook_engine
        self.authority_broker = authority_broker
        self.consequence_boundary = consequence_boundary
        self.max_cascade_depth = max_cascade_depth
        # AFDE-2604 fail-secure closure: distinguishes "omitted" (-> secure real
        # AdmissionPipeline()) from an explicit `admission_pipeline=None` (-> the
        # caller's affirmative, visible opt-out) -- a plain `= None` default could
        # not tell these apart. Constructed fresh here, never as a shared mutable
        # default-argument instance.
        resolved_admission_pipeline: Optional[AdmissionPipeline]
        if isinstance(admission_pipeline, _NotSet):
            resolved_admission_pipeline = AdmissionPipeline()
        else:
            resolved_admission_pipeline = admission_pipeline
        self.admission_pipeline = resolved_admission_pipeline

    def run_reflex_cycle(
        self,
        base_ttl: str,
        initial_event_ttl: str,
        *,
        actor_id: str = "urn:agent:autonomic-controller",
        delta_generator: Callable[[FinalReceipt], str] | None = None,
    ) -> ReactiveSemanticTrace:
        """Run the autonomic reflex cycle until quiescence or max_cascade_depth bound."""
        trace = ReactiveSemanticTrace(
            initial_base_ttl=base_ttl,
            initial_event_ttl=initial_event_ttl,
        )

        current_base = base_ttl
        current_event = initial_event_ttl
        depth = 0

        while depth < self.max_cascade_depth:
            # 1. Evaluate hooks over current graph state and delta
            records = self.hook_engine.evaluate(current_base, current_event)
            fired = [r for r in records if r.verdict == HookVerdict.FIRED and r.intent]

            if not fired:
                trace.quiescence_reached = True
                break

            intents = [r.intent for r in fired if r.intent is not None]
            auth_decisions: list[AuthorityDecision] = []
            receipts: list[FinalReceipt] = []
            next_delta_parts: list[str] = []

            # AFDE-2604 admission fence (opt-in via `admission_pipeline`): the candidate
            # content driving THIS cycle's intents must independently reach
            # Standing.ADMITTED before any intent synthesized from it may reach
            # AuthorityBroker.evaluate(). One admission call per cycle, bound onto every
            # envelope constructed from it -- the same admitted (or refused) candidate
            # identity, not a call this loop could route around per-intent. When
            # `admission_pipeline` is None (default), this is a no-op and every existing
            # caller's behavior is byte-for-byte unchanged.
            #
            # AFDE-2604 default-wiring closure: a real, minimal provenance_record
            # (issuer=this cycle's real actor_id, timestamp=real wall-clock UTC) is
            # supplied -- `AdmissionPipeline.admit()`'s default policy requires both
            # (`require_issuer`/`require_timestamp`), so omitting this would refuse
            # EVERY candidate with REFUSED_PROVENANCE_MISSING regardless of content,
            # making the admission fence appear to work while actually just being
            # permanently closed to legitimate content, never a real content-binding
            # gate. `actor_id` is a real, already-authenticated-enough identity for
            # this call graph (it is the same identity AuthorityBroker.evaluate() is
            # about to check downstream); it is never treated as authority itself --
            # admission stays authority-inert regardless (AFDE-2604 Laws #2).
            admission_result: Optional[AdmissionResult] = None
            if self.admission_pipeline is not None:
                admission_result = self.admission_pipeline.admit(
                    current_event,
                    provenance_record={
                        "issuer": actor_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            # 2. For each intent, evaluate Authority and execute via BRCE
            for intent in intents:
                if self.admission_pipeline is not None and (
                    admission_result is None or admission_result.standing != Standing.ADMITTED
                ):
                    # Fenced: refused before AuthorityBroker.evaluate() is ever consulted.
                    standing_repr = admission_result.standing.value if admission_result else None
                    auth_decisions.append(
                        AuthorityDecision(
                            authorized=False,
                            grant_id=None,
                            refusal_code=REFUSED_NOT_ADMITTED,
                            reason=(
                                "AFDE-2604 admission fence: candidate content for this "
                                f"reflex cycle was not Standing.ADMITTED (standing="
                                f"{standing_repr!r}); refused before AuthorityBroker."
                                "evaluate() was ever consulted for this intent."
                            ),
                        )
                    )
                    continue

                req = ConsequenceRequest(
                    actor_id=actor_id,
                    action_iri=intent.action_iri,
                    target_resource=intent.target_capability_iri,
                    context=dict(intent.parameters),
                )
                auth_decision = self.authority_broker.evaluate(req)
                auth_decisions.append(auth_decision)

                if auth_decision.authorized:
                    env = ExecutionEnvelope(
                        idempotency_token=f"idemp-{intent.intent_id}",
                        action_iri=intent.action_iri,
                        target_resource=intent.target_capability_iri,
                        parameters=intent.parameters,
                        actor_id=actor_id,
                        grant_id=auth_decision.grant_id,
                        admission_result=admission_result,
                    )
                    res = (
                        self.consequence_boundary.execute_admitted(env)
                        if self.admission_pipeline is not None
                        else self.consequence_boundary.execute(env)
                    )
                    if res.final_receipt is not None:
                        receipts.append(res.final_receipt)

                    # Compute resulting delta from receipt
                    if delta_generator:
                        next_delta = delta_generator(res.final_receipt)
                    else:
                        next_delta = (
                            f"@prefix ex: <http://example.org/> .\n"
                            f"<{intent.action_iri}> ex:receiptState \"{res.final_receipt.state.value}\" .\n"
                        )
                    next_delta_parts.append(next_delta)

            resulting_delta = "\n".join(next_delta_parts)
            step = ReactiveCycleStep(
                depth=depth,
                event_delta_ttl=current_event,
                triggered_hooks=tuple(r.hook_name for r in fired),
                intents_synthesized=tuple(intents),
                authority_decisions=tuple(auth_decisions),
                final_receipts=tuple(receipts),
                resulting_delta_ttl=resulting_delta,
            )
            trace.steps.append(step)

            # Advance state for next cycle
            current_base = f"{current_base}\n{current_event}\n{resulting_delta}"
            current_event = resulting_delta
            depth += 1

        if depth >= self.max_cascade_depth and not trace.quiescence_reached:
            trace.stopped_by_bound = True

        return trace
