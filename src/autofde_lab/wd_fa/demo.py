from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

from .automl import train_tpot
from .domain import Standing, make_work_order
from .process import process_evidence, roundtrip_ocel2
from .receipts import issue_receipt, verify_receipt
from .synthetic import RULES, named_cases, training_frame
from .triage import compile_experience, triage


def run_demo() -> dict[str, object]:
    cases = named_cases()
    train_x, train_y = training_frame()
    model = train_tpot(train_x, train_y)

    results = {}
    for name in ("known_a", "known_b_misleading", "incomplete_a", "novel_x"):
        case = cases[name]
        results[name] = triage(case, RULES, candidate_model=model)

    assert results["known_a"].standing is Standing.ALIVE
    assert results["known_b_misleading"].standing is Standing.ALIVE
    assert results["known_b_misleading"].admitted_mode == "MODE-B-SUPPLIER"
    assert results["incomplete_a"].standing is Standing.PARTIAL_ALIVE
    assert results["novel_x"].standing is Standing.UNKNOWN

    novel = cases["novel_x"]
    receipt = issue_receipt(
        novel, results["novel_x"],
        producer_id="autofde-wd-fa",
        verifier_id="wd-fa-independent-observer",
        observed_disposition="MODE-X-NOVEL",
    )
    assert verify_receipt(receipt)
    experience = compile_experience(
        novel,
        mode_id="MODE-X-NOVEL",
        verifier_id=receipt.verifier_id,
        next_action="repeat_verified_novel_x_procedure",
    )
    replay = triage(
        cases["novel_x_replay"],
        (*RULES, experience.mode),
        candidate_model=model,
    )
    assert replay.standing is Standing.ALIVE
    assert replay.admitted_mode == "MODE-X-NOVEL"
    assert replay.exploratory_steps < results["novel_x"].exploratory_steps

    process = process_evidence(cases["known_a"])
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "wd-fa.jsonocel"
        roundtripped = roundtrip_ocel2(cases["known_a"], path)
        roundtrip = {
            "events": len(roundtripped.events),
            "objects": len(roundtripped.objects),
            "relations": len(roundtripped.relations),
            "is_ocel20": bool(roundtripped.is_ocel20()),
        }

    work_order = make_work_order(results["novel_x"], novel)
    return {
        "standing": "ALIVE",
        "authority": "SELECT_CONSTRUCT_ONLY",
        "cases": {name: asdict(result) for name, result in results.items()},
        "machine_experience": asdict(experience),
        "replay": asdict(replay),
        "receipt": asdict(receipt),
        "receipt_valid": verify_receipt(receipt),
        "process": {k: v for k, v in process.items() if k != "powl"},
        "ocel_roundtrip": roundtrip,
        "work_order": asdict(work_order),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = run_demo()
    print(json.dumps(payload, None if args.json else 2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
