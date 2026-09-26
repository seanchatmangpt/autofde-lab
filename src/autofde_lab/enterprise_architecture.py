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
  distinct candidates that share one ``candidate_id`` (``DUPLICATE_CANDIDATE_ID``) or
  one exact subject under different ids (``SUBJECT_ALIASED``, equivalence laundering);
  its receipts record the frontier-contributed codes so they replay byte-identically;
* category confusion is refused: only ``kind="SBB"`` is a solution building block.
  A vendor product presented as the ABB (``kind`` in ``VENDOR``/``PRODUCT``/``ABB``, or
  an exact subject equal to the ABB digest) is ``VENDOR_AS_ABB``; a pack, contract or EA
  model presented as the solution (``kind`` in ``PACK``/``CONTRACT``/``EA``, an exact
  subject equal to the contract digest, or a contract whose ABB and contract digests
  coincide) is ``PACK_AS_EA``; any other kind is ``UNKNOWN_KIND``;
* type confusion never raises: a bare string, unhashable or non-string evidence entry
  is ``MALFORMED_EVIDENCE``; a non-mapping ``dimensions`` is ``MALFORMED_DIMENSION``;
  a non-string authority is ``UNKNOWN_AUTHORITY``/``CONTRACT_CEILING_INVALID``;
  non-JSON values are digested by type name, so a receipt is always issued.

``verify_receipt`` is an integrity check over an unkeyed sha256: it detects edits that
were not followed by a digest recomputation. It is not an authenticity check; anyone
can recompute the digest of a forged receipt. Authenticity is ``replay_refusals``,
which re-derives the receipt from the exact inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
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

SBB_KIND = "SBB"
_VENDOR_KINDS = frozenset({"VENDOR", "PRODUCT", "ABB"})
_PACK_KINDS = frozenset({"PACK", "CONTRACT", "EA"})
FRONTIER_CODES = frozenset({"DUPLICATE_CANDIDATE_ID", "SUBJECT_ALIASED"})


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
    kind: str = SBB_KIND


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
    frontier_refusals: tuple[str, ...] = ()


def _jsonable(value):
    if isinstance(value, StrEnum):
        return value.value
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "__dataclass_fields__") and not isinstance(value, type):
        return {
            name: _jsonable(getattr(value, name)) for name in value.__dataclass_fields__
        }
    if isinstance(value, Mapping):
        items = [(f"{type(k).__name__}:{k}", _jsonable(v)) for k, v in value.items()]
        return {"__mapping__": sorted(items, key=lambda item: item[0])}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    # Non-JSON value (object(), set, bytes, ...): digest its type, never its address.
    kind = type(value)
    return {"__unjsonable__": f"{kind.__module__}.{kind.__qualname__}"}


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

    refusals.extend(_category_refusals(contract, candidate))

    raw_evidence = candidate.evidence
    if raw_evidence is None or (
        isinstance(raw_evidence, (tuple, list)) and not raw_evidence
    ):
        refusals.append("MISSING_EVIDENCE")
    elif not isinstance(raw_evidence, (tuple, list)):
        # A bare string would otherwise be split into characters.
        refusals.append("MALFORMED_EVIDENCE")
    elif any(not isinstance(item, str) or not item.strip() for item in raw_evidence):
        refusals.append("MALFORMED_EVIDENCE")
    elif len(set(raw_evidence)) != len(raw_evidence):
        refusals.append("DUPLICATE_EVIDENCE")

    candidate_authority = _authority_rank(candidate.authority)
    ceiling = _authority_rank(contract.authority_ceiling)
    if ceiling is None or ceiling > _MAX_CEILING:
        refusals.append("CONTRACT_CEILING_INVALID")
    if candidate_authority is None:
        refusals.append("UNKNOWN_AUTHORITY")
    elif candidate_authority > min(ceiling if ceiling is not None else 0, _MAX_CEILING):
        refusals.append("AUTHORITY_WIDENING")

    dimensions = candidate.dimensions
    if not isinstance(dimensions, Mapping):
        refusals.append("MALFORMED_DIMENSION")
        dimensions = {}
    elif any(not isinstance(key, str) or key not in DIMENSIONS for key in dimensions):
        refusals.append("UNDECLARED_DIMENSION")

    results: list[DimensionResult] = []
    for dimension in DIMENSIONS:
        observed = dimensions.get(dimension)
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
        frontier_refusals=tuple(sorted(set(extra_refusals))),
    )
    return replace(provisional, receipt_digest=digest(provisional))


def _authority_rank(value) -> int | None:
    return _AUTHORITY.get(value) if isinstance(value, str) else None


def _category_refusals(
    contract: ArchitectureContract, candidate: CandidateSBB
) -> list[str]:
    """Refuse category confusion: vendor-as-ABB and Pack-as-EA worlds."""

    codes: list[str] = []
    kind = candidate.kind
    if isinstance(kind, str) and kind in _VENDOR_KINDS:
        codes.append("VENDOR_AS_ABB")
    elif isinstance(kind, str) and kind in _PACK_KINDS:
        codes.append("PACK_AS_EA")
    elif kind != SBB_KIND or not isinstance(kind, str):
        codes.append("UNKNOWN_KIND")

    subject = candidate.exact_subject_digest
    if _well_formed(subject):
        if subject in (contract.abb_digest, candidate.abb_digest):
            codes.append("VENDOR_AS_ABB")
        if subject in (contract.contract_digest, candidate.contract_digest):
            codes.append("PACK_AS_EA")
    if _well_formed(contract.abb_digest) and (
        contract.abb_digest == contract.contract_digest
    ):
        codes.append("PACK_AS_EA")
    return codes


