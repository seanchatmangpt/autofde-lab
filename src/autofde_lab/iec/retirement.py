"""IEC-010: the intelligence-retirement ledger and the C3 court (PR-012, ARD section 27).

A `ReasoningClass` is a kind of question this project paid an LLM to answer. Its
lifecycle follows ARD O6:

    UNKNOWN -> explored with intelligence
    KNOWN -> encoded
    REPEATED -> mechanized          (MECHANIZATION_CANDIDATE once recurrence >= 2)
    MECHANIZED -> LLM retired from the normal path

`RETIRED_FROM_LLM` is never set by hand. `retire()` sets it only from a C3 court
receipt that compared an LLM outcome with the deterministic replacement's outcome
on a held-out subject -- one the replacement's author had not seen the LLM answer
for when the replacement was frozen -- *and* a replay that reproduced the
replacement's outcome id. A calibration comparison (on the subject the
replacement was built from) is recorded, but it can never retire anything: an
answer the mechanism was fitted to is not evidence the mechanism generalizes.

Comparison is by typed row: each row is keyed, and each keyed field must be equal.
The court's claim is therefore `Outcome_mechanized ==_V Outcome_LLM` for V = the
named row fields -- not "the mechanism is as smart as the model".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .court import Verifier, VerifierResult, VerifierSet, run_court
from .model import IECRefusal, Verdict, canonical_json, content_id

__all__ = [
    "GENERATED_OUTPUT_AUDIT",
    "RETIREMENT_STATES",
    "ReasoningClass",
    "c3_court",
    "compare_outcomes",
    "ledger_entry",
    "outcome_court",
]

RETIREMENT_STATES = (
    "UNKNOWN",
    "KNOWN",
    "REPEATED",
    "MECHANIZATION_CANDIDATE",
    "MECHANIZED",
    "RETIRED_FROM_LLM",
)


@dataclass(frozen=True)
class ReasoningClass:
    identity: str
    description: str
    observations: tuple[Mapping[str, Any], ...]
    deterministic_replacement: str
    compared_fields: tuple[str, ...]
    last_llm_required_reason: str = ""
    notes: tuple[str, ...] = field(default=())

    @property
    def recurrence_count(self) -> int:
        return len(self.observations)


GENERATED_OUTPUT_AUDIT = ReasoningClass(
    identity="RC-GENERATED-OUTPUT-AUDIT",
    description="For one commit: which committed files does a declared generator claim, "
    "and is each one what its template literally emits (exactly, modulo whitespace, "
    "modulo whitespace and call parentheses, or not at all)?",
    observations=(),
    deterministic_replacement="autofde_lab.iec.audit.audit_generated_outputs",
    compared_fields=("committed", "class"),
)


def compare_outcomes(
    llm_rows: Sequence[Mapping[str, Any]],
    mechanized_rows: Sequence[Mapping[str, Any]],
    *,
    key: str,
    fields: Sequence[str],
) -> dict[str, Any]:
    """Row-by-row equality on `fields`, keyed by `key`; nothing is coerced."""
    llm = {str(row[key]): row for row in llm_rows}
    mechanized = {str(row[key]): row for row in mechanized_rows}
    if len(llm) != len(llm_rows) or len(mechanized) != len(mechanized_rows):
        raise IECRefusal(
            "REFUSED_UNBOUNDED_EQUIVALENCE", f"duplicate {key} in an outcome"
        )
    rows = []
    for name in sorted(set(llm) | set(mechanized)):
        left, right = llm.get(name), mechanized.get(name)
        if left is None or right is None:
            rows.append(
                {
                    key: name,
                    "agree": False,
                    "only_in": "mechanized" if left is None else "llm",
                }
            )
            continue
        disagreements = {
            field_name: {
                "llm": left.get(field_name),
                "mechanized": right.get(field_name),
            }
            for field_name in fields
            if left.get(field_name) != right.get(field_name)
        }
        rows.append(
            {key: name, "agree": not disagreements, "disagreements": disagreements}
        )
    return {
        "key": key,
        "fields": list(fields),
        "rows": rows,
        "agreed": sum(1 for row in rows if row["agree"]),
        "total": len(rows),
    }


def _outcome_equivalence(
    original: bytes, generated: bytes, context: Mapping[str, Any]
) -> VerifierResult:
    comparison = compare_outcomes(
        json.loads(original)["rows"],
        json.loads(generated)["rows"],
        key=context["key"],
        fields=context["fields"],
    )
    if comparison["agreed"] == comparison["total"]:
        return VerifierResult(
            Verdict.PASS,
            f"{comparison['total']} of {comparison['total']} rows agree",
            comparison,
        )
    return VerifierResult(
        Verdict.COUNTEREXAMPLE,
        f"{comparison['total'] - comparison['agreed']} of {comparison['total']} rows disagree",
        comparison,
    )


def _replay(
    original: bytes, generated: bytes, context: Mapping[str, Any]
) -> VerifierResult:
    first, second = context["mechanized_outcome_id"], context["replayed_outcome_id"]
    if first == second:
        return VerifierResult(Verdict.PASS, f"replay reproduced outcome {first}")
    return VerifierResult(
        Verdict.COUNTEREXAMPLE, f"replay produced {second}, not {first}"
    )


def _heldout(
    original: bytes, generated: bytes, context: Mapping[str, Any]
) -> VerifierResult:
    if context.get("held_out") is True:
        return VerifierResult(
            Verdict.PASS,
            "the mechanism was frozen (digest recorded) before the LLM outcome existed",
            {"frozen_mechanism_digest": context.get("frozen_mechanism_digest")},
        )
    return VerifierResult(
        Verdict.UNSUPPORTED,
        "calibration subject: the mechanism was built after reading this LLM outcome",
    )


def outcome_court(reasoning_class: ReasoningClass) -> VerifierSet:
    return VerifierSet(
        f"iec-c3-outcome-equivalence/{reasoning_class.identity}",
        (
            Verifier("row-field-equality", "1", "outcome", _outcome_equivalence),
            Verifier("mechanized-replay", "1", "replay", _replay),
            Verifier("held-out-subject", "1", "generalization", _heldout),
        ),
        claim_prefix="IEC_OUTCOME_EQUIVALENT_TO_LLM",
    )


def c3_court(
    reasoning_class: ReasoningClass,
    subject: str,
    llm_outcome: Mapping[str, Any],
    mechanized_outcome: Mapping[str, Any],
    *,
    replayed_outcome_id: str,
    held_out: bool,
    frozen_mechanism_digest: str,
    key: str = "target",
) -> dict[str, Any]:
    original = canonical_json(llm_outcome).encode("utf-8")
    generated = canonical_json(mechanized_outcome).encode("utf-8")
    receipt = run_court(
        subject,
        original,
        generated,
        outcome_court(reasoning_class),
        original_identity=content_id(llm_outcome),
        generated_identity=mechanized_outcome.get("id", content_id(mechanized_outcome)),
        context={
            "key": key,
            "fields": reasoning_class.compared_fields,
            "mechanized_outcome_id": mechanized_outcome.get("id"),
            "replayed_outcome_id": replayed_outcome_id,
            "held_out": held_out,
            "frozen_mechanism_digest": frozen_mechanism_digest,
        },
    )
    return receipt.to_json()


def ledger_entry(
    reasoning_class: ReasoningClass, courts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """One `retirement-ledger.jsonl` row; the status is computed, never asserted."""
    held_out_pass = [
        court
        for court in courts
        if court["verdict"] == Verdict.PASS.value
        and court["results"]["held-out-subject"]["verdict"] == Verdict.PASS.value
    ]
    if held_out_pass:
        status = "RETIRED_FROM_LLM"
    elif reasoning_class.recurrence_count >= 2:
        status = "MECHANIZATION_CANDIDATE" if not courts else "MECHANIZED"
    elif reasoning_class.recurrence_count == 1:
        status = "KNOWN"
    else:
        status = "UNKNOWN"
    tokens = sum(
        int(o.get("cost", {}).get("tokens", 0)) for o in reasoning_class.observations
    )
    return {
        "identity": reasoning_class.identity,
        "description": reasoning_class.description,
        "observations": [dict(o) for o in reasoning_class.observations],
        "recurrence_count": reasoning_class.recurrence_count,
        "observed_llm_tokens": tokens,
        "current_executor": "deterministic" if status == "RETIRED_FROM_LLM" else "llm",
        "deterministic_replacement": reasoning_class.deterministic_replacement,
        "admission_status": "ADMITTED" if held_out_pass else "CANDIDATE",
        "court_receipts": [court["receipt_id"] for court in courts],
        "court_verdicts": {court["receipt_id"]: court["verdict"] for court in courts},
        "last_llm_required_reason": reasoning_class.last_llm_required_reason,
        "retirement_status": status,
        "notes": list(reasoning_class.notes),
    }
