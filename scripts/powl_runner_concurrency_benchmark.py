#!/usr/bin/env python3
"""Real, measured benchmark of `autofde_lab.powl.guard_executor.execute`'s
`max_workers` concurrency (see `guard_executor.py`'s "Real concurrency for
independent `PartialOrder` branches" design section).

Two real workloads, because the answer to "what's the max useful
concurrency" is workload-dependent, not a single number:

- I/O-bound (`--workload io`, default): each atom sleeps for
  `--work-seconds`, simulating a real gated tool call (network round-trip,
  subprocess wait). The GIL is released during `time.sleep`, so real
  wall-clock speedup up to `max_workers == ready_set_width` is expected.
- CPU-bound (`--workload cpu`): each atom runs a real, un-vectorized Python
  busy loop for `--cpu-iterations` iterations. CPython's GIL serializes
  bytecode execution across threads, so this workload is expected to show
  little or no real speedup, and thread-pool overhead can make it *worse*
  past a small `max_workers` -- the benchmark measures and reports this
  real number, not an assumption.

Every timing here is a real `time.perf_counter()` measurement of a real
`execute()` call against a real `PartialOrder` of independent `Atom`s (no
`OrderEdge`s -- one single ready set of the requested width) -- never
estimated or interpolated.

Usage:
    .venv/bin/python scripts/powl_runner_concurrency_benchmark.py
    .venv/bin/python scripts/powl_runner_concurrency_benchmark.py --workload cpu
    .venv/bin/python scripts/powl_runner_concurrency_benchmark.py --ready-width 64 --max-workers 1 2 4 8 16 32 64
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autofde_lab.powl.algebra import Atom, PartialOrder  # noqa: E402
from autofde_lab.powl.guard_executor import execute  # noqa: E402


def _io_invoker(work_seconds: float):
    def invoker(atom: Atom) -> str:
        time.sleep(work_seconds)
        return atom.label

    return invoker


def _cpu_invoker(iterations: int):
    def invoker(atom: Atom) -> str:
        total = 0
        for i in range(iterations):
            total += i * i
        return f"{atom.label}:{total}"

    return invoker


def _build_ready_set(width: int) -> PartialOrder:
    """`width` fully independent atoms -- no `OrderEdge`s, so the executor's
    real Kahn's-algorithm walk sees exactly one ready set of size `width`."""
    return PartialOrder(children=tuple(Atom(label=f"a{i}") for i in range(width)))


def _run_once(node: PartialOrder, invoker, max_workers: int) -> float:
    start = time.perf_counter()
    execute(node, guard_evaluator=lambda n, a: True, atom_invoker=invoker, max_choice_transitions=1, max_workers=max_workers)
    return time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workload", choices=["io", "cpu"], default="io")
    parser.add_argument("--work-seconds", type=float, default=0.05, help="io workload: real sleep per atom")
    parser.add_argument("--cpu-iterations", type=int, default=2_000_000, help="cpu workload: real busy-loop iterations per atom")
    parser.add_argument("--ready-width", type=int, default=16, help="number of independent atoms in the one ready set")
    parser.add_argument("--max-workers", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32, 64])
    parser.add_argument("--repeats", type=int, default=3, help="real repeats per max_workers value; report the median")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    node = _build_ready_set(args.ready_width)
    invoker = _io_invoker(args.work_seconds) if args.workload == "io" else _cpu_invoker(args.cpu_iterations)

    results: list[dict[str, object]] = []
    baseline: float | None = None
    for mw in args.max_workers:
        samples = sorted(_run_once(node, invoker, mw) for _ in range(args.repeats))
        median = samples[len(samples) // 2]
        if baseline is None:
            baseline = median
        results.append(
            {
                "max_workers": mw,
                "median_seconds": round(median, 6),
                "samples_seconds": [round(s, 6) for s in samples],
                "speedup_vs_max_workers_1": round(baseline / median, 3) if median > 0 else float("inf"),
            }
        )

    report = {
        "workload": args.workload,
        "ready_width": args.ready_width,
        "work_seconds": args.work_seconds if args.workload == "io" else None,
        "cpu_iterations": args.cpu_iterations if args.workload == "cpu" else None,
        "repeats": args.repeats,
        "results": results,
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"workload={args.workload} ready_width={args.ready_width}", end="")
    if args.workload == "io":
        print(f" work_seconds={args.work_seconds}")
    else:
        print(f" cpu_iterations={args.cpu_iterations}")
    print(f"{'max_workers':>12}  {'median_s':>10}  {'speedup':>8}  samples_s")
    for r in results:
        samples = ", ".join(f"{s:.4f}" for s in r["samples_seconds"])  # type: ignore[union-attr]
        print(f"{r['max_workers']:>12}  {r['median_seconds']:>10.4f}  {r['speedup_vs_max_workers_1']:>7.2f}x  [{samples}]")


if __name__ == "__main__":
    main()
