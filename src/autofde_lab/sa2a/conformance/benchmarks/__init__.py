"""SA2A Conformance Benchmarks Harness (RFC-SA2A-002 v26.9.16 SA2A-B1..B10).

Chicago Zero-Mock Standard:
- Real plant components, real disk I/O, genuine brokers and boundaries.
- Zero unittest.mock / Mock / MagicMock.
- Anti-Oracle Rule: No golden OCEL traces or snapshot oracles.
"""

from __future__ import annotations

from autofde_lab.sa2a.conformance.benchmarks.harness import (
    SA2A_B1_ADMISSION,
    SA2A_B2_LOGIC_CLOSURE,
    SA2A_B3_HOOK_REFLEX,
    SA2A_B4_PLANNING_PROJECTION,
    SA2A_B5_CONSEQUENCE_LATENCY,
    SA2A_B6_REACTIVE_CASCADE,
    SA2A_B7_PORTABILITY,
    SA2A_B8_REPLAY_VERIFICATION,
    SA2A_B9_OCEL_OVERHEAD,
    SA2A_B10_RECOVERY_RECONCILIATION,
    ALL_BENCHMARKS,
    BenchmarkHarness,
    BenchmarkMetric,
    BenchmarkResult,
    EnvironmentReceipt,
    run_all_benchmarks,
)

__all__ = [
    "SA2A_B1_ADMISSION",
    "SA2A_B2_LOGIC_CLOSURE",
    "SA2A_B3_HOOK_REFLEX",
    "SA2A_B4_PLANNING_PROJECTION",
    "SA2A_B5_CONSEQUENCE_LATENCY",
    "SA2A_B6_REACTIVE_CASCADE",
    "SA2A_B7_PORTABILITY",
    "SA2A_B8_REPLAY_VERIFICATION",
    "SA2A_B9_OCEL_OVERHEAD",
    "SA2A_B10_RECOVERY_RECONCILIATION",
    "ALL_BENCHMARKS",
    "BenchmarkHarness",
    "BenchmarkMetric",
    "BenchmarkResult",
    "EnvironmentReceipt",
    "run_all_benchmarks",
]
