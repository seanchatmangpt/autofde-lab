#!/usr/bin/env python3
"""Deterministic benchmark for the doctrine lab's run, seal and verify path.

Every timed sample is first required to be semantically correct: the run's
``verify_run`` must be valid, replay must be valid, and every episode must pass
``admit_for_seal``. Timing a wrong run is a benchmark failure, not a fast result.

Measured (median over ``--samples`` wall-clock samples, perf_counter_ns):

* ``run_lab``            full matrix: episodes, OCEL logs, seal, report;
* ``admit_for_seal``     per-episode admission (catalog binding + digests);
* ``verify_run``         no-replay verification (catalog + authority binding);
* ``verify_run_replay``  verification with full re-execution.

``REGRESSION_BOUNDS`` are per-unit ceilings (ms) the test suite enforces; they
sit roughly 10x above the numbers recorded on the authoring host so that a
genuine complexity regression (e.g. a quadratic ledger scan) fails while host
noise does not. Evidence ceiling REPO_LOCAL_FIXTURE.

Subject identity: a commit cannot contain its own hash, so the receipt names the
code it timed by ``source_tree_sha256``, a sha256 over (path, bytes) of every
file in the doctrine_lab package and this script, recomputable from any
checkout. ``source_identity`` recomputes it; the test suite refuses a committed
receipt whose digest differs from the tree it is committed in.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter_ns
from typing import Callable

from autofde_lab.simulation.doctrine_lab import (
    ALL_WORLDS,
    admit_for_seal,
    episode_log,
    load_catalog,
    log_sha256,
    run_doctrine_matrix,
    run_lab,
    verify_run,
)

SCHEMA = "autofde-lab.simulation.doctrine-lab.bench/v1"
ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (
    Path("src/autofde_lab/simulation/doctrine_lab"),
    Path("benchmarks/doctrine_lab_bench.py"),
)
SOURCE_SUFFIXES = frozenset({".py", ".json"})
# ms per unit; see module docstring
REGRESSION_BOUNDS = {
    "run_lab_ms_per_episode": 40.0,
    "admit_for_seal_ms_per_episode": 10.0,
    "verify_run_ms_per_record": 5.0,
    "verify_run_replay_ms_per_record": 40.0,
}


def source_identity(root: Path = ROOT) -> dict[str, object]:
    """sha256 over sorted (relative path, bytes) of the timed source files."""
    files: list[Path] = []
    for entry in SOURCE_ROOTS:
        path = root / entry
        if path.is_file():
            files.append(path)
        else:
            files.extend(
                p
                for p in path.rglob("*")
                if p.is_file()
                and p.suffix in SOURCE_SUFFIXES
                and "__pycache__" not in p.parts
            )
    digest = hashlib.sha256()
    names = sorted(p.relative_to(root).as_posix() for p in files)
    for name in names:
        data = (root / name).read_bytes()
        digest.update(f"{name}\0{len(data)}\0".encode())
        digest.update(data)
    return {"source_tree_sha256": digest.hexdigest(), "source_files": len(names)}


def _median_ms(fn: Callable[[], object], samples: int) -> float:
    times = []
    for _ in range(samples):
        start = perf_counter_ns()
        fn()
        times.append((perf_counter_ns() - start) / 1e6)
    return statistics.median(times)


def run_bench(
    *, seeds: list[int], worlds: int, samples: int, workdir: Path
) -> dict[str, object]:
    catalog = load_catalog()
    world_set = ALL_WORLDS[:worlds]
    strategies = catalog.operationalized
    episodes = len(seeds) * len(world_set) * len(strategies)

    counter = iter(range(10**6))

    def lab() -> dict:
        return run_lab(workdir / f"run{next(counter)}", seeds=seeds, worlds=world_set)

    report = lab()
    out = workdir / "run0"
    if report["episode_count"] != episodes:
        raise AssertionError("episode count differs from the matrix size")
    check = verify_run(out)
    replayed = verify_run(out, replay=True)
    if not (check.valid and replayed.valid):
        raise AssertionError(f"bench subject is not valid: {check} {replayed}")

    result = run_doctrine_matrix(seeds, world_set, strategies, catalog=catalog)
    sealed = [(e, log_sha256(episode_log(e))) for e in result.episodes]

    def admit_all() -> None:
        for episode, digest in sealed:
            admit_for_seal(episode, digest)

    measured = {
        "run_lab_ms": _median_ms(lab, samples),
        "admit_for_seal_ms": _median_ms(admit_all, samples),
        "verify_run_ms": _median_ms(lambda: verify_run(out), samples),
        "verify_run_replay_ms": _median_ms(
            lambda: verify_run(out, replay=True), max(1, samples // 2)
        ),
    }
    per_unit = {
        "run_lab_ms_per_episode": measured["run_lab_ms"] / episodes,
        "admit_for_seal_ms_per_episode": measured["admit_for_seal_ms"] / episodes,
        "verify_run_ms_per_record": measured["verify_run_ms"] / episodes,
        "verify_run_replay_ms_per_record": measured["verify_run_replay_ms"] / episodes,
    }
    within = {k: per_unit[k] <= bound for k, bound in REGRESSION_BOUNDS.items()}
    return {
        "schema": SCHEMA,
        "evidence_ceiling": "REPO_LOCAL_FIXTURE",
        "authority": "NONE",
        "authority_ceiling": "CONSTRUCT",
        "subject": {
            "catalog_sha256": catalog.sha256,
            "report_digest": report["report_digest"],
            "matrix_digest": report["matrix_digest"],
            "ledger_tail_digest": report["ledger"]["tail_digest"],
            **source_identity(),
        },
        "workload": {
            "seeds": seeds,
            "worlds": worlds,
            "strategies": len(strategies),
            "episodes": episodes,
            "samples": samples,
        },
        "host": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "median_ms": {k: round(v, 3) for k, v in measured.items()},
        "per_unit_ms": {k: round(v, 4) for k, v in per_unit.items()},
        "regression_bounds_ms": REGRESSION_BOUNDS,
        "within_bounds": within,
        "passed": all(within.values()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[2030, 2031])
    parser.add_argument("--worlds", type=int, default=9)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--out", type=Path, default=None, help="write receipt JSON")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        receipt = run_bench(
            seeds=args.seeds,
            worlds=args.worlds,
            samples=args.samples,
            workdir=Path(tmp),
        )
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"sha256 {hashlib.sha256(text.encode()).hexdigest()} {args.out}")
    print(text, end="")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
