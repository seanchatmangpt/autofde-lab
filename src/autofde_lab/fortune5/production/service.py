"""Application service layer for the Fortune-5 production simulator."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Mapping

from .artifacts import readiness_witness
from .engine import SimulationRun, run_simulation
from .ocel import project_events_to_ocel2
from .world import generate_world


@dataclass(frozen=True, slots=True)
class RunView:
    run: SimulationRun

    def summary(self) -> dict[str, object]:
        witness = readiness_witness(self.run)
        return {
            "run_id": self.run.run_id,
            "summary": self.run.summary.canonical(),
            "readiness": witness.canonical(),
            "world": {
                "scenario_id": self.run.world.scenario_id,
                "world_digest": self.run.world.world_digest,
                "scale_profile": self.run.world.scale_profile,
                "regions": len(self.run.world.regions),
                "services": len(self.run.world.services),
                "faults": len(self.run.world.faults),
            },
            "formal": {
                "projection_digest": self.run.projection.projection_digest,
                "world_digest": self.run.projection.world_digest,
            },
        }

    def ocel(self) -> dict[str, object]:
        return project_events_to_ocel2(
            run_id=self.run.run_id,
            world=self.run.world,
            events=self.run.events,
            prepared=self.run.prepared_receipts,
            final=self.run.final_receipts,
            routes=tuple(self.run.known_routes),
        )


class SimulationService:
    """Thread-safe in-memory facade used by CLI and HTTP surfaces."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._runs: dict[str, SimulationRun] = {}

    def start(
        self,
        *,
        seed: int = 1,
        rounds: int = 40,
        scale_profile: str = "fortune5",
        scenario_choices: Mapping[str, str] | None = None,
        fault_density: float = 0.12,
    ) -> RunView:
        world = generate_world(
            seed=seed,
            scale_profile=scale_profile,
            scenario_choices=scenario_choices,
            fault_density=fault_density,
            horizon_rounds=rounds,
        )
        run = run_simulation(world, rounds=rounds)
        with self._lock:
            self._runs[run.run_id] = run
        return RunView(run)

    def get(self, run_id: str) -> RunView:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(run_id)
            return RunView(self._runs[run_id])

    def list(self) -> tuple[dict[str, object], ...]:
        with self._lock:
            return tuple(
                RunView(self._runs[key]).summary() for key in sorted(self._runs)
            )


__all__ = ["RunView", "SimulationService"]
