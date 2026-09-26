#!/usr/bin/env python3
"""Audit/search DGF evidence projections before agent deployment."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from autofde_lab.evidence.dgf_information_projection import (
    audit_dgf_projection,
    search_min_cost_sufficient_projection,
    search_sufficient_dgf_projections,
)


def _report(audit):
    return {
        "observation_paths": list(audit.observation_paths),
        "sufficient": audit.sufficient,
        "case_count": audit.report.case_count,
        "observation_class_count": audit.report.observation_class_count,
        "collision_class_count": audit.report.collision_class_count,
        "obstruction_count": audit.report.obstruction_count,
        "witnesses": [asdict(row) for row in audit.report.witnesses],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--candidate-path", action="append", default=[])
    parser.add_argument("--candidate-cost", action="append", default=[])
    parser.add_argument("--max-width", type=int, default=3)
    args = parser.parse_args()

    if args.candidate_cost:
        costs = {}
        for raw in args.candidate_cost:
            try:
                path, value = raw.rsplit("=", 1)
                costs[path] = float(value)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"CANDIDATE_COST_MUST_BE_PATH_EQUALS_FLOAT:{raw}"
                ) from exc

        plan = search_min_cost_sufficient_projection(
            args.dataset_root,
            candidate_costs=costs,
            max_width=args.max_width,
        )
        payload = {
            "schema": "autofde.dgf-evidence-cost-plan/1",
            "standing": "ADMITTED" if plan is not None else "REFUSED(EVIDENCE_CEILING)",
            "plan": (
                {
                    **_report(plan.audit),
                    "total_cost": plan.total_cost,
                }
                if plan is not None
                else None
            ),
        }
        exit_code = 0 if plan is not None else 2
    elif args.candidate_path:
        audits = search_sufficient_dgf_projections(
            args.dataset_root,
            candidate_paths=tuple(args.candidate_path),
            max_width=args.max_width,
        )
        payload = {
            "schema": "autofde.dgf-evidence-search/1",
            "standing": "ADMITTED" if audits else "REFUSED(EVIDENCE_CEILING)",
            "minimal_sufficient_projections": [_report(audit) for audit in audits],
        }
        exit_code = 0 if audits else 2
    else:
        audit = audit_dgf_projection(
            args.dataset_root,
            observation_paths=tuple(args.path),
        )
        payload = {
            "schema": "autofde.dgf-evidence-audit/1",
            "standing": audit.report.standing,
            "audit": _report(audit),
        }
        exit_code = 0 if audit.sufficient else 2

    print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
