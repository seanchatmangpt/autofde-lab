"""Independent ABB -> SBB qualification court for RFC v26.9.26.

Qualification is evidence. It is not selection and never confers BRCE authority.

Fail-closed rules (each is a typed refusal code, guarded by
``tests/fortune5/test_architecture_qualification_adversarial.py``):

* digests must be ``sha256:<64 lowercase hex>`` (``MALFORMED_DIGEST``); a branch or tag
  name is never an exact subject;
* the contract ceiling may not exceed ``CONSTRUCT`` (``CONTRACT_CEILING_INVALID``) and a
  ``DO`` candidate is always ``AUTHORITY_WIDENING``, whatever the contract says;
* evidence entries must be distinct non-blank strings (``MALFORMED_EVIDENCE``,
  ``DUPLICATE_EVIDENCE``); only the literal ``False`` proves immutability;
* dimension values must be ``True``/``False``/``None`` over the declared dimensions
  (``MALFORMED_DIMENSION``, ``UNDECLARED_DIMENSION``);
* the receipt binds the full candidate input (``input_digest``) so tamper, stale
  subject and replay mismatch are detectable (``verify_receipt``, ``replay_refusals``);
* ``frontier`` is order-invariant, idempotent under duplicate delivery and refuses
  distinct candidates that share one ``candidate_id`` (``DUPLICATE_CANDIDATE_ID``).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from typing import Mapping

DIMENSIONS = (
    "semantic",
    "functional",
    "effect",
    "failure",
    "authority",
    "resource",
    "evidence",
    "lifecycle",
)

_AUTHORITY = {"NONE": 0, "OBSERVE": 1, "SELECT": 2, "CONSTRUCT": 3, "DO": 4}
_MAX_CEILING = _AUTHORITY["CONSTRUCT"]
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")

SCHEMA = "autofde.architecture-qualification.v1"


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    QUALIFIED = "QUALIFIED"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class ArchitectureContract:
    abb_digest: str
    contract_digest: str
    authority_ceiling: str = "CONSTRUCT"


@dataclass(frozen=True)
class CandidateSBB:
    candidate_id: str
    abb_digest: str
    contract_digest: str
    exact_subject_digest: str
    mutable: bool
    authority: str
    evidence: tuple[str, ...]
    dimensions: Mapping[str, bool | None]


@dataclass(frozen=True)
class DimensionResult:
    dimension: str
    verdict: str
    reason: str | None = None


@dataclass(frozen=True)
class QualificationReceipt:
    schema: str
    abb_digest: str
    contract_digest: str
    candidate_id: str
    exact_subject_digest: str
    input_digest: str
    standing: Standing
    dimensions: tuple[DimensionResult, ...]
    refusal_codes: tuple[str, ...]
    confers_authority: bool
    receipt_digest: str


def _jsonable(value):
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


def digest(value) -> str:
    payload = json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _well_formed(value) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _qualify(
    contract: ArchitectureContract,
    candidate: CandidateSBB,
    extra_refusals: tuple[str, ...] = (),
) -> QualificationReceipt:
    refusals: list[str] = list(extra_refusals)

    if (
        not isinstance(candidate.candidate_id, str)
        or not candidate.candidate_id.strip()
    ):
        refusals.append("MISSING_CANDIDATE_ID")

    for value in (
        contract.abb_digest,
        contract.contract_digest,
        candidate.abb_digest,
        candidate.contract_digest,
    ):
        if not _well_formed(value):
            refusals.append("MALFORMED_DIGEST")
    if not candidate.exact_subject_digest:
        refusals.append("MISSING_EXACT_SUBJECT")
    elif not _well_formed(candidate.exact_subject_digest):
        refusals.append("MALFORMED_DIGEST")

    if candidate.abb_digest != contract.abb_digest:
        refusals.append("ABB_MISMATCH")
    if candidate.contract_digest != contract.contract_digest:
        refusals.append("STALE_CONTRACT")
    if candidate.mutable is not False:
        refusals.append("MUTABLE_SUBJECT")

    evidence = tuple(candidate.evidence or ())
    if not evidence:
        refusals.append("MISSING_EVIDENCE")
    if any(not isinstance(item, str) or not item.strip() for item in evidence):
        refusals.append("MALFORMED_EVIDENCE")
    if len(set(evidence)) != len(evidence):
        refusals.append("DUPLICATE_EVIDENCE")

    candidate_authority = _AUTHORITY.get(candidate.authority)
    ceiling = _AUTHORITY.get(contract.authority_ceiling)
    if ceiling is None or ceiling > _MAX_CEILING:
        refusals.append("CONTRACT_CEILING_INVALID")
    if candidate_authority is None:
        refusals.append("UNKNOWN_AUTHORITY")
    elif candidate_authority > min(ceiling if ceiling is not None else 0, _MAX_CEILING):
        refusals.append("AUTHORITY_WIDENING")

    undeclared = set(candidate.dimensions) - set(DIMENSIONS)
    if undeclared:
        refusals.append("UNDECLARED_DIMENSION")

    results: list[DimensionResult] = []
    for dimension in DIMENSIONS:
        observed = candidate.dimensions.get(dimension)
        if observed is True:
            results.append(DimensionResult(dimension, "PASS"))
        elif observed is False:
            code = f"{dimension.upper()}_INCOMPATIBLE"
            results.append(DimensionResult(dimension, "FAIL", code))
            refusals.append(code)
        elif observed is None:
            results.append(
                DimensionResult(dimension, "UNKNOWN", f"{dimension.upper()}_UNKNOWN")
            )
        else:
            results.append(
                DimensionResult(dimension, "UNKNOWN", f"{dimension.upper()}_MALFORMED")
            )
            refusals.append("MALFORMED_DIMENSION")

    if refusals:
        standing = Standing.REFUSED
    elif any(result.verdict == "UNKNOWN" for result in results):
        standing = Standing.UNKNOWN
    else:
        standing = Standing.QUALIFIED

    provisional = QualificationReceipt(
        schema=SCHEMA,
        abb_digest=contract.abb_digest,
        contract_digest=contract.contract_digest,
        candidate_id=candidate.candidate_id,
        exact_subject_digest=candidate.exact_subject_digest,
        input_digest=digest({"contract": contract, "candidate": candidate}),
        standing=standing,
        dimensions=tuple(results),
        refusal_codes=tuple(sorted(set(refusals))),
        confers_authority=False,
        receipt_digest="",
    )
    return replace(provisional, receipt_digest=digest(provisional))


def qualify(
    contract: ArchitectureContract, candidate: CandidateSBB
) -> QualificationReceipt:
    """Qualify one exact candidate without selecting it."""

    return _qualify(contract, candidate)


def verify_receipt(receipt: QualificationReceipt) -> bool:
    """Recompute the receipt digest; False means the receipt was edited after issue."""

    if receipt.confers_authority is not False or receipt.schema != SCHEMA:
        return False
    return digest(replace(receipt, receipt_digest="")) == receipt.receipt_digest


def replay_refusals(
    contract: ArchitectureContract,
    candidate: CandidateSBB,
    receipt: QualificationReceipt,
) -> tuple[str, ...]:
    """Replay qualification against a stored receipt; () means byte-identical replay."""

    codes: list[str] = []
    if not verify_receipt(receipt):
        codes.append("RECEIPT_TAMPERED")
    if candidate.exact_subject_digest != receipt.exact_subject_digest:
        codes.append("STALE_SUBJECT")
    if _qualify(contract, candidate).receipt_digest != receipt.receipt_digest:
        codes.append("REPLAY_MISMATCH")
    return tuple(codes)


def frontier(
    contract: ArchitectureContract, candidates: tuple[CandidateSBB, ...]
) -> tuple[QualificationReceipt, ...]:
    """Evaluate the complete DfCM candidate frontier without collapsing selection.

    Identical duplicate deliveries collapse to one receipt; distinct candidates that
    share one ``candidate_id`` are each refused with ``DUPLICATE_CANDIDATE_ID``. The
    output order is a function of the candidate set only, never of arrival order.
    """

    distinct: dict[str, dict[str, CandidateSBB]] = {}
    for candidate in candidates:
        distinct.setdefault(str(candidate.candidate_id), {})[digest(candidate)] = (
            candidate
        )

    receipts: list[QualificationReceipt] = []
    for candidate_id in sorted(distinct):
        by_digest = distinct[candidate_id]
        extra = ("DUPLICATE_CANDIDATE_ID",) if len(by_digest) > 1 else ()
        for key in sorted(by_digest):
            receipts.append(_qualify(contract, by_digest[key], extra))
    return tuple(receipts)


def prior_art_disposition(
    *, reusable: bool, composable: bool, extendable: bool
) -> tuple[str, str]:
    """Return the lawful Reuse -> Compose -> Extend -> Invent disposition and receipt digest."""

    route = (
        "REUSE"
        if reusable
        else "COMPOSE"
        if composable
        else "EXTEND"
        if extendable
        else "INVENT"
    )
    return route, digest({"schema": "autofde.prior-art-route.v1", "route": route})
