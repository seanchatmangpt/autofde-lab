"""Reactive Semantic Network Loop closing the autonomic reflex cycle.

RFC-SA2A-001 v26.9.16:
    O* -> Δ -> KnowledgeHook -> SELECT/CONSTRUCT -> Intent -> Authority -> BRCE -> DO -> Receipt -> ΔO*
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Mapping, Sequence

from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityDecision,
    AuthorityGrant,
    ConsequenceRequest,
)
from autofde_lab.sa2a.brce.boundary import (
    ConsequenceActuator,
    ConsequenceBoundary,
    ConsequenceVerifier,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import FinalReceipt, TerminalReceiptState
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.model import HookExecutionRecord, HookVerdict, SemanticIntent


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
    """Closed autonomic reflex loop driving Hook -> Intent -> Authority -> BRCE -> Delta."""

    def __init__(
        self,
        hook_engine: KnowledgeHookEngine,
        authority_broker: AuthorityBroker,
        consequence_boundary: ConsequenceBoundary,
        *,
        max_cascade_depth: int = 5,
    ) -> None:
        self.hook_engine = hook_engine
        self.authority_broker = authority_broker
        self.consequence_boundary = consequence_boundary
        self.max_cascade_depth = max_cascade_depth

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

            # 2. For each intent, evaluate Authority and execute via BRCE
            for intent in intents:
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
                    )
                    res = self.consequence_boundary.execute(env)
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
