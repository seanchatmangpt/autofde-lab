"""Typed vocabulary and content-addressed identity for the Inverse Ecosystem Compiler.

Everything IEC emits is one of a small number of typed records. The types exist so
that the distinctions the PRD/ARD (`docs/jira/v26.9.23/`) requires cannot be erased
by accident:

* `FactStanding` (PR-003) keeps observation, deterministic derivation, LLM/heuristic
  inference, admission, contradiction, and UNKNOWN apart. Nothing constructs
  `ADMITTED` except `admit()`, and `admit()` requires a court verdict of `PASS` whose
  verifier set is named.
* `ArtifactOrigin` (PR-009) is *where a file came from*. It is orthogonal to a file's
  *role* (test, schema, template...), which is what ggen-create's classifier answers.
  The default origin is `UNKNOWN`: a file with no generator marker is not thereby
  handwritten (`.claude/rules/absence-is-not-evidence.md`).
* `Verdict` (A8) is what a court may say. There is no boolean "equivalent".

Identity is content-addressed (ARD section 23): an observation's id is a hash over
its subject, extractor, extractor version, input identity, predicate, and value, so
an unchanged input re-observed by an unchanged extractor yields the same id and
never needs to be re-purchased.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

__all__ = [
    "AdmittedFact",
    "ArtifactOrigin",
    "EvidenceStrength",
    "FactStanding",
    "IECRefusal",
    "Observation",
    "Verdict",
    "admit",
    "canonical_json",
    "content_id",
]


class FactStanding(str, Enum):
    """PR-003: the standing of one semantic fact."""

    OBSERVED = "OBSERVED"
    DERIVED_DETERMINISTIC = "DERIVED_DETERMINISTIC"
    INFERRED_CANDIDATE = "INFERRED_CANDIDATE"
    ADMITTED = "ADMITTED"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


class ArtifactOrigin(str, Enum):
    """PR-009: where an artifact came from (not what role it plays)."""

    CANONICAL_SOURCE = "CANONICAL_SOURCE"
    GENERATED_PROJECTION = "GENERATED_PROJECTION"
    DERIVED_CACHE = "DERIVED_CACHE"
    HANDWRITTEN_IRREDUCIBLE = "HANDWRITTEN_IRREDUCIBLE"
    HISTORICAL_RESIDUE = "HISTORICAL_RESIDUE"
    EXTERNAL_VENDORED = "EXTERNAL_VENDORED"
    UNKNOWN = "UNKNOWN"


class EvidenceStrength(str, Enum):
    """How an origin classification was reached.

    `EXPLICIT_DECLARATION` means a producer or tool committed to the relation in
    durable evidence (a `.gitmodules` entry, a generator's declared output path, a
    begin/end marker naming the generator). `CONVENTION` means a naming convention
    happens to hold -- a correlation, not a statement anyone committed to
    (`.claude/rules/no-dual-bookkeeping.md`, "Identity is explicit or it does not
    exist"). `NONE` is the absence of either.
    """

    EXPLICIT_DECLARATION = "EXPLICIT_DECLARATION"
    CONVENTION = "CONVENTION"
    NONE = "NONE"


class Verdict(str, Enum):
    """A8: the only four things an equivalence court may emit."""

    PASS = "PASS"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    BLOCKED = "BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"


class IECRefusal(Exception):
    """A typed refusal from the ARD section 37 failure taxonomy.

    The code is the claim; the detail names the exact subject. Neither may be empty.
    """

    def __init__(self, code: str, detail: str) -> None:
        if not code or not detail:
            raise ValueError("IECRefusal requires both a typed code and a detail")
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def canonical_json(value: Any) -> str:
    """The one canonical JSON serialization every IEC digest is computed over."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_id(*parts: Any) -> str:
    """`sha256:<hex>` over the canonical JSON of `parts`."""
    digest = hashlib.sha256(canonical_json(list(parts)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class Observation:
    """One provenance-bearing fact (ARD A3).

    `subject` names exactly what the fact is about (e.g.
    `git:seanchatmangpt/ggen_igniter@<commit>:<path>`); `input_identity` is the
    immutable identity of what the extractor read (a git blob id, a commit id). The
    `derived_from` ids make lineage explicit rather than reconstructable.
    """

    subject: str
    extractor: str
    extractor_version: str
    input_identity: str
    predicate: str
    value: Any
    standing: FactStanding
    derived_from: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.standing is FactStanding.ADMITTED:
            raise IECRefusal(
                "REFUSED_SELF_ADMISSION",
                f"{self.predicate} on {self.subject}: ADMITTED is only reachable through admit()",
            )

    @property
    def id(self) -> str:
        return content_id(
            self.subject,
            self.extractor,
            self.extractor_version,
            self.input_identity,
            self.predicate,
            self.value,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "extractor": self.extractor,
            "extractor_version": self.extractor_version,
            "input_identity": self.input_identity,
            "predicate": self.predicate,
            "value": self.value,
            "standing": self.standing.value,
            "derived_from": list(self.derived_from),
        }


@dataclass(frozen=True)
class AdmittedFact:
    """An observation promoted by a named court. Only `admit()` builds one."""

    observation: Observation
    court_receipt_id: str
    verifier_set_id: str

    def to_json(self) -> dict[str, Any]:
        record = self.observation.to_json()
        record["standing"] = FactStanding.ADMITTED.value
        record["admitted_by"] = {
            "court_receipt_id": self.court_receipt_id,
            "verifier_set_id": self.verifier_set_id,
        }
        return record


def admit(observation: Observation, court_receipt: Mapping[str, Any]) -> AdmittedFact:
    """Promote `observation` to ADMITTED on the strength of one court receipt.

    Refuses unless the receipt's verdict is PASS, names its verifier set, and is
    about the same subject. Agreement between agents is not a court receipt.
    """
    if court_receipt.get("verdict") != Verdict.PASS.value:
        raise IECRefusal(
            "REFUSED_ADMISSION_WITHOUT_PASS",
            f"{observation.subject}: court verdict {court_receipt.get('verdict')!r}",
        )
    verifier_set_id = court_receipt.get("verifier_set_id")
    receipt_id = court_receipt.get("receipt_id")
    if not verifier_set_id or not receipt_id:
        raise IECRefusal(
            "REFUSED_UNBOUNDED_EQUIVALENCE",
            f"{observation.subject}: court receipt names no verifier set",
        )
    if court_receipt.get("subject") != observation.subject:
        raise IECRefusal(
            "REFUSED_AMBIGUOUS_AUTHORITY",
            f"court receipt is about {court_receipt.get('subject')!r}, "
            f"not {observation.subject!r}",
        )
    if observation.standing in (FactStanding.CONTRADICTED, FactStanding.UNKNOWN):
        raise IECRefusal(
            "REFUSED_ADMISSION_OF_UNKNOWN",
            f"{observation.subject}: {observation.standing.value} cannot be admitted",
        )
    return AdmittedFact(observation, receipt_id, verifier_set_id)
