from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .domain import CandidateTriage, FailureCase, Standing
from .receipts import candidate_digest
from .synthetic import RULES, named_cases
from .triage import triage


class TriageRequest(BaseModel):
    case_name: str = Field(
        description="Synthetic case key for the bounded case-study court"
    )


class HypothesisResponse(BaseModel):
    mode_id: str
    candidate_score: float
    score_basis: str
    structural_similarity: float
    deterministic_match: bool
    evidence_completeness: float
    prior_case_ids: list[str]
    evidence_ids: list[str]
    owning_team: str
    action_type: str
    next_action: str


class EvidenceReference(BaseModel):
    evidence_id: str
    kind: str
    modality: str
    source_ref: str
    digest: str


class TriageResponse(BaseModel):
    case_id: str
    standing: Standing
    admitted_mode: str | None
    ranked_hypotheses: list[HypothesisResponse]
    closest_prior_cases: list[str]
    supporting_evidence: list[EvidenceReference]
    next_action: str
    action_type: str
    owning_team: str
    evidence_completeness: float
    confidence_basis: str
    human_gate: str
    trace_id: str
    authority: str = "SELECT_ONLY"


def _response(case: FailureCase, result: CandidateTriage) -> TriageResponse:
    # UNSUPPORTED(generator-capability:collection-valued-projection):
    # marketplace SHACL projections manufacture the scalar envelope today; ranked
    # hypotheses and evidence collections remain explicit runtime adapter residue.
    by_id = {item.evidence_id: item for item in case.evidence}
    evidence = [
        by_id[evidence_id]
        for evidence_id in result.supporting_evidence_ids
        if evidence_id in by_id
    ]
    return TriageResponse(
        case_id=result.case_id,
        standing=result.standing,
        admitted_mode=result.admitted_mode,
        ranked_hypotheses=[
            HypothesisResponse(
                mode_id=item.mode_id,
                candidate_score=item.candidate_score,
                score_basis=item.score_basis,
                structural_similarity=item.structural_similarity,
                deterministic_match=item.deterministic_match,
                evidence_completeness=item.evidence_completeness,
                prior_case_ids=list(item.prior_case_ids),
                evidence_ids=list(item.evidence_ids),
                owning_team=item.owning_team,
                action_type=item.action_type,
                next_action=item.next_action,
            )
            for item in result.ranked_hypotheses
        ],
        closest_prior_cases=list(result.closest_prior_case_ids),
        supporting_evidence=[
            EvidenceReference(
                evidence_id=item.evidence_id,
                kind=item.kind,
                modality=item.modality,
                source_ref=item.source_ref,
                digest=item.digest,
            )
            for item in evidence
        ],
        next_action=result.next_action,
        action_type=result.action_type,
        owning_team=result.owning_team,
        evidence_completeness=result.evidence_completeness,
        confidence_basis=result.confidence_basis,
        human_gate=result.human_gate,
        trace_id="sha256:" + candidate_digest(result),
    )


def create_app() -> FastAPI:
    app = FastAPI(title="WD Semantic Failure Analysis", version="26.9.21")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ALIVE", "authority": "NO_DO"}

    @app.post("/triage", response_model=TriageResponse)
    def triage_case(request: TriageRequest) -> TriageResponse:
        cases = named_cases()
        if request.case_name not in cases:
            raise HTTPException(status_code=404, detail="REFUSED:UNKNOWN_SYNTHETIC_SUBJECT")
        case = cases[request.case_name]
        return _response(case, triage(case, RULES))

    @app.post("/a2a/tasks/analyze_failure", response_model=TriageResponse)
    def sa2a_analyze(request: TriageRequest) -> TriageResponse:
        return triage_case(request)

    return app


app = create_app()
