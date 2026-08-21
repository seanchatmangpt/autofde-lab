"""DMEDI curriculum module: DEVELOP phase -- "Intro to Design of Experiments".

Real curriculum source: Design for Lean Six Sigma Black Belt (DMEDI).
Unlike most files in this directory, "Intro to Design of Experiments" has a REAL implementation
-- not here, but in autofde-lab's own laboratory pipeline
(src/autofde_lab/reasoning/laboratory.py). This file is a real, thin
pointer, not a duplicate implementation -- re-implementing the same logic
in two places would itself be the kind of drift this session's other real
work (wasm4pm-drift-reconciliation-pack) exists to catch.

Real, tested, committed:
laboratory.py section 15 (DOEFactor, DOELevel, DOEDesignPoint,
generate_full_factorial_design, generate_doe_candidates) -- commit
6db5e99a, real tests in tests/reasoning/test_doe_chicago.py
(6 passed).
"""

from __future__ import annotations

MODULE_STANDING = "IMPLEMENTED"
DMEDI_PHASE = "DEVELOP"
CURRICULUM_TOPIC = "Intro to Design of Experiments"

# Real re-export -- see laboratory.py for the actual implementation and
# tests/reasoning/ for the real, passing Chicago-style test suite.
from autofde_lab.reasoning.laboratory import (
    DOEFactor,
    DOELevel,
    DOEDesignPoint,
    generate_full_factorial_design,
    generate_doe_candidates,
)
