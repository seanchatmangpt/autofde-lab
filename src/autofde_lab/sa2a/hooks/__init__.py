"""Knowledge Hooks subsystem for Semantic A2A (RFC-SA2A-001 v26.9.16).

Provides reactive semantic operators that evaluate over graph deltas,
synthesize unauthorized SemanticIntents, and drive autonomic reflex loops.
"""

from .engine import KnowledgeHookEngine
from .model import (
    HookEffectKind,
    HookEventTrigger,
    HookExecutionRecord,
    HookVerdict,
    KnowledgeHookDefinition,
    SemanticIntent,
)
from .reactive_loop import (
    ReactiveCycleStep,
    ReactiveSemanticLoop,
    ReactiveSemanticTrace,
)

__all__ = [
    "HookEffectKind",
    "HookEventTrigger",
    "HookExecutionRecord",
    "HookVerdict",
    "KnowledgeHookDefinition",
    "KnowledgeHookEngine",
    "ReactiveCycleStep",
    "ReactiveSemanticLoop",
    "ReactiveSemanticTrace",
    "SemanticIntent",
]
