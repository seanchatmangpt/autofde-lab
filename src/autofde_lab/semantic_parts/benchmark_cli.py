"""Command-line runner for the semantic substitution benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from .substitution_benchmark import (
    SubstitutionCase,
    evaluate_at_cutoffs,
    evaluate_substitution_discovery,
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _load_cases(path: Path) -> tuple[SubstitutionCase, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("cases")
    if not isinstance(raw, list):
        raise ValueError("benchmark input must be a JSON list or an object with cases")
    return tuple(SubstitutionCase.from_mapping(item) for item in raw)


def _receipt(
    *,
    input_path: Path,
    cases: Sequence[SubstitutionCase],
    result: dict[str, object],
) -> dict[str, object]:
    input_bytes = input_path.read_bytes()
    result_digest = hashlib.sha256(_canonical_json(result)).hexdigest()
    return {
        "schema": "autofde.semantic-substitution-receipt.v1",
        "input": str(input_path),
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "case_count": len(cases),
        "result_sha256": result_digest,
        "result": result,
        "authority": "NONE",
        "standing": "OBSERVED",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--cutoffs",
        help="comma-separated retrieval budgets; when supplied, emits a sweep",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    try:
        cases = _load_cases(args.input)
        if args.cutoffs:
            cutoffs = tuple(int(value) for value in args.cutoffs.split(",") if value)
            result = evaluate_at_cutoffs(cases, cutoffs=cutoffs)
        else:
            result = evaluate_substitution_discovery(cases, k=args.k)
        receipt = _receipt(input_path=args.input, cases=cases, result=result)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        payload = {
            "schema": "autofde.semantic-substitution-receipt.v1",
            "standing": "REFUSED",
            "authority": "NONE",
            "code": "REFUSED_BENCHMARK_INPUT",
            "detail": str(error),
        }
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2

    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
