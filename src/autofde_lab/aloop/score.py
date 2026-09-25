# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""``python -m autofde_lab.aloop.score`` -- ALOOP metrics CLI (lane 6).

Subcommands
-----------
``score LOG...``            score one or more logs (OCEL 2.0 JSON or NDJSON).
``corpus [DIR]``            score a synth mutant battery against MANIFEST.json
                            (regenerates the canonical corpus when DIR omitted).
``trials SEED...``          repeated seeded trials + mutant battery + stats;
                            emits the report-form scoreboard (distributions,
                            Wilson 95% intervals, negative controls).
``validate-manifests DIR``  check ALOOP scenario manifests for the required
                            contract fields (id, objective, repository_scope,
                            seeds, scenario_identity, setup, acceptance_criteria,
                            falsifier, expected_outcome_classes, negative_control).

Exit codes: 0 all checks passed; 1 any check failed; 2 usage error. The
scoreboard/receipt JSON goes to stdout or ``--out``; human status to stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from autofde_lab.aloop.metrics import score_corpus, score_log
from autofde_lab.aloop.stats import add_stats, run_trials

REQUIRED_MANIFEST_FIELDS = (
    "id",
    "objective",
    "repository_scope",
    "seeds",
    "scenario_identity",
    "setup",
    "acceptance_criteria",
    "falsifier",
    "expected_outcome_classes",
    "negative_control",
)


def validate_manifests(directory: Path) -> dict[str, Any]:
    """Validate scenario manifests against the ALOOP benchmark contract."""
    results: dict[str, Any] = {}
    ok = True
    for path in sorted(directory.glob("*.json")):
        problems: list[str] = []
        try:
            manifest = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            problems.append(f"unparseable JSON: {exc}")
            manifest = None
        if manifest is not None:
            for field in REQUIRED_MANIFEST_FIELDS:
                if field not in manifest or manifest[field] in (None, "", [], {}):
                    problems.append(f"missing/empty required field: {field}")
            if not str(manifest.get("falsifier", "")).strip():
                problems.append("falsifier must be a non-empty observation that kills the claim")
            nc = manifest.get("negative_control")
            if isinstance(nc, dict) and not nc.get("cases") and not nc.get("requirement"):
                problems.append("negative_control needs cases or requirement")
            if not manifest.get("seeds"):
                problems.append("seeds must be non-empty for repeated trials")
        results[path.name] = {"valid": not problems, "problems": problems}
        ok &= not problems
    return {"directory": str(directory), "manifests": results, "all_valid": ok}


def _emit(payload: Mapping[str, Any], out: Path | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m autofde_lab.aloop.score")
    sub = parser.add_subparsers(dest="command", required=True)

    p_score = sub.add_parser("score", help="score one or more logs")
    p_score.add_argument("logs", nargs="+", type=Path)
    p_score.add_argument("--out", type=Path, default=None)
    p_score.add_argument("--no-corpus", action="store_true",
                         help="skip the mutant battery (MKR/controls)")

    p_corpus = sub.add_parser("corpus", help="score the synth mutant battery")
    p_corpus.add_argument("dir", nargs="?", type=Path, default=None)
    p_corpus.add_argument("--out", type=Path, default=None)

    p_trials = sub.add_parser("trials", help="repeated seeded trials + stats")
    p_trials.add_argument("seeds", nargs="+", type=int)
    p_trials.add_argument("--out", type=Path, default=None)
    p_trials.add_argument("--no-corpus", action="store_true")

    p_val = sub.add_parser("validate-manifests", help="validate scenario manifests")
    p_val.add_argument("directory", type=Path)
    p_val.add_argument("--out", type=Path, default=None)

    args = parser.parse_args(argv)
    out: Path | None = getattr(args, "out", None)

    if args.command == "score":
        scores = [score_log(p) for p in args.logs]
        corpus = None if args.no_corpus else score_corpus()
        from autofde_lab.aloop.metrics import scoreboard

        board = scoreboard(scores, corpus=corpus)
        _emit(board, out)
        passed = all(board["invariants"].values()) and (
            not board["negative_controls"] or all(board["negative_controls"].values())
        )
        sys.stderr.write(
            f"scored {len(scores)} log(s); standing={board['standing']} passed={passed}\n"
        )
        return 0 if passed else 1

    if args.command == "corpus":
        report = score_corpus(args.dir)
        _emit(report, out)
        passed = (report["MKR"]["value"] == 1.0) and all(report["negative_controls"].values())
        sys.stderr.write(
            f"MKR={report['MKR']['killed']}/{report['MKR']['executed']} "
            f"controls={'PASS' if all(report['negative_controls'].values()) else 'FAIL'}\n"
        )
        return 0 if passed else 1

    if args.command == "trials":
        board = add_stats(run_trials(args.seeds, with_corpus=not args.no_corpus))
        _emit(board, out)
        controls = board.get("negative_controls") or {}
        invariants = board.get("invariants") or {}
        passed = bool(invariants) and all(invariants.values()) and controls and all(controls.values())
        sys.stderr.write(
            f"trials={len(args.seeds)} standing={board['standing']} passed={passed}\n"
        )
        return 0 if passed else 1

    if args.command == "validate-manifests":
        report = validate_manifests(args.directory)
        _emit(report, out)
        sys.stderr.write(
            f"manifests valid={sum(1 for r in report['manifests'].values() if r['valid'])}"
            f"/{len(report['manifests'])}\n"
        )
        return 0 if report["all_valid"] else 1

    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
