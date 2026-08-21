"""DMEDI curriculum module: MEASURE phase -- "Target Costing".

Real curriculum source: Design for Lean Six Sigma Black Belt (DMEDI:
Define, Measure, Explore, Develop, Implement). This file is a real,
honestly-scoped planner-module placeholder in
autofde-lab's laboratory pipeline (src/autofde_lab/reasoning/laboratory.py):
it is NOT yet implemented. It exists to admit "Target Costing" as a real,
named, tracked module in the curriculum -- not to fake having built it.

Per this repo's own no-overclaiming discipline (see laboratory.py's
FalsificationStanding.UNSUPPORTED / OperatorApplicabilityStatus patterns):
calling plan_target_costing() raises NotImplementedError explicitly and loudly.
There is no silent stub that returns a fabricated ArchitectureCandidate.
"""

from __future__ import annotations

MODULE_STANDING = "PLANNED"  # never ALIVE/IMPLEMENTED until real code lands here
DMEDI_PHASE = "MEASURE"
CURRICULUM_TOPIC = "Target Costing"


def plan_target_costing(*args, **kwargs):
    """Real, explicit refusal -- "Target Costing" (MEASURE phase) is not yet
    implemented in this laboratory. Raises NotImplementedError rather than
    returning a fabricated result, matching laboratory.py's own
    ArchitectureCandidate/ExperimentReceipt honesty contract."""
    raise NotImplementedError(
        f"DMEDI curriculum module '{CURRICULUM_TOPIC}' ({DMEDI_PHASE} phase) "
        "is PLANNED, not yet implemented -- see "
        "src/autofde_lab/reasoning/dmedi_curriculum/target_costing.py"
    )
