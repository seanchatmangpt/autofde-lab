#!/usr/bin/env python3
"""Deterministic stress harness for the semantic-parts benchmark engine."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path

from autofde_lab.semantic_parts import SubstitutionCase, evaluate_substitution_discovery


def generate_cases(count: int, seed: int) -> tuple[SubstitutionCase, ...]:
    if count < 1:
        raise ValueError("count must be >= 1")

    rng = random.Random(seed)
    cases: list[SubstitutionCase] = []

    for index in range(count):
        subject = f"subject:{index}"
        verified = f"verified:{index}"
        distractors = [f"distractor:{index}:{slot}" for slot in range(8)]
        rng.shuffle(distractors)

        mode = index % 6
        if mode in (0, 1, 2):
            lexical = tuple(distractors[:5])
            semantic = (verified, *distractors[:4])
        elif mode == 3:
            lexical = (verified, *distractors[:4])
            semantic = tuple(distractors[:5])
        elif mode == 4:
            lexical = (verified, *distractors[:4])
            semantic = (verified, *distractors[4:8])
        else:
            lexical = tuple(distractors[:5])
            semantic = tuple(distractors[3:8])

        cases.append(
            SubstitutionCase(
                subject_id=subject,
                verified_equivalents=frozenset({verified}),
                lexical_candidates=lexical,
                semantic_candidates=semantic,
            )
        )

    return tuple(cases)


def _case_digest(cases: tuple[SubstitutionCase, ...]) -> str:
    digest = hashlib.sha256()
    for case in cases:
        payload = {
            "subject_id": case.subject_id,
            "verified_equivalents": sorted(case.verified_equivalents),
            "lexical_candidates": list(case.lexical_candidates),
            "semantic_candidates": list(case.semantic_candidates),
        }
        digest.update(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=26_092_026)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    cases = generate_cases(args.cases, args.seed)
    started = time.perf_counter()
    result = evaluate_substitution_discovery(cases, k=args.k)
    elapsed = time.perf_counter() - started

    receipt = {
        "schema": "autofde.semantic-substitution-stress.v1",
        "case_count": len(cases),
        "seed": args.seed,
        "k": args.k,
        "case_digest_sha256": _case_digest(cases),
        "elapsed_seconds": elapsed,
        "cases_per_second": len(cases) / elapsed if elapsed else None,
        "oracle_standing": "DECLARED_SYNTHETIC",
        "result": result,
        "authority": "NONE",
        "standing": "OBSERVED",
    }

    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
