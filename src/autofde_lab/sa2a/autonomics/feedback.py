"""GALL-009 runtime feedback admission.

Validated observations are evidence, not normative law and not authority.  This
module is the explicit bridge from GALL-008 observations into GALL-010 belief:
only an admitted rule may name which boolean facts a finding can update.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Mapping

from .belief import BeliefState, EpistemicValue

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_FORBIDDEN_FACTS = {
    "authority",
    "authorization",
    "authorizes_actuation",
    "standing",
    "execute",
    "do",
}


def _digest(value: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
        ).hexdigest()
    )


@dataclass(frozen=True, slots=True)
class FeedbackFinding:
    semantic_subject_digest: str
    source_receipt_digest: str
    finding_type: str
    evidence_class: str
    facts: Mapping[str, bool | None]

    def validate(self) -> None:
        if not _SHA256.fullmatch(self.semantic_subject_digest):
            raise ValueError("feedback semantic subject must be sha256:<64hex>")
        if not _SHA256.fullmatch(self.source_receipt_digest):
            raise ValueError("feedback source receipt must be sha256:<64hex>")
        if not self.finding_type or not self.evidence_class:
            raise ValueError("feedback finding type and evidence class are required")
        for key, value in self.facts.items():
            if not key or key.lower() in _FORBIDDEN_FACTS:
                raise ValueError(f"feedback cannot assert reserved fact {key!r}")
            if value not in (True, False, None):
                raise ValueError(
                    f"feedback fact {key!r} must be true, false, or unknown"
                )


@dataclass(frozen=True, slots=True)
class FeedbackRule:
    rule_id: str
    finding_type: str
    evidence_class: str
    allowed_facts: tuple[str, ...]

    def validate(self) -> None:
        if not self.rule_id or not self.finding_type or not self.evidence_class:
            raise ValueError("feedback rule identity/type/evidence class are required")
        if not self.allowed_facts:
            raise ValueError("feedback rule must admit at least one fact")
        if len(set(self.allowed_facts)) != len(self.allowed_facts):
            raise ValueError("feedback rule contains duplicate fact identities")
        if any(
            not fact or fact.lower() in _FORBIDDEN_FACTS for fact in self.allowed_facts
        ):
            raise ValueError(
                "feedback rule attempts to admit a reserved authority/standing fact"
            )

    @property
    def digest(self) -> str:
        self.validate()
        return _digest(
            {
                "rule_id": self.rule_id,
                "finding_type": self.finding_type,
                "evidence_class": self.evidence_class,
                "allowed_facts": sorted(self.allowed_facts),
            }
        )


@dataclass(frozen=True, slots=True)
class AdmittedFeedback:
    semantic_subject_digest: str
    source_receipt_digest: str
    admission_rule_id: str
    admission_rule_digest: str
    fact_updates: Mapping[str, EpistemicValue]
    admitted: bool = True
    normative: bool = False
    authorizes_actuation: bool = False

    @property
    def receipt_digest(self) -> str:
        return _digest(
            {
                "semantic_subject_digest": self.semantic_subject_digest,
                "source_receipt_digest": self.source_receipt_digest,
                "admission_rule_id": self.admission_rule_id,
                "admission_rule_digest": self.admission_rule_digest,
                "fact_updates": {
                    key: value.value for key, value in sorted(self.fact_updates.items())
                },
                "admitted": self.admitted,
                "normative": self.normative,
                "authorizes_actuation": self.authorizes_actuation,
            }
        )

    def apply(self, belief: BeliefState) -> BeliefState:
        if belief.provenance_digest != self.source_receipt_digest:
            raise ValueError(
                "feedback receipt does not match belief provenance boundary"
            )
        facts = dict(belief.facts)
        facts.update(self.fact_updates)
        return BeliefState(
            facts=facts,
            observation_projection=belief.observation_projection,
            provenance_digest=self.receipt_digest,
        )


class FeedbackAdmission:
    @staticmethod
    def admit(
        finding: FeedbackFinding,
        rule: FeedbackRule,
        *,
        expected_subject_digest: str,
    ) -> AdmittedFeedback:
        finding.validate()
        rule.validate()
        if finding.semantic_subject_digest != expected_subject_digest:
            raise ValueError(
                "feedback semantic subject does not match admitted subject"
            )
        if finding.finding_type != rule.finding_type:
            raise ValueError("feedback finding type is not admitted by this rule")
        if finding.evidence_class != rule.evidence_class:
            raise ValueError("feedback evidence class is not admitted by this rule")

        unknown = set(finding.facts) - set(rule.allowed_facts)
        if unknown:
            raise ValueError(f"feedback contains unadmitted facts: {sorted(unknown)}")

        updates = {
            key: (
                EpistemicValue.UNKNOWN
                if value is None
                else EpistemicValue.KNOWN_TRUE
                if value
                else EpistemicValue.KNOWN_FALSE
            )
            for key, value in finding.facts.items()
        }
        return AdmittedFeedback(
            semantic_subject_digest=finding.semantic_subject_digest,
            source_receipt_digest=finding.source_receipt_digest,
            admission_rule_id=rule.rule_id,
            admission_rule_digest=rule.digest,
            fact_updates=updates,
        )
