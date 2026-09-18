"""Durable artifact bundle and Fortune-5 readiness witness for simulation runs."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ..readiness import F5ReadinessVerifier, REQUIRED_GATES, build_submission, evidence_digest
from .engine import SimulationRun
from .model import canonical_json, digest
from .ocel import project_events_to_ocel2, verify_ocel2


def readiness_witness(run: SimulationRun):
    """Produce the existing Fortune-5 TTF5-AR technical witness from run evidence."""
    ocel = project_events_to_ocel2(
        run_id=run.run_id,
        world=run.world,
        events=run.events,
        prepared=run.prepared_receipts,
        final=run.final_receipts,
        routes=tuple(run.known_routes),
    )
    court = verify_ocel2(ocel)
    projection_ok = run.projection.world_digest == run.world.world_digest
    budgets_ok = not (
        run.summary.cost_budget_violations
        or run.summary.energy_budget_violations
        or run.summary.carbon_budget_violations
    )
    retirement_observed = run.summary.known_route_hits > 0 and run.summary.known_routes > 0

    facts = {
        "identity": run.world.world_digest == run.summary.world_digest,
        "strategy": projection_ok,
        "business": len(run.world.services) > 0,
        "information": len(ocel.get("objects", [])) > 0,
        "application": len(run.world.services) > 0,
        "technology": len(run.world.regions) >= 2,
        "governance": bool(run.world.authority_grants),
        "security": court["authority_violations"] == 0,
        "transition": projection_ok,
        "production": run.summary.rounds > 0 and budgets_ok,
        "actuation": court["unreceipted_actuations"] == 0 and court["duplicate_effects"] == 0,
        "evidence": bool(court["ok"]) and retirement_observed,
    }
    evidence_by_gate = {
        gate: (
            "PASS" if facts.get(gate, False) else "FAIL",
            evidence_digest({
                "gate": gate,
                "facts": facts,
                "run": run.summary.canonical(),
            }),
        )
        for gate in REQUIRED_GATES
    }
    submission = build_submission(
        benchmark_id="fortune5-sa2a-production-simulation",
        benchmark_version="v26.9.18",
        scenario_digest=run.world.world_digest,
        admitted_observation_digest=digest({
            "events": [event.canonical() for event in run.events],
            "projection": run.projection.projection_digest,
        }),
        started_at_ns=0,
        submitted_at_ns=max((event.timestamp_ns for event in run.events), default=0),
        evidence_by_gate=evidence_by_gate,
    )
    return F5ReadinessVerifier().verify(
        submission, verified_at_ns=submission.submitted_at_ns + 1
    )


class ArtifactStore:
    """Atomic file-system store for simulation run bundles."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = canonical_json(value) + "\n"
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def persist(self, run: SimulationRun) -> dict[str, str]:
        run_dir = self.root / run.run_id.replace(":", "_")
        ocel = project_events_to_ocel2(
            run_id=run.run_id,
            world=run.world,
            events=run.events,
            prepared=run.prepared_receipts,
            final=run.final_receipts,
            routes=tuple(run.known_routes),
        )
        witness = readiness_witness(run)
        files: dict[str, object] = {
            "world.json": run.world.canonical,
            "formal.json": run.projection.canonical(),
            "events.json": [event.canonical() for event in run.events],
            "otlp-spans.json": [span.canonical() for span in run.spans],
            "prepared-receipts.json": [
                receipt.canonical() for receipt in run.prepared_receipts
            ],
            "final-receipts.json": [
                receipt.canonical() for receipt in run.final_receipts
            ],
            "ocel2.json": ocel,
            "summary.json": run.summary.canonical(),
            "readiness.json": witness.canonical(),
            "final-state.json": [
                [service_id, state] for service_id, state in run.final_state
            ],
        }
        manifest: dict[str, str] = {}
        for name, value in files.items():
            self._write_json(run_dir / name, value)
            manifest[name] = digest(value)
        manifest["bundle_digest"] = digest(manifest)
        self._write_json(run_dir / "manifest.json", manifest)
        return manifest

    def verify(self, run_id: str) -> dict[str, Any]:
        run_dir = self.root / run_id.replace(":", "_")
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(run_id)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        failures: list[str] = []
        for name, expected in manifest.items():
            if name == "bundle_digest":
                continue
            path = run_dir / name
            if not path.exists():
                failures.append(f"MISSING:{name}")
                continue
            actual = digest(json.loads(path.read_text(encoding="utf-8")))
            if actual != expected:
                failures.append(f"DIGEST_MISMATCH:{name}")
        expected_bundle = manifest.get("bundle_digest")
        actual_bundle = digest({
            k: v for k, v in manifest.items() if k != "bundle_digest"
        })
        if expected_bundle != actual_bundle:
            failures.append("BUNDLE_DIGEST_MISMATCH")
        return {"ok": not failures, "failures": failures, "manifest": manifest}


__all__ = ["ArtifactStore", "readiness_witness"]
