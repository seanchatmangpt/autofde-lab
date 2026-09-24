"""IEC-C3: retire one repeated reasoning class, with a held-out court.

The class is `retirement.GENERATED_OUTPUT_AUDIT`. The protocol, in the order it
was executed (the receipts record the digests that make the order checkable):

1. freeze the mechanized audit's outcome on the held-out subject
   (autofde-lab@ae255ad, `src/autofde_lab/**/*.py` rule targets) and record the
   mechanism's source digest -- *before* any LLM outcome for that subject exists;
2. obtain an independent LLM outcome for the same question on the same subject
   (a fresh agent, told not to compute the answer with a program);
3. compare the two, row by row, on the class's declared fields;
4. replay the mechanized audit from the frozen commit and require the same
   outcome id -- the mechanism that answers now is the one that answered then;
5. compute the ledger status from the court receipts.

A calibration comparison on ggen_igniter (the subject the mechanism was built
from) is run too, and can never retire anything.

    python -m autofde_lab.iec.crowns.c3 --autofde-lab . --c3-dir receipts/v26.9.23/iec/c3 \\
        [--ggen-igniter ~/ggen_igniter]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .audit import audit_generated_outputs, audit_source_digest
from .census import census
from .corpus import observe_checkout
from .model import IECRefusal, canonical_json, content_id
from .retirement import GENERATED_OUTPUT_AUDIT, ReasoningClass, c3_court, ledger_entry

__all__ = ["HELD_OUT_COMMIT", "HELD_OUT_INCLUDE", "REASONING_CLASSES", "run_c3"]

HELD_OUT_REPOSITORY = "seanchatmangpt/autofde-lab"
HELD_OUT_COMMIT = "ae255ad123dfdcef9b3de82395006834abb20a28"
HELD_OUT_INCLUDE = r"^src/autofde_lab/.*\.py$"
CALIBRATION_REPOSITORY = "seanchatmangpt/ggen_igniter"
CALIBRATION_COMMIT = "d84da1419a6945c6a8a64b8f6cdca9d0b2c9e0f3"

_SESSION = "claude-code session 2026-09-23 (IEC v26.9.23 first execution)"

REASONING_CLASSES = (
    ReasoningClass(
        identity=GENERATED_OUTPUT_AUDIT.identity,
        description=GENERATED_OUTPUT_AUDIT.description,
        observations=(
            {
                "session": _SESSION,
                "actor": "subagent: ggen_igniter archaeology",
                "subject": f"{CALIBRATION_REPOSITORY}@{CALIBRATION_COMMIT}",
                "cost": {"tokens": 204625, "tool_uses": 100, "duration_ms": 463464},
                "cost_note": "whole archaeology run; this class was one of seven questions",
            },
            {
                "session": _SESSION,
                "actor": "subagent: autofde-lab held-out hand audit",
                "subject": f"{HELD_OUT_REPOSITORY}@{HELD_OUT_COMMIT}",
                "cost": {"tokens": 114650, "tool_uses": 38, "duration_ms": 310616},
                "cost_note": "the whole run answered this class only",
            },
            {
                "session": _SESSION,
                "actor": "orchestrator: manual diff of templates/constitution_module.py.tera "
                "against src/autofde_lab/constitution/authority.py",
                "subject": f"{HELD_OUT_REPOSITORY}@{HELD_OUT_COMMIT}",
                "cost": {},
                "cost_note": "not separately metered",
            },
        ),
        deterministic_replacement=GENERATED_OUTPUT_AUDIT.deterministic_replacement,
        compared_fields=GENERATED_OUTPUT_AUDIT.compared_fields,
        last_llm_required_reason="",
        notes=(
            "retired scope: the (committed, class) answer under the audit's claim ceiling "
            "(block-depth-0 template literals); divergence inside for/if bodies is not "
            "observed by the mechanism and stays with RC-PRODUCER-POSTPROCESSING",
        ),
    ),
    ReasoningClass(
        identity="RC-PRODUCER-POSTPROCESSING",
        description="Why does a committed generated file differ from its raw render -- "
        "which producer stage (formatter, lint autofix, hand edit) and which commit?",
        observations=(
            {
                "session": _SESSION,
                "actor": "subagent: ggen_igniter archaeology",
                "subject": f"{CALIBRATION_REPOSITORY}@{CALIBRATION_COMMIT}",
                "finding": "expense_approval_reactor.ex = Code.format_string!(render)",
            },
            {
                "session": _SESSION,
                "actor": "subagent: autofde-lab held-out hand audit",
                "subject": f"{HELD_OUT_REPOSITORY}@{HELD_OUT_COMMIT}",
                "finding": "ruff F401 autofix + ruff-format in pre-commit sweep 814615f",
            },
            {
                "session": _SESSION,
                "actor": "orchestrator",
                "subject": f"{HELD_OUT_REPOSITORY}@{HELD_OUT_COMMIT}",
                "finding": "`from enum import Enum` removed where no enum is rendered",
            },
        ),
        deterministic_replacement="autofde_lab.iec.crowns.crown (producer-postprocessing hypothesis "
        "+ producer-source evidence search); cause-to-commit attribution not mechanized",
        compared_fields=(),
        last_llm_required_reason="attributing a divergence to a specific hook and commit "
        "required reading commit diffs; no deterministic court compares cause attributions yet",
    ),
    ReasoningClass(
        identity="RC-INDEX-DRIFT",
        description="Which files match an index's own naming pattern but are missing "
        "from the index's source data?",
        observations=(
            {
                "session": _SESSION,
                "actor": "subagent: ggen_igniter archaeology",
                "subject": f"{CALIBRATION_REPOSITORY}@{CALIBRATION_COMMIT}",
                "finding": "docs/architecture/adr/0009-runtime-shape-semantic-ir.md is not "
                "in adr-index-pack/ontology.ttl",
            },
        ),
        deterministic_replacement="autofde_lab.iec.crowns.crown._kernel_path_coverage",
        compared_fields=(),
        last_llm_required_reason="observed once; mechanized but not yet repeated",
    ),
    ReasoningClass(
        identity="RC-FEDERATION-SURFACE",
        description="What in-process API does a sibling reverse compiler expose, and "
        "which of its steps need external binaries?",
        observations=(
            {
                "session": _SESSION,
                "actor": "subagent: ggen-create federation mapping",
                "subject": "seanchatmangpt/ggen-create@eaa463af138d7aff88db813f0f65307bf5c9b5ba",
                "cost": {"tokens": 213326, "tool_uses": 47, "duration_ms": 199790},
            },
        ),
        deterministic_replacement="autofde_lab.iec.crowns.federation.GgenCreate",
        compared_fields=(),
        last_llm_required_reason="observed once; the adapter pins the surface it found",
    ),
)


def _read(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> str:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    Path(path).write_text(text, encoding="utf-8")
    return content_id(text)


def _audit(
    repository: str, commit: str, checkout: Path, include: str
) -> dict[str, Any]:
    subject = observe_checkout(
        Path(checkout),
        repository=repository,
        branch="master" if repository == HELD_OUT_REPOSITORY else "main",
        visibility="public",
        inclusion_reason="IEC-C3 generated-output audit",
        commit=commit,
    )
    return audit_generated_outputs(
        census(subject, Path(checkout)), Path(checkout), include=include
    )


def run_c3(
    autofde_lab: Path, c3_dir: Path, *, ggen_igniter: Path | None = None
) -> dict[str, Any]:
    c3_dir = Path(c3_dir)
    frozen = _read(c3_dir / "mechanized.autofde-lab.frozen.json")
    llm = _read(c3_dir / "llm-outcome.autofde-lab.json")
    if llm["subject"] != f"{HELD_OUT_REPOSITORY}@{HELD_OUT_COMMIT}":
        raise IECRefusal(
            "BLOCKED_CORPUS_IDENTITY", f"LLM outcome is about {llm['subject']}"
        )
    replayed = _audit(
        HELD_OUT_REPOSITORY, HELD_OUT_COMMIT, autofde_lab, HELD_OUT_INCLUDE
    )
    held_out = c3_court(
        GENERATED_OUTPUT_AUDIT,
        f"git:{HELD_OUT_REPOSITORY}@{HELD_OUT_COMMIT}",
        llm,
        frozen["audit"],
        replayed_outcome_id=replayed["id"],
        held_out=bool(frozen.get("frozen_before_claude_outcome")),
        frozen_mechanism_digest=frozen["audit_source_digest"],
    )
    courts = [held_out]
    digests = {
        "court.held-out.autofde-lab.json": _write(
            c3_dir / "court.held-out.autofde-lab.json", held_out
        )
    }

    calibration_path = c3_dir / "llm-outcome.ggen_igniter.calibration.json"
    if ggen_igniter is not None and calibration_path.exists():
        calibration_llm = _read(calibration_path)
        mechanized = _audit(
            CALIBRATION_REPOSITORY, CALIBRATION_COMMIT, ggen_igniter, r".*"
        )
        calibration = c3_court(
            GENERATED_OUTPUT_AUDIT,
            f"git:{CALIBRATION_REPOSITORY}@{CALIBRATION_COMMIT}",
            calibration_llm,
            mechanized,
            replayed_outcome_id=_audit(
                CALIBRATION_REPOSITORY, CALIBRATION_COMMIT, ggen_igniter, r".*"
            )["id"],
            held_out=False,
            frozen_mechanism_digest="",
        )
        courts.append(calibration)
        digests["court.calibration.ggen_igniter.json"] = _write(
            c3_dir / "court.calibration.ggen_igniter.json", calibration
        )
        digests["mechanized.ggen_igniter.json"] = _write(
            c3_dir / "mechanized.ggen_igniter.json", mechanized
        )

    ledger = []
    for reasoning_class in REASONING_CLASSES:
        applicable = (
            courts
            if reasoning_class.identity == GENERATED_OUTPUT_AUDIT.identity
            else []
        )
        ledger.append(ledger_entry(reasoning_class, applicable))
    text = "".join(canonical_json(row) + "\n" for row in ledger)
    (c3_dir / "retirement-ledger.jsonl").write_text(text, encoding="utf-8")
    digests["retirement-ledger.jsonl"] = content_id(text)
    receipt_body = {
        "schema": "autofde-lab.iec.c3-run-receipt/1",
        "reasoning_class": GENERATED_OUTPUT_AUDIT.identity,
        "held_out_subject": f"{HELD_OUT_REPOSITORY}@{HELD_OUT_COMMIT}",
        "held_out_include": HELD_OUT_INCLUDE,
        "frozen_outcome_id": frozen["audit"]["id"],
        "frozen_file_sha256": hashlib.sha256(
            (c3_dir / "mechanized.autofde-lab.frozen.json").read_bytes()
        ).hexdigest(),
        "replayed_outcome_id": replayed["id"],
        "frozen_mechanism_digest": frozen["audit_source_digest"],
        "current_mechanism_digest": audit_source_digest(),
        "held_out_verdict": held_out["verdict"],
        "held_out_claim": held_out["claim"],
        "calibration_verdict": courts[1]["verdict"] if len(courts) > 1 else "NOT_RUN",
        "ledger_status": {row["identity"]: row["retirement_status"] for row in ledger},
        "mechanized_llm_calls": 0,
        "ordering_evidence": "the frozen outcome file's sha256 was recorded in the session "
        "transcript before the held-out agent was launched; no external timestamp authority "
        "attests that order",
        "files": digests,
    }
    receipt = {**receipt_body, "run_id": content_id(receipt_body)}
    _write(c3_dir / "run-receipt.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--autofde-lab", required=True, type=Path)
    parser.add_argument("--c3-dir", required=True, type=Path)
    parser.add_argument("--ggen-igniter", type=Path)
    args = parser.parse_args(argv)
    receipt = run_c3(args.autofde_lab, args.c3_dir, ggen_igniter=args.ggen_igniter)
    print(
        json.dumps(
            {
                k: receipt[k]
                for k in (
                    "run_id",
                    "held_out_verdict",
                    "held_out_claim",
                    "calibration_verdict",
                    "ledger_status",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
