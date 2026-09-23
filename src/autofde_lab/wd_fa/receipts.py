from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .domain import CandidateTriage, FailureCase


@dataclass(frozen=True)
class VerificationReceipt:
    subject_id: str
    evidence_digests: tuple[str, ...]
    producer_id: str
    verifier_id: str
    observed_disposition: str
    candidate_digest: str
    receipt_digest: str
    authority_scope: str = "REPO_LOCAL_FIXTURE"


def _canonical(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def candidate_digest(triage: CandidateTriage) -> str:
    return hashlib.sha256(_canonical(asdict(triage))).hexdigest()


def issue_receipt(
    case: FailureCase,
    triage: CandidateTriage,
    *,
    producer_id: str,
    verifier_id: str,
    observed_disposition: str,
) -> VerificationReceipt:
    if producer_id == verifier_id:
        raise ValueError("REFUSED:SELF_CERTIFICATION")
    core = {
        "subject_id": case.case_id,
        "evidence_digests": sorted(item.digest for item in case.evidence),
        "producer_id": producer_id,
        "verifier_id": verifier_id,
        "observed_disposition": observed_disposition,
        "candidate_digest": candidate_digest(triage),
        "authority_scope": "REPO_LOCAL_FIXTURE",
    }
    digest = hashlib.sha256(_canonical(core)).hexdigest()
    return VerificationReceipt(
        subject_id=core["subject_id"],
        evidence_digests=tuple(core["evidence_digests"]),
        producer_id=producer_id,
        verifier_id=verifier_id,
        observed_disposition=observed_disposition,
        candidate_digest=core["candidate_digest"],
        receipt_digest=digest,
        authority_scope=core["authority_scope"],
    )


def verify_receipt(receipt: VerificationReceipt) -> bool:
    core = {
        "subject_id": receipt.subject_id,
        "evidence_digests": sorted(receipt.evidence_digests),
        "producer_id": receipt.producer_id,
        "verifier_id": receipt.verifier_id,
        "observed_disposition": receipt.observed_disposition,
        "candidate_digest": receipt.candidate_digest,
        "authority_scope": receipt.authority_scope,
    }
    return (
        receipt.producer_id != receipt.verifier_id
        and receipt.authority_scope == "REPO_LOCAL_FIXTURE"
        and hashlib.sha256(_canonical(core)).hexdigest() == receipt.receipt_digest
    )
