"""IEC-007: the equivalence court (PR-008, PR-015, ARD A8 and section 19).

A court takes an original subject, a generated subject, and a named verifier set,
and returns one verdict per verifier plus a receipt. It never returns a bare
"equivalent": the only positive claim it can issue is

    IEC_TRANSLATION_VALIDATED_FOR_<subject>_UNDER_<verifier-set-id>

and only when every verifier in the set returned `PASS`. A verifier that could not
run (`BLOCKED`) or has no way to judge this subject (`UNSUPPORTED`) is recorded as
such and lowers the claim to `NOT_VALIDATED`; it is never dropped from the set to
make the rest look complete. Counterexamples are part of the receipt, permanently.

Verifiers are plain functions of `(original, generated, context) -> VerifierResult`.
Their identity -- name, version, dimension -- is what the verifier-set id hashes,
so changing a verifier's logic without bumping its version is a detectable lie
only if the version is bumped; keep the version honest.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .model import IECRefusal, Verdict, content_id

__all__ = [
    "BLOB_IDENTITY",
    "BYTE_IDENTITY",
    "CourtReceipt",
    "Verifier",
    "VerifierResult",
    "VerifierSet",
    "git_blob_id",
    "run_court",
]


@dataclass(frozen=True)
class VerifierResult:
    verdict: Verdict
    detail: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("a verifier result must say what it observed")

    def to_json(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "detail": self.detail,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class Verifier:
    name: str
    version: str
    dimension: str
    check: Callable[[bytes, bytes, Mapping[str, Any]], VerifierResult] = field(
        compare=False
    )

    def identity(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version, "dimension": self.dimension}


@dataclass(frozen=True)
class VerifierSet:
    name: str
    verifiers: tuple[Verifier, ...]
    claim_prefix: str = "IEC_TRANSLATION_VALIDATED"

    def __post_init__(self) -> None:
        names = [verifier.name for verifier in self.verifiers]
        if not names:
            raise IECRefusal(
                "REFUSED_UNBOUNDED_EQUIVALENCE", "an empty verifier set proves nothing"
            )
        if len(set(names)) != len(names):
            raise IECRefusal(
                "REFUSED_UNBOUNDED_EQUIVALENCE", f"duplicate verifier in {names}"
            )

    @property
    def id(self) -> str:
        return content_id(
            self.name,
            self.claim_prefix,
            [verifier.identity() for verifier in self.verifiers],
        )

    @property
    def short_id(self) -> str:
        return self.id.split(":", 1)[1][:16]

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "claim_prefix": self.claim_prefix,
            "verifiers": [verifier.identity() for verifier in self.verifiers],
        }


@dataclass(frozen=True)
class CourtReceipt:
    subject: str
    original_identity: str
    generated_identity: str
    verifier_set: VerifierSet
    results: tuple[tuple[str, VerifierResult], ...]

    @property
    def verdict(self) -> Verdict:
        verdicts = [result.verdict for _, result in self.results]
        if any(verdict is Verdict.COUNTEREXAMPLE for verdict in verdicts):
            return Verdict.COUNTEREXAMPLE
        if any(verdict is Verdict.BLOCKED for verdict in verdicts):
            return Verdict.BLOCKED
        if any(verdict is Verdict.UNSUPPORTED for verdict in verdicts):
            return Verdict.UNSUPPORTED
        return Verdict.PASS

    @property
    def claim(self) -> str:
        if self.verdict is not Verdict.PASS:
            return "NOT_VALIDATED"
        prefix = self.verifier_set.claim_prefix
        return f"{prefix}_FOR_{self.subject}_UNDER_{self.verifier_set.short_id}"

    @property
    def dimensions(self) -> dict[str, str]:
        by_name = {
            verifier.name: verifier.dimension
            for verifier in self.verifier_set.verifiers
        }
        return {by_name[name]: result.verdict.value for name, result in self.results}

    def counterexamples(self) -> list[dict[str, Any]]:
        return [
            {
                "subject": self.subject,
                "verifier": name,
                "verifier_set_id": self.verifier_set.id,
                "original_identity": self.original_identity,
                "generated_identity": self.generated_identity,
                **result.to_json(),
            }
            for name, result in self.results
            if result.verdict is Verdict.COUNTEREXAMPLE
        ]

    def _body(self) -> dict[str, Any]:
        return {
            "schema": "autofde-lab.iec.court-receipt/1",
            "subject": self.subject,
            "original_identity": self.original_identity,
            "generated_identity": self.generated_identity,
            "verifier_set": self.verifier_set.to_json(),
            "verifier_set_id": self.verifier_set.id,
            "results": {name: result.to_json() for name, result in self.results},
            "dimensions": self.dimensions,
            "verdict": self.verdict.value,
            "claim": self.claim,
        }

    @property
    def receipt_id(self) -> str:
        return content_id(self._body())

    def to_json(self) -> dict[str, Any]:
        return {**self._body(), "receipt_id": self.receipt_id}


def run_court(
    subject: str,
    original: bytes,
    generated: bytes,
    verifier_set: VerifierSet,
    *,
    original_identity: str,
    generated_identity: str,
    context: Mapping[str, Any] | None = None,
    blocked: Mapping[str, str] | None = None,
) -> CourtReceipt:
    """Run every verifier; `blocked` names verifiers that may not run, with why.

    A verifier that raises is a counterexample against the translation (the court
    could not establish the property), not an infrastructure flake to retry.
    """
    context = dict(context or {})
    blocked = dict(blocked or {})
    unknown = set(blocked) - {verifier.name for verifier in verifier_set.verifiers}
    if unknown:
        raise IECRefusal(
            "REFUSED_UNBOUNDED_EQUIVALENCE",
            f"blocked names {sorted(unknown)} not in set",
        )
    results: list[tuple[str, VerifierResult]] = []
    for verifier in verifier_set.verifiers:
        if verifier.name in blocked:
            results.append(
                (verifier.name, VerifierResult(Verdict.BLOCKED, blocked[verifier.name]))
            )
            continue
        try:
            result = verifier.check(original, generated, context)
        except IECRefusal as refusal:
            result = VerifierResult(
                Verdict.COUNTEREXAMPLE,
                f"{refusal.code}: {refusal.detail}",
                {"raised": True},
            )
        results.append((verifier.name, result))
    return CourtReceipt(
        subject, original_identity, generated_identity, verifier_set, tuple(results)
    )


def git_blob_id(content: bytes) -> str:
    """The git object id of `content` as a blob (what `git hash-object` prints)."""
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def byte_identity(
    original: bytes, generated: bytes, context: Mapping[str, Any]
) -> VerifierResult:
    if original == generated:
        return VerifierResult(Verdict.PASS, f"{len(original)} bytes identical")
    limit = min(len(original), len(generated))
    first = next((i for i in range(limit) if original[i] != generated[i]), limit)
    return VerifierResult(
        Verdict.COUNTEREXAMPLE,
        f"first differing byte at offset {first}",
        {
            "offset": first,
            "original_len": len(original),
            "generated_len": len(generated),
            "original_excerpt": original[max(0, first - 40) : first + 40].decode(
                "utf-8", "replace"
            ),
            "generated_excerpt": generated[max(0, first - 40) : first + 40].decode(
                "utf-8", "replace"
            ),
        },
    )


def blob_identity(
    original: bytes, generated: bytes, context: Mapping[str, Any]
) -> VerifierResult:
    """The generated bytes hash to the exact blob id the frozen tree records."""
    expected = context.get("expected_blob_id")
    if not expected:
        return VerifierResult(
            Verdict.UNSUPPORTED, "no frozen blob id supplied for this subject"
        )
    actual = git_blob_id(generated)
    if actual == expected:
        return VerifierResult(
            Verdict.PASS, f"generated blob id {actual} equals frozen tree entry"
        )
    return VerifierResult(
        Verdict.COUNTEREXAMPLE,
        f"generated blob id {actual} != frozen tree entry {expected}",
        {"expected": expected, "actual": actual},
    )


BYTE_IDENTITY = Verifier("byte-identity", "1", "syntax", byte_identity)
BLOB_IDENTITY = Verifier(
    "git-blob-identity", "1", "exact-subject-identity", blob_identity
)