def qualify(
    contract: ArchitectureContract, candidate: CandidateSBB
) -> QualificationReceipt:
    """Qualify one exact candidate without selecting it."""

    return _qualify(contract, candidate)


def verify_receipt(receipt: QualificationReceipt) -> bool:
    """Integrity check: recompute the unkeyed receipt digest.

    False means the receipt is structurally invalid (wrong schema, confers authority,
    frontier codes outside the frontier vocabulary) or was edited without recomputing
    its digest. True is NOT authenticity: an adversary can recompute the digest of a
    forged receipt. Use ``replay_refusals`` to authenticate against exact inputs.
    """

    if receipt.confers_authority is not False or receipt.schema != SCHEMA:
        return False
    frontier_codes = receipt.frontier_refusals
    if not isinstance(frontier_codes, tuple) or not set(frontier_codes) <= (
        FRONTIER_CODES
    ):
        return False
    return digest(replace(receipt, receipt_digest="")) == receipt.receipt_digest


def replay_refusals(
    contract: ArchitectureContract,
    candidate: CandidateSBB,
    receipt: QualificationReceipt,
    frontier_set: tuple[CandidateSBB, ...] | None = None,
) -> tuple[str, ...]:
    """Replay qualification against a stored receipt; () means byte-identical replay.

    A receipt issued by ``frontier`` carries its frontier-contributed codes. With
    ``frontier_set`` those codes are re-derived from the full candidate set; without
    it they are taken from the (integrity-checked) receipt. Frontier codes can only add
    refusals, so honouring them never lets a candidate qualify.
    """

    codes: list[str] = []
    if not verify_receipt(receipt):
        codes.append("RECEIPT_TAMPERED")
    if candidate.exact_subject_digest != receipt.exact_subject_digest:
        codes.append("STALE_SUBJECT")
    if frontier_set is not None:
        extra = _frontier_extras(tuple(frontier_set)).get(
            (str(candidate.candidate_id), digest(candidate)), ()
        )
    elif (
        isinstance(receipt.frontier_refusals, tuple)
        and set(receipt.frontier_refusals) <= FRONTIER_CODES
    ):
        extra = receipt.frontier_refusals
    else:
        extra = ()
    if _qualify(contract, candidate, extra).receipt_digest != receipt.receipt_digest:
        codes.append("REPLAY_MISMATCH")
    return tuple(codes)


def _frontier_extras(
    candidates: tuple[CandidateSBB, ...],
) -> dict[tuple[str, str], tuple[str, ...]]:
    """Frontier-level refusals keyed by (candidate_id, candidate digest)."""

    distinct: dict[str, dict[str, CandidateSBB]] = {}
    for candidate in candidates:
        distinct.setdefault(str(candidate.candidate_id), {})[digest(candidate)] = (
            candidate
        )
    ids_by_subject: dict[str, set[str]] = {}
    for candidate_id, by_digest in distinct.items():
        for candidate in by_digest.values():
            subject = candidate.exact_subject_digest
            if _well_formed(subject):
                ids_by_subject.setdefault(subject, set()).add(candidate_id)

    extras: dict[tuple[str, str], tuple[str, ...]] = {}
    for candidate_id, by_digest in distinct.items():
        for key, candidate in by_digest.items():
            codes = []
            if len(by_digest) > 1:
                codes.append("DUPLICATE_CANDIDATE_ID")
            subject = candidate.exact_subject_digest
            if _well_formed(subject) and len(ids_by_subject[subject]) > 1:
                codes.append("SUBJECT_ALIASED")
            extras[(candidate_id, key)] = tuple(codes)
    return extras


def frontier(
    contract: ArchitectureContract, candidates: tuple[CandidateSBB, ...]
) -> tuple[QualificationReceipt, ...]:
    """Evaluate the complete DfCM candidate frontier without collapsing selection.

    Identical duplicate deliveries collapse to one receipt; distinct candidates that
    share one ``candidate_id`` are each refused with ``DUPLICATE_CANDIDATE_ID``. The
    output order is a function of the candidate set only, never of arrival order.
    """

    candidates = tuple(candidates)
    extras = _frontier_extras(candidates)
    by_key: dict[tuple[str, str], CandidateSBB] = {}
    for candidate in candidates:
        by_key[(str(candidate.candidate_id), digest(candidate))] = candidate
    return tuple(_qualify(contract, by_key[key], extras[key]) for key in sorted(by_key))


def prior_art_disposition(
    *, reusable: bool, composable: bool, extendable: bool
) -> tuple[str, str]:
    """Return the lawful Reuse -> Compose -> Extend -> Invent disposition and receipt digest.

    The receipt digest binds the full decision input, not only the route, so two
    different findings that land on the same route get different receipts. A non-bool
    finding is not evidence: the route is ``UNKNOWN`` (never ``INVENT`` by default).
    """

    findings = {
        "reusable": reusable,
        "composable": composable,
        "extendable": extendable,
    }
    if any(not isinstance(value, bool) for value in findings.values()):
        route = "UNKNOWN"
    else:
        route = (
            "REUSE"
            if reusable
            else "COMPOSE"
            if composable
            else "EXTEND"
            if extendable
            else "INVENT"
        )
    return route, digest(
        {"schema": "autofde.prior-art-route.v2", "findings": findings, "route": route}
    )
