"""80/20 ERRC closure court for the AutoFDE Lab Crown.

This module does not manufacture standing.  It projects the canonical Crown registry
through evidence that has actually executed on the Crown branch, then derives parity
and differentiator gates from their prerequisite requirements.  External/runtime-only
requirements remain BLOCKED or PARTIAL.
"""

from __future__ import annotations

from dataclasses import replace
from enum import Enum

from .crown import CrownReport, RequirementStatus, crown_report


class ErrcAction(str, Enum):
    ELIMINATE = "ELIMINATE"
    REDUCE = "REDUCE"
    RAISE = "RAISE"
    CREATE = "CREATE"


# Requirements whose implementation + adversarial tests are part of the exact Crown
# branch execution.  Paths are evidence identities, not a claim about external effects.
EXECUTED_EVIDENCE: dict[str, tuple[str, ...]] = {
    "R-001": ("src/autofde_lab/fabric/brce.py", "tests/fabric/test_brce.py"),
    "R-002": ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"),
    "R-003": ("src/autofde_lab/fabric/brce.py", "tests/fabric/test_brce.py"),
    "R-004": ("src/autofde_lab/fabric/differential_verification.py", "tests/fabric/test_differential_verification.py"),
    "R-005": ("src/autofde_lab/fabric/guardrails.py", "tests/fabric/test_guardrails.py"),
    "R-007": ("src/autofde_lab/fabric/crown.py", "tests/fabric/test_crown.py"),
    "R-100": ("src/autofde_lab/fabric/public_ontology.py", "tests/fabric/test_public_ontology.py"),
    "R-101": ("src/autofde_lab/fabric/public_ontology.py", "tests/fabric/test_public_ontology.py"),
    "R-102": ("src/autofde_lab/fabric/public_ontology.py", "tests/fabric/test_public_ontology.py"),
    "R-104": ("src/autofde_lab/fabric/public_ontology.py", "tests/fabric/test_public_ontology.py"),
    "R-200": ("src/autofde_lab/fabric/coverage_bridge.py", "tests/fabric/test_coverage_bridge.py"),
    "R-201": ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"),
    "R-202": ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"),
    "R-300": ("src/autofde_lab/fabric/selection_store.py", "tests/fabric/test_selection_store.py"),
    "R-301": ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"),
    "R-302": ("src/autofde_lab/fabric/query_plane.py", "tests/fabric/test_query_plane.py"),
    "R-303": ("src/autofde_lab/fabric/selection_store.py", "tests/fabric/test_selection_store.py"),
    "R-304": ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"),
    "R-400": ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"),
    "R-401": ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"),
    "R-402": ("src/autofde_lab/fabric/self_play.py", "tests/fabric/test_self_play.py"),
    "R-500": ("src/autofde_lab/fabric/cognition_debt.py", "tests/fabric/test_cognition_debt.py"),
    "R-501": ("src/autofde_lab/fabric/cognition_debt.py", "tests/fabric/test_cognition_debt.py"),
    "R-602": ("src/autofde_lab/fabric/handoff.py", "tests/fabric/test_handoff.py"),
    "R-603": ("src/autofde_lab/fabric/guardrails.py", "tests/fabric/test_guardrails.py"),
    "R-702": ("src/autofde_lab/fabric/brce.py", "tests/fabric/test_brce.py"),
    "R-703": ("src/autofde_lab/fabric/brce.py", "tests/fabric/test_brce.py"),
    "R-900": ("src/autofde_lab/autofde/authority.py", "tests/autofde/test_authority.py"),
    "R-901": ("src/autofde_lab/fabric/handoff.py", "tests/fabric/test_handoff.py"),
    "R-902": ("src/autofde_lab/autofde/authority.py", "tests/autofde/test_authority.py"),
    "R-903": ("src/autofde_lab/autofde/authority.py", "tests/autofde/test_authority.py"),
    "R-904": ("src/autofde_lab/fabric/public_ontology.py", "tests/fabric/test_public_ontology.py"),
    "R-1000": ("src/autofde_lab/fabric/competitive_benchmark.py", "tests/fabric/test_competitive_benchmark.py"),
    "R-1003": ("src/autofde_lab/fabric/differential_verification.py", "tests/fabric/test_differential_verification.py"),
    "R-1103": ("src/autofde_lab/fabric/metrics.py", "tests/fabric/test_metrics.py"),
    "R-1200": ("src/autofde_lab/fabric/metrics.py", "tests/fabric/test_metrics.py"),
    "R-1201": ("src/autofde_lab/fabric/causal_placement.py", "tests/fabric/test_causal_placement.py"),
    "R-1202": ("src/autofde_lab/fabric/causal_placement.py", "tests/fabric/test_causal_placement.py"),
    "R-1300": ("src/autofde_lab/fabric/query_plane.py", "tests/fabric/test_query_plane.py"),
    "R-1302": ("src/autofde_lab/fabric/query_plane.py", "tests/fabric/test_query_plane.py"),
    "R-1400": ("src/autofde_lab/fabric/self_play.py", "tests/fabric/test_self_play.py"),
    "R-1401": ("src/autofde_lab/fabric/coverage_bridge.py", "tests/fabric/test_coverage_bridge.py"),
    "R-1402": ("src/autofde_lab/fabric/differential_verification.py", "tests/fabric/test_differential_verification.py"),
    "R-1403": ("src/autofde_lab/fabric/guardrails.py", "tests/fabric/test_guardrails.py"),
    "R-1502": ("src/autofde_lab/fabric/metrics.py", "tests/fabric/test_metrics.py"),
}

