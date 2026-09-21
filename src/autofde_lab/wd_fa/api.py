from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .domain import Standing
from .synthetic import RULES, named_cases
from .triage import triage


class TriageRequest(BaseModel):
    case_name: str = Field(
        description="Synthetic case key for the bounded case-study court"
    )


class TriageResponse(BaseModel):
    case_id: str
    standing: Standing
    admitted_mode: str | None
    next_action: str
    authority: str = "SELECT_ONLY"


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
        case = named_cases()[request.case_name]
        result = triage(case, RULES)
        return TriageResponse(
            case_id=result.case_id,
            standing=result.standing,
            admitted_mode=result.admitted_mode,
            next_action=result.next_action,
        )

    @app.post("/a2a/tasks/analyze_failure", response_model=TriageResponse)
    def sa2a_analyze(request: TriageRequest) -> TriageResponse:
        return triage_case(request)

    return app


app = create_app()
