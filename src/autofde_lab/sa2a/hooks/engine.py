"""Knowledge Hook Engine driving reactive semantic transformations.

Evaluates admitted hooks against graph deltas using Praxis GraphLaw WASM,
producing deterministic SemanticIntents without direct consequence execution.
"""

from __future__ import annotations

import hashlib
import re
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

    @staticmethod
    def _local_fallback_condition_matches(
        hook: KnowledgeHookDefinition, event_ttl: str
    ) -> bool:
        """Real content check used by the local Python fallback (below), for when the
        Praxis GraphLaw WASM engine returned no verdict for this hook's IRI -- which is
        every hook manufactured by HookSynthesizer today, since a synthesized hook's
        GraphLaw rule (``artifact.graphlaw_rule_ttl``) is never merged into the graph
        ``GraphLawBridge.run_hooks`` evaluates, and its ``condition_query`` is never
        populated.

        AFDE-2612 (2026-09-16 pass): merging a hook's ``kh:Hook``-shaped Turtle into
        ``base_ttl`` would NOT be sufficient to make the WASM branch above
        (``v_data = verdicts_by_iri.get(hook.iri)``) actually hit, even if a future
        change wired that merge in. Confirmed by real execution this session (see
        ``tests/sa2a/test_afde_2612_wasm_admission_blocked.py``) against the exact
        pinned ``praxis-graphlaw-wasm`` artifact this bridge loads
        (``admission/graphlaw_bridge.py:EXPECTED_ARTIFACT_SHA256``): the vendored
        engine's own ``TripleStore::from`` parse path decodes plain string literals
        with an RDF 1.1 datatype suffix baked into the text (e.g.
        ``"assert"^^<http://www.w3.org/2001/XMLSchema#string>``), and
        ``hooks::parsing::clean_term`` in ``~/praxis`` (a separate, pinned,
        content-addressed dependency this repo does not modify) never strips that
        suffix -- so ``validate_and_extract_hooks``'s exact-string matches on
        ``kh:on``/``kh:kind`` always fail, silently, for every hook, and
        ``TripleStore::from`` ends up with an empty hook registry regardless of what
        Turtle is supplied. This reproduces even against the upstream WASM crate's own
        reference fixture for a firing hook
        (``crates/praxis-graphlaw-wasm/tests/core.rs::test_run_hooks_core_fires_expected_hook``),
        whose own assertion is deliberately weakened to tolerate it. The gap is
        therefore `BLOCKED:UPSTREAM_PRAXIS_GRAPHLAW_LITERAL_DECODE` (per this repo's
        ``.claude/rules/standing-law.md`` vocabulary), not a wiring gap local to this
        module -- see the AFDE-2612 ticket's closure notes for the full trace.

        AFDE-2612 local fix: before this method existed, the fallback fired ANY
        registered ``ASSERT`` hook on ANY non-empty event delta, regardless of the
        delta's actual content -- confirmed by live execution in this repo's
        AFDE-2612 closure notes (an event asserting an unrelated predicate/value still
        fired a hook whose GraphLaw rule named a completely different one). This
        method requires the event delta to actually contain a triple matching the
        hook's own ``trigger_predicate``/``trigger_value`` before it may fire.

        A hook with no explicit trigger condition configured (``trigger_predicate`` or
        ``trigger_value`` is ``None`` -- true for every hand-constructed hook in this
        repo's test/CLI/benchmark call sites that never set these fields) preserves
        the pre-fix behavior: any non-empty delta is treated as a match, since there
        is nothing more specific to check it against.
        """
        predicate = (hook.trigger_predicate or "").strip()
        value = (hook.trigger_value or "").strip()
        if not predicate or not value:
            return True
        pattern = re.compile(rf"{re.escape(predicate)}\s+['\"]{re.escape(value)}['\"]")
        return pattern.search(event_ttl) is not None

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
                # WASM verdict lookup missed this hook's IRI (see
                # _local_fallback_condition_matches's docstring for why that is the
                # common case for synthesized hooks). Evaluate the trigger locally: a
                # gated ASSERT hook never fires on an empty delta; a non-empty delta
                # only fires the hook if its real trigger_predicate/trigger_value
                # actually matches the delta's content (AFDE-2612 local fix -- this
                # used to fire on ANY non-empty delta regardless of content).
                gated = hook.on == HookEventTrigger.ASSERT and not event_ttl.strip()
                if gated:
                    verdict = HookVerdict.GATED
                elif event_ttl.strip() and self._local_fallback_condition_matches(
                    hook, event_ttl
                ):
                    verdict = HookVerdict.FIRED
                else:
                    verdict = HookVerdict.NOT_FIRED
                condition_hash = hashlib.sha256(
                    hook.condition_query.encode("utf-8")
                ).hexdigest()
                diag = None

            intent: SemanticIntent | None = None
            if (
                verdict == HookVerdict.FIRED
                and hook.effect == HookEffectKind.GROUND_ACTION
            ):
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