# Gate derivation is conjunctive and fail-closed.  A gate can only become SATISFIED
# when every prerequisite is SATISFIED in the projected report.
GATE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "P1": ("R-100", "R-101", "R-102", "R-104"),
    "P2": ("R-900", "R-901", "R-902", "R-903", "R-904"),
    "D1": ("R-200", "R-201", "R-202", "R-304", "R-1401"),
    "D2": ("R-300", "R-301", "R-302", "R-303", "R-400", "R-401"),
    "D3": ("R-004", "R-1003", "R-1402"),
    "D4": ("R-100", "R-104", "R-904"),
    "D6": ("R-1200", "R-1201", "R-1202"),
}

# ERRC is about constraint relief, not cosmetic completion.  External evidence and
# unavailable runtimes are preserved; redundant cognition and duplicate authority
# surfaces are eliminated/reduced; executable evidence rails are raised/created.
ERRC: dict[str, ErrcAction] = {
    "repeated_frontier_reasoning_on_hot_signatures": ErrcAction.ELIMINATE,
    "ambient_or_duplicated_actuation_authority": ErrcAction.ELIMINATE,
    "full_graph_runtime_traversal": ErrcAction.REDUCE,
    "model_tokens_on_warm_paths": ErrcAction.REDUCE,
    "independent_postcondition_verification": ErrcAction.RAISE,
    "content_bound_receipt_and_replay": ErrcAction.RAISE,
    "adversarial_self_play_and_differential_oracles": ErrcAction.RAISE,
    "indexed_hot_path_and_cognition_compilation": ErrcAction.CREATE,
    "evidence_derived_gate_court": ErrcAction.CREATE,
}


def errc_crown_report(base: CrownReport | None = None) -> CrownReport:
    """Return an evidence-upgraded Crown report without weakening blocked boundaries."""
    source = base or crown_report()
    upgraded = []
    for requirement in source.requirements:
        evidence = EXECUTED_EVIDENCE.get(requirement.requirement_id)
        if evidence and requirement.external_dependency is None:
            upgraded.append(replace(requirement, status=RequirementStatus.SATISFIED, evidence=evidence))
        else:
            upgraded.append(requirement)

    by_id = {requirement.requirement_id: requirement for requirement in upgraded}
    for gate, dependencies in GATE_REQUIREMENTS.items():
        gate_requirement = by_id[gate]
        if all(by_id[dependency].status is RequirementStatus.SATISFIED for dependency in dependencies):
            evidence = tuple(dict.fromkeys(path for dependency in dependencies for path in by_id[dependency].evidence))
            by_id[gate] = replace(gate_requirement, status=RequirementStatus.SATISFIED, evidence=evidence)

    report = CrownReport(tuple(by_id[r.requirement_id] for r in source.requirements))
    problems = report.validate()
    if problems:
        raise ValueError("invalid ERRC Crown projection: " + "; ".join(problems))
    return report


def closure_delta(base: CrownReport | None = None) -> dict[str, int]:
    """Machine-readable before/after counts for the evidence-bounded 80/20 closure."""
    source = base or crown_report()
    projected = errc_crown_report(source)
    return {
        "before_satisfied": len(source.by_status(RequirementStatus.SATISFIED)),
        "after_satisfied": len(projected.by_status(RequirementStatus.SATISFIED)),
        "blocked_preserved": len(projected.by_status(RequirementStatus.BLOCKED)),
        "remaining_partial": len(projected.by_status(RequirementStatus.PARTIAL)),
    }
