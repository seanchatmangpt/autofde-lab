"""CLI: python -m autofde_lab.simulation.doctrine_lab --out DIR [--seeds ..] [--worlds N|all]."""

from __future__ import annotations

import argparse
import json

from . import ALL_WORLDS, run_lab, verify_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--seeds", type=int, nargs="+", default=[2030, 2031])
    parser.add_argument(
        "--worlds", default="9", help="first N worlds of the 243 product, or 'all'"
    )
    parser.add_argument("--ordinals", type=int, nargs="*", default=None)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument(
        "--replay", action="store_true", help="re-execute the run inside verify_run"
    )
    args = parser.parse_args(argv)
    worlds = ALL_WORLDS if args.worlds == "all" else ALL_WORLDS[: int(args.worlds)]
    report = run_lab(
        args.out,
        seeds=args.seeds,
        worlds=worlds,
        ordinals=args.ordinals or None,
        rounds=args.rounds,
    )
    run_check = verify_run(args.out, replay=args.replay)
    print(
        json.dumps(
            {
                "evidence_ceiling": report["evidence_ceiling"],
                "authority": report["authority"],
                "episode_count": report["episode_count"],
                "world_count": report["world_count"],
                "matrix_digest": report["matrix_digest"],
                "report_digest": report["report_digest"],
                "ledger": report["ledger"],
                "clusters": len(report["primitive_equivalence_clusters"]),
                "selection": None,
                "verify_run": {
                    "valid": run_check.valid,
                    "replayed": args.replay,
                    "failures": list(run_check.failures),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["ledger"]["valid"] and run_check.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
