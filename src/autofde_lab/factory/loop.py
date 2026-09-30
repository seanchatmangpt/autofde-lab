"""The autonomous loop. No human gate is awaited and no language model is used.

UNKNOWN -> bounded investigation in the world -> independent receipt ->
compiled experience -> later sightings of the class resolve by rule, cost 0.
Every step is appended to a JSONL ledger at the moment it happens; nothing is
back-filled. Standing is computed by ``verify.verify_ledger`` from that file.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from autofde_lab.wd_fa.domain import Standing
from autofde_lab.wd_fa.receipts import issue_receipt
from autofde_lab.wd_fa.synthetic import RULES
from autofde_lab.wd_fa.triage import compile_experience, triage

from .verify import verify_ledger
from .world import PRODUCER_ID, class_key, generate_stream

LEDGER = "ledger.jsonl"
_FORBIDDEN_LLM_MODULES = ("dspy", "openai", "anthropic", "litellm", "langchain")


def run_factory(
    out_dir: Path,
    *,
    n_classes: int = 6,
    repeats: int = 4,
    seed: int = 7,
    budget: int = 6,
    sony: bool = True,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / LEDGER
    ledger_path.write_text("")
    cases, world = generate_stream(n_classes, repeats, seed)
    rules = list(RULES)
    experiences: dict[str, object] = {}

    with ledger_path.open("a", encoding="utf-8") as ledger:

        def emit(record: dict) -> None:
            record["seq"] = emit.n
            emit.n += 1
            ledger.write(json.dumps(record, sort_keys=True, default=str) + "\n")
            ledger.flush()

        emit.n = 0
        for case in cases:
            result = triage(case, rules)
            base = {
                "case_id": case.case_id,
                "class_key": list(class_key(case.facts)),
                "evidence_kinds": sorted(i.kind for i in case.evidence),
                "receipt": None,
                "experience_id": None,
                "derived_from_case": None,
                "admitted_mode": result.admitted_mode,
            }
            if result.standing is Standing.ALIVE:
                exp = experiences.get(result.admitted_mode)
                emit(
                    {
                        **base,
                        "standing": "ALIVE",
                        "route": "experience" if exp else "seed_rule",
                        "cost": result.exploratory_steps,
                        "experience_id": exp.experience_id if exp else None,
                        "derived_from_case": exp.source_case_id if exp else None,
                    }
                )
                continue
            if result.standing is not Standing.UNKNOWN:
                emit(
                    {
                        **base,
                        "standing": result.standing.value,
                        "route": "unresolved",
                        "cost": result.exploratory_steps,
                    }
                )
                continue
            obs = world.investigate(case, budget)
            if obs is None:
                emit(
                    {
                        **base,
                        "standing": "UNKNOWN",
                        "route": "unresolved",
                        "cost": budget,
                    }
                )
                continue
            receipt = issue_receipt(
                case,
                result,
                producer_id=PRODUCER_ID,
                verifier_id=obs.observer_id,
                observed_disposition=obs.mode_id,
            )
            exp = compile_experience(
                case,
                result,
                receipt,
                mode_id=obs.mode_id,
                next_action=f"repeat_verified_procedure_{obs.mode_id}",
            )
            rules.append(exp.mode)
            experiences[obs.mode_id] = exp
            emit(
                {
                    **base,
                    "standing": "ALIVE",
                    "route": "investigation",
                    "admitted_mode": obs.mode_id,
                    "cost": obs.probes,
                    "receipt": asdict(receipt),
                    "experience_id": exp.experience_id,
                }
            )

    report: dict = {"ledger": str(ledger_path), "cases": len(cases)}
    report["verdict"] = asdict(verify_ledger(ledger_path))
    if sony:
        from autofde_lab.sony.crown import run_sony_crown

        ev = run_sony_crown(out_dir / "sony-workspace")
        report["sony_crown_runtime_projection"] = {
            "standing": ev.standing,
            "claim_ceiling": ev.claim_ceiling,
        }
    report["llm_modules_loaded"] = sorted(
        m for m in sys.modules if m.split(".")[0] in _FORBIDDEN_LLM_MODULES
    )
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--classes", type=int, default=6)
    p.add_argument("--repeats", type=int, default=4)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--budget", type=int, default=6)
    p.add_argument("--no-sony", action="store_true")
    a = p.parse_args(argv)
    r = run_factory(
        a.out,
        n_classes=a.classes,
        repeats=a.repeats,
        seed=a.seed,
        budget=a.budget,
        sony=not a.no_sony,
    )
    print(json.dumps(r, indent=2, sort_keys=True))
    ok = r["verdict"]["technical_standing"] == "ALIVE" and not r["llm_modules_loaded"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
