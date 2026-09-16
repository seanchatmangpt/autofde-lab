"""Knowledge Hook and Semantic Intent models for reactive semantic networks.

RFC-SA2A-001 v26.9.16 §4.5-§4.8, §25, §26, §28, §30, §31.
Separates:
    GraphLaw (truth / derivation) != KnowledgeHook (intent synthesis) != Authority != BRCE (DO).
Invariants:
    Intent != Authority
    Hook != DO
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class HookEventTrigger(str, Enum):
    ASSERT = "assert"
    RETRACT = "retract"
    ANY = "any"


class HookEffectKind(str, Enum):
    EMIT_DELTA = "EmitDelta"
    GROUND_ACTION = "GroundAction"
    REFUSE = "Refuse"


class HookVerdict(str, Enum):
    FIRED = "Fired"
    NOT_FIRED = "NotFired"
    GATED = "Gated"


@dataclass(frozen=True, slots=True)
class KnowledgeHookDefinition:
    """Admitted Knowledge Hook specification conforming to kh:HookShape."""

    iri: str
    name: str
    on: HookEventTrigger = HookEventTrigger.ASSERT
    condition_kind: str = "delta"
    condition_query: str = ""
    effect: HookEffectKind = HookEffectKind.GROUND_ACTION
    action_iri: str | None = None
    target_capability_iri: str | None = None
    goal_iri: str | None = None
    reason: str | None = None
    priority: int = 0
    after: tuple[str, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def to_turtle(self) -> str:
        """Serialize hook definition to Turtle for GraphLaw / ShEx validation."""
        lines = [
            f"@prefix kh: <http://seanchatmangpt.github.io/praxis/kh#> .",
            f"@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            f"<{self.iri}> a kh:Hook ;",
            f'    kh:name "{self.name}" ;',
            f'    kh:on "{self.on.value}" ;',
            f'    kh:kind "{self.condition_kind}" ;',
            f'    kh:effect "{self.effect.value}" ;',
            f'    kh:priority {self.priority} ;',
        ]
        if self.action_iri:
            lines.append(f"    kh:action <{self.action_iri}> ;")
        if self.goal_iri:
            lines.append(f'    kh:goal "{self.goal_iri}" ;')
        if self.reason:
            lines.append(f'    kh:reason "{self.reason}" ;')
        for dep in self.after:
            lines.append(f"    kh:after <{dep}> ;")
        lines[-1] = lines[-1][:-1] + " ."
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class SemanticIntent:
    """Operational intent synthesized from an admitted Knowledge Hook firing.

    Intent != Authority: An intent has no execution authority until evaluated by
    AuthorityBroker and admitted to BRCE.
    """

    intent_id: str
    source_hook_iri: str
    action_iri: str
    target_capability_iri: str
    goal_iri: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    condition_hash: str = ""
    causal_prior_digest: str = ""
    timestamp_ns: int = 0

    @property
    def intent_digest(self) -> str:
        dumped = json.dumps(
            {
                "intent_id": self.intent_id,
                "source_hook_iri": self.source_hook_iri,
                "action_iri": self.action_iri,
                "target_capability_iri": self.target_capability_iri,
                "goal_iri": self.goal_iri,
                "parameters": dict(sorted(self.parameters.items())),
                "condition_hash": self.condition_hash,
                "causal_prior_digest": self.causal_prior_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class HookExecutionRecord:
    """Deterministic record of evaluating a hook against an admitted graph change."""

    hook_iri: str
    hook_name: str
    verdict: HookVerdict
    condition_kind: str
    condition_hash: str
    action_iri: str | None = None
    intent: SemanticIntent | None = None
    diagnostics: str | None = None
