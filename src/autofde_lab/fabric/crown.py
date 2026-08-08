"""Machine-checkable Crown court for AutoFDE Lab.

The court is fail closed: a competitive crown exists only when every Palantir
parity gate P1-P7 and differentiator gate D1-D8 has evidence-backed SATISFIED
standing. Partial source surfaces never self-promote to runtime standing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class RequirementStatus(str, Enum):
    SATISFIED = "SATISFIED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class CrownRequirement:
    requirement_id: str
    statement: str
    status: RequirementStatus
    evidence: tuple[str, ...] = ()
    falsifier: str = ""
    external_dependency: str | None = None


@dataclass(frozen=True, slots=True)
class CrownReport:
    requirements: tuple[CrownRequirement, ...]

    def by_status(self, status: RequirementStatus) -> tuple[CrownRequirement, ...]:
        return tuple(r for r in self.requirements if r.status is status)

    def get(self, requirement_id: str) -> CrownRequirement:
        for requirement in self.requirements:
            if requirement.requirement_id == requirement_id:
                return requirement
        raise KeyError(requirement_id)

    @property
    def palantir_defeat_ready(self) -> bool:
        gates = [f"P{i}" for i in range(1, 8)] + [f"D{i}" for i in range(1, 9)]
        return all(self.get(gate).status is RequirementStatus.SATISFIED for gate in gates)

    def validate(self) -> tuple[str, ...]:
        problems: list[str] = []
        ids = [r.requirement_id for r in self.requirements]
        duplicates = sorted({rid for rid in ids if ids.count(rid) > 1})
        if duplicates:
            problems.append(f"duplicate requirement ids: {duplicates}")
        for requirement in self.requirements:
            if requirement.status is RequirementStatus.SATISFIED and not requirement.evidence:
                problems.append(f"{requirement.requirement_id}: SATISFIED without evidence")
            if requirement.status is RequirementStatus.SATISFIED and requirement.external_dependency:
                problems.append(f"{requirement.requirement_id}: external dependency cannot be internally SATISFIED")
            if requirement.requirement_id == "R-1501" and requirement.status is RequirementStatus.SATISFIED:
                if all(path.startswith(("tests/", "fixtures/", "docs/")) for path in requirement.evidence):
                    problems.append("R-1501: ADOPTED cannot be established by internal fixtures/docs")
        return tuple(problems)


_STATEMENTS = {
    "R-001": "Zero unreceipted actuation; DO implies BRCE.",
    "R-002": "Planner/model output is a candidate, never authority.",
    "R-003": "Acknowledgement, effect, postcondition and verification are distinct states.",
    "R-004": "Consequential success requires independent postcondition verification where possible.",
    "R-005": "Typed refusal is positive evidence and fail-closed behavior.",
    "R-006": "Importability/compilation/mocks do not establish runtime ALIVE.",
    "R-007": "No capability receives stronger standing than its evidence.",
    "R-100": "Ontology-first model prefers public vocabularies.",
    "R-101": "World model covers subjects, observations, state, capabilities, authority, effects and evidence.",
    "R-102": "Important graph boundaries are mechanically admitted by SHACL/equivalent constraints.",
    "R-103": "Semantic actions expose identity, contracts, authority, effects, verification and reconciliation.",
    "R-104": "Canonical world model is portable through open semantic representations.",
    "R-200": "Preserve and expand the heterogeneous formal solver ecology.",
    "R-201": "Admitted problems have structural signatures for decision-class recognition.",
    "R-202": "Applicability is resolved before empirical ranking.",
    "R-300": "Choosing mature machinery becomes indexed retrieval rather than repeated open-ended model deliberation.",
    "R-301": "Cheap structural classification precedes expensive interpretation.",
    "R-302": "Semantic possibility space is indexed so runtime touches only the relevant partition.",
    "R-303": "Planner selection accumulates immutable empirical receipts across runs.",
    "R-304": "Planner choice preserves the measured Pareto frontier; ties are not false wins.",
    "R-400": "HOT exact signatures can route without generalized model deliberation.",
    "R-401": "WARM paths bound exploration to empirically justified candidates.",
    "R-402": "COLD discovery manufactures evidence for future WARM/HOT routes.",
    "R-500": "Successful expensive cognition is examinable for compilation into reusable machinery.",
    "R-501": "Repeated frontier cognition on verified HOT exact signatures is measurable technical debt.",
    "R-502": "Stable admitted structures are eligible for deterministic ggen manufacture.",
    "R-503": "Semantic capability caching never bypasses authority or postcondition verification.",
    "R-600": "Model-provider choice is replaceable and not part of correctness.",
    "R-601": "Agent/session context is durable and resumable.",
    "R-602": "Agent handoffs are typed, authority-narrowing and evidence-linked.",
    "R-603": "Input/output/tool guardrails exist below the BRCE actuation authority boundary.",
    "R-604": "Model, tool, planner, handoff, authority, actuation and verification events are traceable into evidence.",
    "R-605": "Long-horizon harness supports planning, task graph, checkpoint, interruption and workspace/tool policy.",
    "R-700": "Long-running workflows survive process/worker/network failure.",
    "R-701": "Deterministic history is replayable; nondeterminism is captured as observation.",
    "R-702": "Consequential operations declare idempotency semantics.",
    "R-703": "Possible actuation plus lost acknowledgement enters UNCERTAIN/reconciliation rather than blind retry.",
    "R-800": "GymAct-compatible executable-world abstraction keeps environment-specific physics explicit.",
    "R-801": "Real provider surface spans browser, cluster, IaC, API/MCP and benchmark environments.",
    "R-802": "Mocks may test mechanics but never establish integration crown.",
    "R-803": "Provider ALIVE requires execution against a real compatible system.",
    "R-900": "Actuation is bound to principal, capability, scope, policy, authority and intended effect.",
    "R-901": "Autonomous execution receives least authority.",
    "R-902": "Automation cannot silently exceed authenticated principal permission.",
    "R-903": "Autonomous policy may be stricter than the human principal's own permission.",
    "R-904": "Authority/policy is representable in open machine-readable policy semantics where practical.",
    "R-905": "Mutable artifacts default to branch/proposal/validation before merge/deploy when staging is possible.",
    "R-1000": "Important evidence and artifacts carry content-addressed identity.",
    "R-1001": "Receipts preserve causal provenance from observation through verification.",
    "R-1002": "Replay detects changed evidence, policy, planner, environment, capability or revision.",
    "R-1003": "Independent verifier implementations can be composed for differential confidence.",
    "R-1100": "Partial-order process semantics preserve concurrency and choice without forced serialization.",
    "R-1101": "Process semantics can be delegated to wasm4pm for execution/verification where supported.",
    "R-1102": "Execution evidence feeds conformance, bottleneck, drift, remaining-time, handover and decision mining.",
    "R-1103": "Operational workflows expose Little's Law quantities where meaningful.",
    "R-1200": "Closed-loop causal diameter is measurable.",
    "R-1201": "Stable bounded control can be pushed toward effectors when authority/safety permit.",
    "R-1202": "Central generalized intelligence is not required in every mature local control loop.",
    "R-1300": "Query plane is polyglot across semantic, relational, search and process views.",
    "R-1301": "Large RDF/semantic workloads target indexed QLever-class execution rather than app traversal.",
    "R-1302": "Important query/selector decisions expose measurable execution cost/evidence.",
    "R-1400": "Ontology constraints can manufacture combinatorial synthetic/adversarial scenarios.",
    "R-1401": "Applicable planners can run tournaments on equivalent admitted subjects.",
    "R-1402": "Independent implementations can act as differential oracles.",
    "R-1403": "Critical authority/verification/selection/receipt invariants have mutation/falsification tests.",
    "R-1500": "Enterprise crown requires technical ALIVE plus external ADOPTED evidence.",
    "R-1501": "ADOPTED requires a real external organization/operator depending on consequential capability.",
    "R-1502": "Flagships report cost, latency, intervention, reconciliation, tokens, compute and reuse distribution.",
    "P1": "Palantir parity: operational ontology objects, links and actions.",
    "P2": "Palantir parity: fine-grained identity-bound governance and audit.",
    "P3": "Palantir parity: natural-language and programmatic FDE operation over the platform.",
    "P4": "Palantir parity: safe branch, validation, review and merge/deployment workflow.",
    "P5": "Palantir parity: real heterogeneous enterprise integrations.",
    "P6": "Palantir parity: repeatable local/cloud/edge deployment.",
    "P7": "Palantir parity: trace planning, manufacture and execution end-to-end.",
    "D1": "Differentiator: formal planner breadth and measured problem-class specialization.",
    "D2": "Differentiator: indexed empirical selection can replace generalized reasoning on mature paths.",
    "D3": "Differentiator: independent postcondition verification is universal for consequential actions where possible.",
    "D4": "Differentiator: canonical semantics remain portable through public/open ontology formats.",
    "D5": "Differentiator: repeated task economics exhibit a persistent crossover versus model-centric baseline.",
    "D6": "Differentiator: bounded controllers can reduce causal distance by executing near effectors.",
    "D7": "Differentiator: full causal chain has reproducible content-bound receipts and replay.",
    "D8": "Differentiator: successful cold-path cognition becomes durable indexed/manufactured capability.",
}

_SATISFIED = {
    "R-201": ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"),
    "R-202": ("src/autofde_lab/fabric/selection.py", "src/autofde_lab/fabric/coverage.py", "tests/fabric/test_selection.py"),
    "R-303": ("src/autofde_lab/fabric/selection_store.py", "tests/fabric/test_selection_store.py"),
    "R-304": ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"),
    "R-401": ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"),
    "R-501": ("src/autofde_lab/fabric/cognition_debt.py", "tests/fabric/test_cognition_debt.py"),
    "R-602": ("src/autofde_lab/fabric/handoff.py", "tests/fabric/test_handoff.py"),
    "R-1003": ("src/autofde_lab/fabric/differential_verification.py", "tests/fabric/test_differential_verification.py"),
    "R-1103": ("src/autofde_lab/fabric/metrics.py", "tests/fabric/test_metrics.py"),
    "R-1200": ("src/autofde_lab/fabric/metrics.py", "tests/fabric/test_metrics.py"),
    "R-1402": ("src/autofde_lab/fabric/differential_verification.py", "tests/fabric/test_differential_verification.py"),
}

_BLOCKED = {
    "R-1301": (("src/autofde_lab/fabric/selection_store.py",), "QLever runtime and benchmark corpus are unavailable in the current cloud environment"),
    "R-1501": ((), "real external customer/operator evidence"),
}

_PARTIAL_EVIDENCE = {
    "R-1201": ("src/autofde_lab/fabric/causal_placement.py", "tests/fabric/test_causal_placement.py"),
    "R-1401": ("src/autofde_lab/fabric/coverage.py", "src/autofde_lab/fabric/coverage_bridge.py"),
    "P6": (".github/workflows/", "src/autofde_lab/adapters/"),
    "D5": ("src/autofde_lab/fabric/metrics.py", "src/autofde_lab/fabric/competitive_benchmark.py", "tests/fabric/test_competitive_benchmark.py"),
    "D6": ("src/autofde_lab/fabric/causal_placement.py", "tests/fabric/test_causal_placement.py"),
}


def _build_requirement(requirement_id: str, statement: str) -> CrownRequirement:
    if requirement_id in _SATISFIED:
        return CrownRequirement(requirement_id, statement, RequirementStatus.SATISFIED, _SATISFIED[requirement_id])
    if requirement_id in _BLOCKED:
        evidence, dependency = _BLOCKED[requirement_id]
        return CrownRequirement(requirement_id, statement, RequirementStatus.BLOCKED, evidence, external_dependency=dependency)
    return CrownRequirement(requirement_id, statement, RequirementStatus.PARTIAL, _PARTIAL_EVIDENCE.get(requirement_id, ()))


_REQUIREMENTS = tuple(_build_requirement(rid, statement) for rid, statement in _STATEMENTS.items())


def crown_report(requirements: Iterable[CrownRequirement] = _REQUIREMENTS) -> CrownReport:
    report = CrownReport(tuple(requirements))
    problems = report.validate()
    if problems:
        raise ValueError("invalid Crown requirement registry: " + "; ".join(problems))
    return report
