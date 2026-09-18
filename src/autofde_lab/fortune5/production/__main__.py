"""CLI for the Fortune-5 Semantic A2A production-system simulation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .artifacts import ArtifactStore, readiness_witness
from .engine import run_simulation
from .ocel import project_events_to_ocel2, verify_ocel2
from .server import serve
from .world import SCALE_PROFILES, generate_world


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--seed", type=int, default=1)
    run_p.add_argument("--rounds", type=int, default=40)
    run_p.add_argument("--scale", choices=tuple(SCALE_PROFILES), default="fortune5")
    run_p.add_argument("--fault-density", type=float, default=0.12)
    run_p.add_argument("--artifacts", type=Path)

    world_p = sub.add_parser("world")
    world_p.add_argument("--seed", type=int, default=1)
    world_p.add_argument("--scale", choices=tuple(SCALE_PROFILES), default="fortune5")

    serve_p = sub.add_parser("serve")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8080)

    args = parser.parse_args(argv)
    if args.command == "serve":
        serve(args.host, args.port)
        return 0
    if args.command == "world":
        world = generate_world(seed=args.seed, scale_profile=args.scale)
        print(json.dumps(world.canonical, sort_keys=True))
        return 0

    world = generate_world(
        seed=args.seed,
        scale_profile=args.scale,
        fault_density=args.fault_density,
        horizon_rounds=args.rounds,
    )
    run = run_simulation(world, rounds=args.rounds)
    ocel = project_events_to_ocel2(
        run_id=run.run_id,
        world=run.world,
        events=run.events,
        prepared=run.prepared_receipts,
        final=run.final_receipts,
        routes=tuple(run.known_routes),
    )
    court = verify_ocel2(ocel)
    witness = readiness_witness(run)
    payload = {
        "summary": run.summary.canonical(),
        "ocel_court": court,
        "readiness": witness.canonical(),
        "projection": {
            "world_digest": run.projection.world_digest,
            "projection_digest": run.projection.projection_digest,
        },
    }
    if args.artifacts is not None:
        payload["artifact_manifest"] = ArtifactStore(args.artifacts).persist(run)
    print(json.dumps(payload, sort_keys=True))
    return 0 if court["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
