"""Deterministic benchmark for the ABB -> SBB architecture qualification court.

Measures, on the real ``autofde_lab.enterprise_architecture`` functions (no doubles):

* throughput: median ns per ``qualify``, per ``replay_refusals`` and per 64-candidate
  ``frontier`` call over ``--repeats`` timed rounds;
* replay determinism: number of distinct receipt digests over ``--replays`` independent
  re-qualifications of one exact subject (must be exactly 1);
* falsifier coverage: fraction of named adversarial mutation operators whose output is
  REFUSED (must be 1.0); every operator is listed with its observed refusal codes.

Timings are observations of this host, never capability claims; the regression bound
lives in ``tests/fortune5/test_architecture_qualification_bench.py``.

usage: python benchmarks/architecture_qualification.py [--repeats N] [--replays N]
       [--output path.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from dataclasses import replace
from pathlib import Path
from statistics import median

from autofde_lab.enterprise_architecture import (
    DIMENSIONS,
    ArchitectureContract,
    CandidateSBB,
    Standing,
    digest,
    frontier,
    qualify,
    replay_refusals,
)

SCHEMA = "autofde.architecture-qualification-bench.v1"

CONTRACT = ArchitectureContract(
    abb_digest=digest({"abb": "bench:order-to-cash"}),
    contract_digest=digest({"contract": "bench:order-to-cash/v1"}),
    authority_ceiling="CONSTRUCT",
)


def valid_candidate(index: int = 0) -> CandidateSBB:
    return CandidateSBB(
        candidate_id=f"sbb:{index:03d}",
        abb_digest=CONTRACT.abb_digest,
        contract_digest=CONTRACT.contract_digest,
        exact_subject_digest=digest({"subject": index}),
        mutable=False,
        authority="CONSTRUCT",
        evidence=(f"evidence:run-{index}",),
        dimensions={dimension: True for dimension in DIMENSIONS},
    )


def _dims(**changes) -> dict:
    values = {dimension: True for dimension in DIMENSIONS}
    values.update(changes)
    return values


def mutation_operators() -> dict[str, CandidateSBB]:
    """Named adversarial worlds; each must be REFUSED by the court."""

    base = valid_candidate()
    worlds = {
        "abb_mismatch": replace(base, abb_digest=digest("other-abb")),
        "stale_contract": replace(base, contract_digest=digest("contract/v0")),
        "mutable_subject": replace(base, mutable=True),
        "mutable_truthy_string": replace(base, mutable="false"),
        "missing_subject": replace(base, exact_subject_digest=""),
        "malformed_subject_tag": replace(base, exact_subject_digest="latest"),
        "malformed_subject_short": replace(
            base, exact_subject_digest="sha256:" + "a" * 63
        ),
        "missing_evidence": replace(base, evidence=()),
        "blank_evidence": replace(base, evidence=("",)),
        "duplicate_evidence": replace(base, evidence=("e:1", "e:1")),
        "authority_do": replace(base, authority="DO"),
        "authority_unknown": replace(base, authority="ROOT"),
        "blank_candidate_id": replace(base, candidate_id=""),
        "undeclared_dimension": replace(base, dimensions=_dims(semantics=True)),
        "malformed_dimension": replace(base, dimensions=_dims(effect="yes")),
        "vendor_as_abb_subject": replace(
            base, exact_subject_digest=CONTRACT.abb_digest
        ),
        "vendor_as_abb_kind": replace(base, kind="VENDOR"),
        "pack_as_ea_subject": replace(
            base, exact_subject_digest=CONTRACT.contract_digest
        ),
        "pack_as_ea_kind": replace(base, kind="PACK"),
        "unknown_kind": replace(base, kind="sbb"),
        "evidence_bare_string": replace(base, evidence="e:1"),
        "evidence_unhashable_entry": replace(base, evidence=(["e:1"],)),
        "dimensions_not_mapping": replace(base, dimensions=list(DIMENSIONS)),
        "authority_unhashable": replace(base, authority=["DO"]),
    }
    for dimension in DIMENSIONS:
        worlds[f"{dimension}_incompatible"] = replace(
            base, dimensions=_dims(**{dimension: False})
        )
    return worlds


def _time_ns(fn, repeats: int, inner: int) -> float:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            fn()
        samples.append((time.perf_counter_ns() - start) / inner)
    return float(median(samples))


def run(repeats: int = 30, replays: int = 2000) -> dict:
    subject = valid_candidate()
    receipt = qualify(CONTRACT, subject)
    pool = tuple(valid_candidate(i) for i in range(64))

    replay_digests = {qualify(CONTRACT, subject).receipt_digest for _ in range(replays)}
    replay_clean = sum(
        1
        for _ in range(min(replays, 200))
        if not replay_refusals(CONTRACT, subject, receipt)
    )

    operators = mutation_operators()
    falsifiers = {}
    for name, world in sorted(operators.items()):
        observed = qualify(CONTRACT, world)
        falsifiers[name] = {
            "standing": observed.standing.value,
            "refusal_codes": list(observed.refusal_codes),
        }
    refused = sum(1 for f in falsifiers.values() if f["standing"] == "REFUSED")

    reversed_pool = tuple(reversed(pool))
    order_invariant = frontier(CONTRACT, pool) == frontier(CONTRACT, reversed_pool)

    return {
        "schema": SCHEMA,
        "authority": "NONE",
        "evidence_ceiling": "HOST_LOCAL_TIMING",
        "host": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "parameters": {"repeats": repeats, "replays": replays, "frontier_size": 64},
        "throughput_ns": {
            "qualify_median": _time_ns(
                lambda: qualify(CONTRACT, subject), repeats, 200
            ),
            "replay_median": _time_ns(
                lambda: replay_refusals(CONTRACT, subject, receipt), repeats, 100
            ),
            "frontier64_median": _time_ns(lambda: frontier(CONTRACT, pool), repeats, 5),
        },
        "replay_determinism": {
            "replays": replays,
            "distinct_receipt_digests": len(replay_digests),
            "clean_replays": replay_clean,
            "receipt_digest": receipt.receipt_digest,
            "qualified": receipt.standing is Standing.QUALIFIED,
        },
        "frontier_order_invariant": order_invariant,
        "falsifier_coverage": {
            "operators": len(falsifiers),
            "refused": refused,
            "coverage": refused / len(falsifiers),
            "results": falsifiers,
        },
        "court_source_sha256": "sha256:"
        + hashlib.sha256(
            Path(sys.modules[qualify.__module__].__file__).read_bytes()
        ).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--replays", type=int, default=2000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = run(args.repeats, args.replays)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    coverage = report["falsifier_coverage"]["coverage"]
    determinism = report["replay_determinism"]["distinct_receipt_digests"]
    return 0 if coverage == 1.0 and determinism == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
