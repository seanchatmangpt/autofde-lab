"""Typed observation/receipt shapes reused from ``wasm4pm-compat-py`` — a self-
contained pydantic package (see ``/Users/sac/wasm4pm-compat/wasm4pm-compat-py``),
confirmed this session to have zero coupling to mfw or ``praxis-graphlaw`` and no
native/Rust dependency, unlike the Rust ``wasm4pm-compat`` crate that ``mfw-meaning``
pulls in.

This module is the seam: everything else in ``autofde_lab.receipts`` depends on this
file, not on ``pydantic_integration`` directly, so swapping/vendoring the upstream
package later touches one file.

Not the default shape for a scikit-decide planning step: a real rollout step
(``planning_types.PlanStepOutcome``) has no ``id``/``type``/``time``/``relationships`` —
these OCEL/process-mining types are for an explicitly separate, optional downstream
adapter (mapping a planning trajectory into synthetic process-mining events), not for
validating raw solver output. See ``planning_types.py``'s module docstring for the
investigation that established this.
"""

from __future__ import annotations

from pydantic_integration.pydantic_models import (  # noqa: F401 - re-export
    ConformanceResult,
    ConformanceVerdict,
    Evidence,
    OcelEvent,
    OcelEventAttribute,
    OcelLog,
    OcelObject,
    OcelObjectAttribute,
    OcelRelationship,
    OcelType,
    Receipt,
)

__all__ = [
    "ConformanceResult",
    "ConformanceVerdict",
    "Evidence",
    "OcelEvent",
    "OcelEventAttribute",
    "OcelLog",
    "OcelObject",
    "OcelObjectAttribute",
    "OcelRelationship",
    "OcelType",
    "Receipt",
]
