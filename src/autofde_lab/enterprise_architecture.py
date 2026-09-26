"""Independent ABB -> SBB qualification court for RFC v26.9.26.

Qualification is evidence. It is not selection and never confers BRCE authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
import hashlib
import json
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


def qualify(
    contract: ArchitectureContract, candidate: CandidateSBB
) -> QualificationReceipt:
    """Qualify one exact candidate without selecting it."""

    refusals: list[str] = []

    if candidate.abb_digest != contract.abb_digest:
        refusals.append("ABB_MISMATCH")
    if candidate.contract_digest != contract.contract_digest:
        refusals.append("STALE_CONTRACT")
    if candidate.mutable:
        refusals.append("MUTABLE_SUBJECT")
    if not candidate.exact_subject_digest:
        refusals.append("MISSING_EXACT_SUBJECT")
    if not candidate.evidence:
        refusals.append("MISSING_EVIDENCE")

    candidate_authority = _AUTHORITY.get(candidate.authority)
    ceiling = _AUTHORITY.get(contract.authority_ceiling)
    if candidate_authority is None or ceiling is None:
        refusals.append("UNKNOWN_AUTHORITY")
    elif candidate_authority > ceiling:
        refusals.append("AUTHORITY_WIDENING")

    results: list[DimensionResult] = []
    for dimension in DIMENSIONS:
        observed = candidate.dimensions.get(dimension)
        if observed is True:
            results.append(DimensionResult(dimension, "PASS"))
        elif observed is False:
            results.append(DimensionResult(dimension, "FAIL", f"{dimension.upper()}_INCOMPATIBLE"))
            refusals.append(f"{dimension.upper()}_INCOMPATIBLE")
        else:
            results.append(DimensionResult(dimension, "UNKNOWN", f"{dimension.upper()}_UNKNOWN"))

    if refusals:
        standing = Standing.REFUSED
    elif any(result.verdict == "UNKNOWN" for result in results):
        standing = Standing.UNKNOWN
    else:
        standing = Standing.QUALIFIED

    provisional = QualificationReceipt(
        schema="autofde.architecture-qualification.v1",
        abb_digest=contract.abb_digest,
        contract_digest=contract.contract_digest,
        candidate_id=candidate.candidate_id,
        exact_subject_digest=candidate.exact_subject_digest,
        standing=standing,
        dimensions=tuple(results),
        refusal_codes=tuple(sorted(set(refusals))),
        confers_authority=False,
        receipt_digest="",
    )
    return replace(provisional, receipt_digest=digest(provisional))


def frontier(
    contract: ArchitectureContract, candidates: tuple[CandidateSBB, ...]
) -> tuple[QualificationReceipt, ...]:
    """Evaluate the complete DfCM candidate frontier without collapsing selection."""

    return tuple(
        qualify(contract, candidate)
        for candidate in sorted(candidates, key=lambda c: c.candidate_id)
    )


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
