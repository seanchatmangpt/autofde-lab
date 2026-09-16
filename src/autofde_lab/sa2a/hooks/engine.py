"""Knowledge Hook Engine driving reactive semantic transformations.

Evaluates admitted hooks against graph deltas using Praxis GraphLaw WASM,
producing deterministic SemanticIntents without direct consequence execution.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Mapping, Sequence

from autofde_lab.sa2a.admission.graphlaw_bridge import GraphLawBridge
from autofde_lab.sa2a.hooks.model import (
    HookEffectKind,
    HookEventTrigger,
    HookExecutionRecord,
    HookVerdict,
    KnowledgeHookDefinition,
    SemanticIntent,
)


class KnowledgeHookEngine:
    """Reactive engine evaluating admitted Knowledge Hooks over graph transitions."""

    def __init__(self, bridge: GraphLawBridge | None = None) -> None:
        self._bridge = bridge or GraphLawBridge()
        self._hooks: dict[str, KnowledgeHookDefinition] = {}

    def register_hook(self, hook: KnowledgeHookDefinition) -> None:
        """Register an admitted KnowledgeHook."""
        self._hooks[hook.iri] = hook

    def unregister_hook(self, hook_iri: str) -> bool:
        """Remove a hook by IRI."""
        return self._hooks.pop(hook_iri, None) is not None

    @property
    def registered_hooks(self) -> Sequence[KnowledgeHookDefinition]:
        return tuple(self._hooks.values())

    def evaluate(
        self,
        base_ttl: str,
        event_ttl: str,
        *,
        causal_prior_digest: str = "",
        parameters: Mapping[str, Any] | None = None,
    ) -> list[HookExecutionRecord]:
        """Evaluate registered hooks against base graph state and transition event delta.

        Uses Praxis GraphLaw WASM engine to compute deterministic verdicts, receipts,
        and schedules. Synthesizes SemanticIntents for fired hooks.
        """
        params = parameters or {}
        # Execute hooks in GraphLaw WASM
        raw_res = self._bridge.run_hooks(base_ttl, event_ttl)
        status = raw_res.get("status", "UNKNOWN")
        verdicts_raw = raw_res.get("verdicts", [])

        # Map verdicts by IRI
        verdicts_by_iri: dict[str, dict[str, Any]] = {
            v.get("hook_iri", ""): v for v in verdicts_raw
        }

        records: list[HookExecutionRecord] = []
        now_ns = time.time_ns()

        for hook in self._hooks.values():
            v_data = verdicts_by_iri.get(hook.iri)
            if v_data:
                raw_verdict = v_data.get("verdict", "NotFired")
                verdict = (
                    HookVerdict.FIRED
                    if raw_verdict == "Fired"
                    else (
                        HookVerdict.GATED
                        if raw_verdict == "Gated"
                        else HookVerdict.NOT_FIRED
                    )
                )
                condition_hash = v_data.get("condition_hash", "")
                diag = v_data.get("diagnostics")
            else:
                # If event delta has content and hook condition matches, evaluate trigger
                gated = (hook.on == HookEventTrigger.ASSERT and not event_ttl.strip())
                if gated:
                    verdict = HookVerdict.GATED
                elif event_ttl.strip():
                    verdict = HookVerdict.FIRED
                else:
                    verdict = HookVerdict.NOT_FIRED
                condition_hash = hashlib.sha256(
                    hook.condition_query.encode("utf-8")
                ).hexdigest()
                diag = None

            intent: SemanticIntent | None = None
            if verdict == HookVerdict.FIRED and hook.effect == HookEffectKind.GROUND_ACTION:
                action_iri = hook.action_iri or f"{hook.iri}#action"
                target_cap = hook.target_capability_iri or f"{action_iri}/capability"
                goal = hook.goal_iri or f"{action_iri}/goal"
                combined_params = dict(hook.parameters)
                if params:
                    combined_params.update(params)
                intent = SemanticIntent(
                    intent_id=f"intent-{uuid.uuid4().hex[:12]}",
                    source_hook_iri=hook.iri,
                    action_iri=action_iri,
                    target_capability_iri=target_cap,
                    goal_iri=goal,
                    parameters=combined_params,
                    condition_hash=condition_hash,
                    causal_prior_digest=causal_prior_digest,
                    timestamp_ns=now_ns,
                )

            records.append(
                HookExecutionRecord(
                    hook_iri=hook.iri,
                    hook_name=hook.name,
                    verdict=verdict,
                    condition_kind=hook.condition_kind,
                    condition_hash=condition_hash,
                    action_iri=hook.action_iri,
                    intent=intent,
                    diagnostics=diag,
                )
            )

        return records
