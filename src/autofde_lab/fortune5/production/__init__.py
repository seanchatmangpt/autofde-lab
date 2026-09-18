"""Fortune-5 Semantic A2A production-system simulation.

The surface is a deterministic simulation/evidence harness.  It does not have
authority over real production infrastructure.
"""

from .artifacts import ArtifactStore, readiness_witness
from .engine import ProductionSimulator, SimulationRun, run_simulation
from .formal import FormalProjection, generate_formal_projection, verify_projection_coherence
from .model import FaultEvent, SimulationSummary, WorldSpec
from .ocel import project_events_to_ocel2, verify_ocel2
from .service import SimulationService
from .world import SCALE_PROFILES, generate_world, with_faults

__all__ = [
    "ArtifactStore",
    "FaultEvent",
    "FormalProjection",
    "ProductionSimulator",
    "SCALE_PROFILES",
    "SimulationRun",
    "SimulationService",
    "SimulationSummary",
    "WorldSpec",
    "generate_formal_projection",
    "generate_world",
    "project_events_to_ocel2",
    "readiness_witness",
    "run_simulation",
    "verify_ocel2",
    "verify_projection_coherence",
    "with_faults",
]
