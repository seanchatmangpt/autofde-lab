"""DMEDI curriculum module: EXPLORE phase -- "TRIZ for New Product Design".

Real curriculum source: Design for Lean Six Sigma Black Belt (DMEDI).
Unlike most files in this directory, "TRIZ for New Product Design" has a REAL implementation
-- not here, but in autofde-lab's own laboratory pipeline
(src/autofde_lab/reasoning/laboratory.py). This file is a real, thin
pointer, not a duplicate implementation -- re-implementing the same logic
in two places would itself be the kind of drift this session's other real
work (wasm4pm-drift-reconciliation-pack) exists to catch.

Real, tested, committed:
laboratory.py section 14 (TRIZParameter, TRIZContradiction,
classify_triz_contradiction, generate_triz_candidates) -- commit
2cfab1453ffded217c7a85b35e0946a216906f17, real tests in
tests/reasoning/test_triz_chicago.py (5 passed).
"""

from __future__ import annotations

MODULE_STANDING = "IMPLEMENTED"
DMEDI_PHASE = "EXPLORE"
CURRICULUM_TOPIC = "TRIZ for New Product Design"

# Real re-export -- see laboratory.py for the actual implementation and
# tests/reasoning/ for the real, passing Chicago-style test suite.
from autofde_lab.reasoning.laboratory import (
    TRIZParameter,
    TRIZContradiction,
    TRIZResolutionApplicability,
    classify_triz_contradiction,
    generate_triz_candidates,
)
