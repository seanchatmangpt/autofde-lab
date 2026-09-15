"""Structured-output boundary for semantic candidates."""

from __future__ import annotations

import json

from pydantic import ValidationError

from .contracts import CandidateGraphDelta


def candidate_json_schema() -> dict:
    """JSON Schema suitable for vLLM/OpenAI-compatible constrained decoding."""
    return CandidateGraphDelta.model_json_schema()


def parse_candidate_json(raw: str) -> CandidateGraphDelta:
    """Fail closed unless raw output is exactly a CandidateGraphDelta."""
    try:
        payload = json.loads(raw)
        return CandidateGraphDelta.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("model output is not an admissible candidate schema") from exc


def vllm_structured_output_request() -> dict:
    """Provider-neutral schema fragment for JSON-schema capable serving layers."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "candidate_graph_delta",
            "schema": candidate_json_schema(),
            "strict": True,
        },
    }
