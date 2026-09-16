"""Knowledge Hook Synthesizer (§4.5–§4.8).

Manufactures admitted KnowledgeHookDefinition and GraphLaw N3/SHACL rules from
qualified Lab resolutions (Planner League outcomes, verified repairs, or candidate solutions).
Ensures:
    Experience -> Semantic Law -> Knowledge Hook -> Deterministic Reflex.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from autofde_lab.sa2a.authority.broker import AuthorityGrant
from autofde_lab.sa2a.hooks.model import (
    HookEffectKind,
    HookEventTrigger,
    KnowledgeHookDefinition,
)


@dataclass(frozen=True, slots=True)
class SynthesizedHookArtifact:
    """Manufactured hook artifact combining hook definition, GraphLaw rule, and authority grant."""

    hook: KnowledgeHookDefinition
    graphlaw_rule_ttl: str
    suggested_grant: AuthorityGrant
    artifact_digest: str


class HookSynthesizer:
    """Synthesizes deterministic Knowledge Hooks from qualified Lab candidate resolutions."""

    def synthesize_from_resolution(
        self,
        *,
        hook_name: str,
        trigger_predicate: str = "ex:status",
        trigger_value: str = "FAILED",
        action_iri: str,
        target_capability_iri: str,
        goal_iri: str = "urn:goal:autonomic_stabilization",
        reason: str = "Autonomic reflex compiled from Lab qualification",
        priority: int = 10,
        authorized_actor: str = "urn:agent:autonomic-controller",
    ) -> SynthesizedHookArtifact:
        """Synthesize a KnowledgeHookDefinition and matching GraphLaw rule from a verified resolution."""
        hook_iri = f"http://example.org/hook/{hook_name}"
        hook = KnowledgeHookDefinition(
            iri=hook_iri,
            name=hook_name,
            on=HookEventTrigger.ASSERT,
            condition_kind="delta",
            effect=HookEffectKind.GROUND_ACTION,
            action_iri=action_iri,
            target_capability_iri=target_capability_iri,
            goal_iri=goal_iri,
            reason=reason,
            priority=priority,
        )

        # GraphLaw N3 Rule: when trigger_predicate matches trigger_value, infer intent requirement
        rule_ttl = (
            f"@prefix kh: <http://seanchatmangpt.github.io/praxis/kh#> .\n"
            f"@prefix ex: <http://example.org/> .\n\n"
            f"# Compiled GraphLaw rule for hook: {hook_name}\n"
            f"{{ ?s {trigger_predicate} '{trigger_value}' }} => {{\n"
            f"    <{hook_iri}> a kh:TriggeredHook ;\n"
            f"        kh:targetAction <{action_iri}> ;\n"
            f"        kh:targetCapability <{target_capability_iri}> .\n"
            f"}} .\n"
        )

        grant = AuthorityGrant(
            grant_id=f"grant-{hook_name}-{uuid.uuid4().hex[:8]}",
            subject_id=authorized_actor,
            action_iri=action_iri,
            target_resource_iri=target_capability_iri,
        )

        digest_payload = f"{hook.to_turtle()}:{rule_ttl}:{grant.grant_id}"
        artifact_digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()

        return SynthesizedHookArtifact(
            hook=hook,
            graphlaw_rule_ttl=rule_ttl,
            suggested_grant=grant,
            artifact_digest=artifact_digest,
        )
