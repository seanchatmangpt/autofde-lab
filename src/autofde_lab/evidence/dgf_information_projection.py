"""DGF evidence-projection experiments over the information-obstruction theorem.

This module is an offline benchmark tool. It deliberately reads hidden DGF
canonical truth so researchers can simulate candidate observation interfaces
and ask a precise question before deploying an agent:

    Does this proposed evidence projection distinguish every case that requires
    an incompatible governance output?

It never exposes hidden truth to the evaluated agent and never calls a model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Sequence

from autofde_lab.evidence.dgf_substitution import discover_dgf_cases
from autofde_lab.evidence.information_obstruction import (
    DecisionCase,
    InformationObstructionReport,
    analyze_information_obstruction,
)


@dataclass(frozen=True, slots=True)
class ProjectionAudit:
    observation_paths: tuple[str, ...]
    report: InformationObstructionReport

    @property
    def sufficient(self) -> bool:
        return self.report.information_sufficient


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dotted_get(root: Any, path: str) -> Any:
    """Resolve a dotted mapping/list path without inventing missing values."""
    if not path:
        raise ValueError("PROJECTION_PATH_REQUIRED")

    value = root
    for segment in path.split("."):
        if isinstance(value, dict):
            if segment not in value:
                raise KeyError(path)
            value = value[segment]
        elif isinstance(value, list):
            try:
                index = int(segment)
            except ValueError as exc:
                raise KeyError(path) from exc
            try:
                value = value[index]
            except IndexError as exc:
                raise KeyError(path) from exc
        else:
            raise KeyError(path)
    return value


def route_signature(reference_decisions: Sequence[dict[str, Any]]) -> str:
    """Canonicalize the required route into one accepted-output identity."""
    if not reference_decisions:
        raise ValueError("DGF_REFERENCE_ROUTE_REQUIRED")

    rows = []
    for index, decision in enumerate(reference_decisions):
        try:
            rows.append(
                {
                    "position": decision.get("position", index + 1),
                    "gate": decision["gate"],
                    "phase": decision["phase"],
                    "disposition": decision["disposition"],
                }
            )
        except KeyError as exc:
            raise ValueError(f"DGF_REFERENCE_DECISION_MALFORMED:{index}") from exc
    return json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_dgf_decision_cases(
    dataset_root: Path,
    *,
    observation_paths: Sequence[str],
    case_dirs: Sequence[Path] | None = None,
) -> tuple[DecisionCase, ...]:
    """Project canonical DGF truth to a candidate permitted-observation surface."""
    paths = tuple(observation_paths)
    if not paths:
        raise ValueError("DGF_PROJECTION_PATHS_REQUIRED")
    if len(paths) != len(set(paths)):
        raise ValueError("DGF_PROJECTION_PATHS_DUPLICATE")

    cases = tuple(case_dirs) if case_dirs is not None else discover_dgf_cases(dataset_root)
    if not cases:
        raise ValueError("DGF_EMPTY_DATASET")

    result = []
    for case_dir in cases:
        hidden = _read_json(case_dir / "99_hidden_ground_truth.json")
        truth = hidden["canonical_truth"]
        observation = {path: dotted_get(truth, path) for path in paths}
        accepted = frozenset({route_signature(hidden["reference_decisions"])})
        result.append(
            DecisionCase(
                case_id=str(hidden.get("case_id", case_dir.name)),
                observation=observation,
                accepted_outputs=accepted,
            )
        )
    return tuple(result)


def audit_dgf_projection(
    dataset_root: Path,
    *,
    observation_paths: Sequence[str],
    case_dirs: Sequence[Path] | None = None,
) -> ProjectionAudit:
    decision_cases = build_dgf_decision_cases(
        dataset_root,
        observation_paths=observation_paths,
        case_dirs=case_dirs,
    )
    return ProjectionAudit(
        observation_paths=tuple(observation_paths),
        report=analyze_information_obstruction(decision_cases),
    )


def search_sufficient_dgf_projections(
    dataset_root: Path,
    *,
    candidate_paths: Sequence[str],
    max_width: int,
    case_dirs: Sequence[Path] | None = None,
) -> tuple[ProjectionAudit, ...]:
    """Return all minimal-width sufficient projections, if any.

    The search stops at the first width that yields at least one sufficient
    projection. This is exhaustive over the supplied candidate path vocabulary
    at each tested width; no model or heuristic ranks paths.
    """
    paths = tuple(candidate_paths)
    if not paths:
        raise ValueError("DGF_CANDIDATE_PATHS_REQUIRED")
    if len(paths) != len(set(paths)):
        raise ValueError("DGF_CANDIDATE_PATHS_DUPLICATE")
    if max_width < 1:
        raise ValueError("DGF_MAX_WIDTH_MUST_BE_POSITIVE")

    upper = min(max_width, len(paths))
    for width in range(1, upper + 1):
        admitted = tuple(
            audit
            for subset in combinations(paths, width)
            if (
                audit := audit_dgf_projection(
                    dataset_root,
                    observation_paths=subset,
                    case_dirs=case_dirs,
                )
            ).sufficient
        )
        if admitted:
            return admitted
    return ()
