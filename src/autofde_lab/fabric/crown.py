"""Machine-checkable Crown requirements for AutoFDE Lab.

This is a court, not a roadmap generator: a status may only be as strong as
its cited evidence. In particular, the competitive crown is mechanically
closed until every Palantir-parity and differentiation gate is SATISFIED.
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
                problems.append(
                    f"{requirement.requirement_id}: SATISFIED without evidence"
                )
            if (
                requirement.status is RequirementStatus.SATISFIED
                and requirement.external_dependency is not None
            ):
                problems.append(
                    f"{requirement.requirement_id}: external dependency cannot be internally SATISFIED"
                )
            if requirement.requirement_id == "R-1501" and requirement.status is RequirementStatus.SATISFIED:
                if all(
                    path.startswith(("tests/", "fixtures/", "docs/"))
                    for path in requirement.evidence
                ):
                    problems.append("R-1501: ADOPTED cannot be established by internal fixtures/docs")
        return tuple(problems)


# Statuses below describe the branch's presently established evidence, not the
# desired end state. Existing capabilities that have not been executed in the
# current evidence context remain PARTIAL even when their source is substantial.
_REQUIREMENTS = (
    CrownRequirement("R-001", "Zero unreceipted actuation; DO implies BRCE.", RequirementStatus.PARTIAL, (".claude/rules/actuation-boundary.md",), "Any external mutation outside the admitted broker boundary."),
    CrownRequirement("R-002", "Planner/model output is a candidate, never authority.", RequirementStatus.PARTIAL, ("src/autofde_lab/hub/solver/CLAUDE.md", "src/autofde_lab/fabric/selection.py"), "A solver directly actuates external state."),
    CrownRequirement("R-003", "Acknowledgement, effect, postcondition and verification are distinct states.", RequirementStatus.PARTIAL, (".claude/rules/actuation-boundary.md",), "An acknowledged command is accepted as verified consequence."),
    CrownRequirement("R-004", "Consequential success requires independent postcondition verification where possible.", RequirementStatus.PARTIAL, (".claude/rules/standing-law.md",), "Executor self-report alone establishes consequence."),
    CrownRequirement("R-005", "Typed refusal is positive evidence and fail-closed behavior.", RequirementStatus.PARTIAL, ("src/autofde_lab/autofde/refusals.py", "src/autofde_lab/agent/refusals.py", "src/autofde_lab/fabric/vendor_materialization.py"), "Identity/authority drift silently degrades to success."),
    CrownRequirement("R-006", "Importability/compilation/mocks do not establish runtime ALIVE.", RequirementStatus.PARTIAL, ("src/autofde_lab/hub/solver/CLAUDE.md",), "Import-only evidence establishes ALIVE."),
    CrownRequirement("R-007", "No capability receives stronger standing than its evidence.", RequirementStatus.PARTIAL, (".claude/rules/standing-law.md", "src/autofde_lab/fabric/selection.py"), "Untested applicable competitor permits HOT crown."),
    CrownRequirement("R-100", "Ontology-first model prefers public vocabularies.", RequirementStatus.PARTIAL, ("src/autofde_lab/autofde/ontology.py",), "Canonical semantics require only proprietary vocabulary."),
    CrownRequirement("R-101", "World model covers subjects, observations, state, capabilities, authority, effects and evidence.", RequirementStatus.PARTIAL, ("src/autofde_lab/autofde/ontology.py",), "Required causal concept has no semantic representation."),
    CrownRequirement("R-102", "Important graph boundaries are mechanically admitted by SHACL/equivalent constraints.", RequirementStatus.PARTIAL, ("ontology/",), "Natural-language-only admission remains on a consequential boundary."),
    CrownRequirement("R-103", "Semantic actions expose identity, contracts, authority, effects, verification and reconciliation.", RequirementStatus.PARTIAL, ("src/autofde_lab/autofde/phase_graph.py",), "Action lacks an authority/effect/verification contract."),
    CrownRequirement("R-104", "Canonical world model is portable through open semantic representations.", RequirementStatus.PARTIAL, ("src/autofde_lab/autofde/ontology.py",), "World model requires a proprietary ontology runtime."),
    CrownRequirement("R-200", "Preserve and expand the heterogeneous formal solver ecology.", RequirementStatus.PARTIAL, ("pyproject.toml", "src/autofde_lab/hub/solver/CLAUDE.md"), "Registered solver is silently removed or collapsed into one model planner."),
    CrownRequirement("R-201", "Admitted problems have structural signatures for decision-class recognition.", RequirementStatus.SATISFIED, ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"), "Unknown properties satisfy a planner requirement."),
    CrownRequirement("R-202", "Applicability is resolved before empirical ranking.", RequirementStatus.SATISFIED, ("src/autofde_lab/fabric/selection.py", "src/autofde_lab/fabric/coverage.py", "tests/fabric/test_selection.py"), "Inapplicable planner reaches Pareto ranking."),
    CrownRequirement("R-300", "Choosing mature machinery becomes indexed retrieval rather than repeated open-ended model deliberation.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/selection.py", "src/autofde_lab/fabric/selection_store.py"), "Production selector still requires frontier inference for an exact HOT signature."),
    CrownRequirement("R-301", "Cheap structural classification precedes expensive interpretation.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/selection.py",), "Expensive planner/model exploration occurs before structural applicability filtering."),
    CrownRequirement("R-302", "Semantic possibility space is indexed so runtime touches only the relevant partition.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/selection_store.py",), "Selection requires full-corpus traversal at runtime."),
    CrownRequirement("R-303", "Planner selection accumulates immutable empirical receipts across runs.", RequirementStatus.SATISFIED, ("src/autofde_lab/fabric/selection_store.py", "tests/fabric/test_selection_store.py"), "Process restart erases the evidence used to establish HOT standing."),
    CrownRequirement("R-304", "Planner choice preserves the measured Pareto frontier; ties are not false wins.", RequirementStatus.SATISFIED, ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"), "Tied or non-dominated candidate is silently discarded."),
    CrownRequirement("R-400", "HOT exact signatures can route without generalized model deliberation.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/selection.py",), "HOT route intrinsically calls a frontier model."),
    CrownRequirement("R-401", "WARM paths bound exploration to empirically justified candidates.", RequirementStatus.SATISFIED, ("src/autofde_lab/fabric/selection.py", "tests/fabric/test_selection.py"), "WARM ignores applicability/Pareto evidence."),
    CrownRequirement("R-402", "COLD discovery manufactures evidence for future WARM/HOT routes.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/selection_store.py",), "Cold evidence cannot be persisted/reused by later selection."),
    CrownRequirement("R-500", "Successful expensive cognition is examinable for compilation into reusable machinery.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/cognition_debt.py",), "Repeated exact HOT cognition remains invisible."),
    CrownRequirement("R-501", "Repeated frontier cognition on verified HOT exact signatures is measurable technical debt.", RequirementStatus.SATISFIED, ("src/autofde_lab/fabric/cognition_debt.py", "tests/fabric/test_cognition_debt.py"), "Cold/unverified work is incorrectly granted compilation authority."),
    CrownRequirement("R-502", "Stable admitted structures are eligible for deterministic ggen manufacture.", RequirementStatus.PARTIAL, (".claude/rules/ecosystem-boundary.md",), "Stable structure has no deterministic manufacture handoff."),
    CrownRequirement("R-503", "Semantic capability caching never bypasses authority or postcondition verification.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/cache.py",), "Cache hit grants actuation authority."),
    CrownRequirement("R-600", "Model-provider choice is replaceable and not part of correctness.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/bridge.py",), "Correctness depends on one model vendor."),
    CrownRequirement("R-601", "Agent/session context is durable and resumable.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/session.py", "src/autofde_lab/agent/ledger.py"), "Session loss destroys admitted state without evidence."),
    CrownRequirement("R-602", "Agent handoffs are typed, authority-narrowing and evidence-linked.", RequirementStatus.MISSING, (), "Untyped handoff can broaden authority."),
    CrownRequirement("R-603", "Input/output/tool guardrails exist below the BRCE actuation authority boundary.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/faults.py",), "Guardrail is treated as equivalent to actuation authority."),
    CrownRequirement("R-604", "Model, tool, planner, handoff, authority, actuation and verification events are traceable into evidence.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/ledger.py", "src/autofde_lab/agent/ocel_sink.py"), "Consequential transition has no trace/evidence lineage."),
    CrownRequirement("R-605", "Long-horizon harness supports planning, task graph, checkpoint, interruption and workspace/tool policy.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/session.py", "src/autofde_lab/agent/replan.py"), "Long-horizon session cannot resume after interruption."),
    CrownRequirement("R-700", "Long-running workflows survive process/worker/network failure.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/session.py", "src/autofde_lab/agent/ledger.py"), "Restart loses workflow standing."),
    CrownRequirement("R-701", "Deterministic history is replayable; nondeterminism is captured as observation.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/ledger.py",), "Replay re-reads uncaptured nondeterministic input."),
    CrownRequirement("R-702", "Consequential operations declare idempotency semantics.", RequirementStatus.PARTIAL, (".claude/rules/actuation-boundary.md",), "Unknown-idempotency operation is retried as if safe."),
    CrownRequirement("R-703", "Possible actuation plus lost acknowledgement enters UNCERTAIN/reconciliation rather than blind retry.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/faults.py", "src/autofde_lab/agent/replan.py"), "Uncertain consequential operation is blindly repeated."),
    CrownRequirement("R-800", "GymAct-compatible executable-world abstraction keeps environment-specific physics explicit.", RequirementStatus.PARTIAL, ("src/autofde_lab/forwardbench/",), "Heterogeneous effectors are falsely normalized into identical semantics."),
    CrownRequirement("R-801", "Real provider surface spans browser, cluster, IaC, API/MCP and benchmark environments.", RequirementStatus.PARTIAL, ("src/autofde_lab/adapters/", "src/autofde_lab/forwardbench/"), "Provider category lacks a real-system witness."),
    CrownRequirement("R-802", "Mocks may test mechanics but never establish integration crown.", RequirementStatus.PARTIAL, (".claude/rules/standing-law.md",), "Mock-only result receives ALIVE."),
    CrownRequirement("R-803", "Provider ALIVE requires execution against a real compatible system.", RequirementStatus.PARTIAL, (".claude/rules/standing-law.md",), "Real-system dependency is skipped but ALIVE remains."),
    CrownRequirement("R-900", "Actuation is bound to principal, capability, scope, policy, authority and intended effect.", RequirementStatus.PARTIAL, (".claude/rules/actuation-boundary.md",), "Receipt omits authority identity/scope."),
    CrownRequirement("R-901", "Autonomous execution receives least authority.", RequirementStatus.PARTIAL, (".claude/rules/fde-authority-boundary.md",), "Broad standing credential is used where narrower capability exists."),
    CrownRequirement("R-902", "Automation cannot silently exceed authenticated principal permission.", RequirementStatus.PARTIAL, (".claude/rules/fde-authority-boundary.md",), "Delegation broadens user authority."),
    CrownRequirement("R-903", "Autonomous policy may be stricter than the human principal's own permission.", RequirementStatus.PARTIAL, (".claude/rules/fde-authority-boundary.md",), "Human permission automatically implies autonomous admission."),
    CrownRequirement("R-904", "Authority/policy is representable in open machine-readable policy semantics where practical.", RequirementStatus.PARTIAL, ("ontology/",), "Consequential policy exists only as application prose."),
    CrownRequirement("R-905", "Mutable artifacts default to branch/proposal/validation before merge/deploy when staging is possible.", RequirementStatus.PARTIAL, ("src/autofde_lab/autofde/github_projection.py",), "Direct production mutation occurs where a staged proposal path exists."),
    CrownRequirement("R-1000", "Important evidence and artifacts carry content-addressed identity.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/canonical.py", "src/autofde_lab/agent/ledger.py"), "Evidence can change without identity changing."),
    CrownRequirement("R-1001", "Receipts preserve causal provenance from observation through verification.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/ledger.py",), "Receipt cannot reconstruct causal predecessor chain."),
    CrownRequirement("R-1002", "Replay detects changed evidence, policy, planner, environment, capability or revision.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/ledger.py", "src/autofde_lab/fabric/vendor_materialization.py"), "Revision drift replays as equivalent."),
    CrownRequirement("R-1003", "Independent verifier implementations can be composed for differential confidence.", RequirementStatus.MISSING, (), "One implementation self-certifies every consequential outcome."),
    CrownRequirement("R-1100", "Partial-order process semantics preserve concurrency and choice without forced serialization.", RequirementStatus.PARTIAL, ("src/autofde_lab/autofde/phase_graph.py",), "Independent transitions are serialized without semantic cause."),
    CrownRequirement("R-1101", "Process semantics can be delegated to wasm4pm for execution/verification where supported.", RequirementStatus.PARTIAL, (".claude/rules/ecosystem-boundary.md",), "Process claim has no wasm4pm evidence where supported."),
    CrownRequirement("R-1102", "Execution evidence feeds conformance, bottleneck, drift, remaining-time, handover and decision mining.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/ocel_sink.py",), "Execution evidence cannot feed process analysis."),
    CrownRequirement("R-1103", "Operational workflows expose Little's Law quantities where meaningful.", RequirementStatus.MISSING, (), "Workflow optimization reports productivity while hiding WIP/wait time."),
    CrownRequirement("R-1200", "Closed-loop causal diameter is measurable.", RequirementStatus.SATISFIED, ("src/autofde_lab/fabric/metrics.py", "tests/fabric/test_metrics.py"), "Decision latency is reported without observation/actuation/verification latency."),
    CrownRequirement("R-1201", "Stable bounded control can be pushed toward effectors when authority/safety permit.", RequirementStatus.MISSING, (), "All mature control remains centrally model-mediated."),
    CrownRequirement("R-1202", "Central generalized intelligence is not required in every mature local control loop.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/selection.py", "src/autofde_lab/fabric/metrics.py"), "HOT route structurally requires model inference."),
    CrownRequirement("R-1300", "Query plane is polyglot across semantic, relational, search and process views.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/kgc.py",), "Canonical data requires application-specific traversal."),
    CrownRequirement("R-1301", "Large RDF/semantic workloads target indexed QLever-class execution rather than app traversal.", RequirementStatus.MISSING, (), "Large semantic selection scans the full graph per decision."),
    CrownRequirement("R-1302", "Important query/selector decisions expose measurable execution cost/evidence.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/selection.py", "src/autofde_lab/fabric/metrics.py"), "Selector choice has no measurable basis."),
    CrownRequirement("R-1400", "Ontology constraints can manufacture combinatorial synthetic/adversarial scenarios.", RequirementStatus.PARTIAL, ("src/autofde_lab/forwardbench/",), "Scenario generation cannot derive from admitted semantics."),
    CrownRequirement("R-1401", "Applicable planners can run tournaments on equivalent admitted subjects.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/coverage.py",), "Planner preference is asserted without equivalent measured runs."),
    CrownRequirement("R-1402", "Independent implementations can act as differential oracles.", RequirementStatus.MISSING, (), "Semantic disagreement between implementations is unobservable."),
    CrownRequirement("R-1403", "Critical authority/verification/selection/receipt invariants have mutation/falsification tests.", RequirementStatus.PARTIAL, ("tests/fabric/test_selection.py", "tests/fabric/test_vendor_materialization.py"), "Incorrect implementation survives the falsification suite."),
    CrownRequirement("R-1500", "Enterprise crown requires technical ALIVE plus external ADOPTED evidence.", RequirementStatus.PARTIAL, (".claude/rules/standing-law.md",), "Internal test alone establishes enterprise crown."),
    CrownRequirement("R-1501", "ADOPTED requires a real external organization/operator depending on consequential capability.", RequirementStatus.BLOCKED, (), "Internal fixture establishes customer adoption.", external_dependency="real external customer/operator evidence"),
    CrownRequirement("R-1502", "Flagships report cost, latency, intervention, reconciliation, tokens, compute and reuse distribution.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/metrics.py",), "Flagship omits closed-loop economics."),
    CrownRequirement("P1", "Palantir parity: operational ontology objects, links and actions.", RequirementStatus.PARTIAL, ("src/autofde_lab/autofde/ontology.py",), "Equivalent ontology/action workload cannot be represented."),
    CrownRequirement("P2", "Palantir parity: fine-grained identity-bound governance and audit.", RequirementStatus.PARTIAL, (".claude/rules/fde-authority-boundary.md", "src/autofde_lab/agent/ledger.py"), "Equivalent permission boundary cannot be enforced/audited."),
    CrownRequirement("P3", "Palantir parity: natural-language and programmatic FDE operation over the platform.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/fde.py", "src/autofde_lab/fabric/mcp.py"), "Equivalent FDE task cannot be expressed through supported surfaces."),
    CrownRequirement("P4", "Palantir parity: safe branch, validation, review and merge/deployment workflow.", RequirementStatus.PARTIAL, ("src/autofde_lab/autofde/github_projection.py",), "Staged change cannot be independently reviewed before merge."),
    CrownRequirement("P5", "Palantir parity: real heterogeneous enterprise integrations.", RequirementStatus.PARTIAL, ("src/autofde_lab/adapters/", "src/autofde_lab/forwardbench/"), "Representative enterprise integration lacks real-system evidence."),
    CrownRequirement("P6", "Palantir parity: repeatable local/cloud/edge deployment.", RequirementStatus.MISSING, (), "Equivalent deployment cannot be reproduced across environments."),
    CrownRequirement("P7", "Palantir parity: trace planning, manufacture and execution end-to-end.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/ledger.py", "src/autofde_lab/agent/ocel_sink.py"), "Causal step disappears from trace lineage."),
    CrownRequirement("D1", "Differentiator: formal planner breadth and measured problem-class specialization.", RequirementStatus.PARTIAL, ("pyproject.toml", "src/autofde_lab/fabric/coverage.py"), "Frontier model remains the only effective decision engine."),
    CrownRequirement("D2", "Differentiator: indexed empirical selection can replace generalized reasoning on mature paths.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/selection.py", "src/autofde_lab/fabric/selection_store.py"), "Exact mature route still requires open-ended model planner selection."),
    CrownRequirement("D3", "Differentiator: independent postcondition verification is universal for consequential actions where possible.", RequirementStatus.PARTIAL, (".claude/rules/standing-law.md",), "Consequential provider lacks independent verifier semantics."),
    CrownRequirement("D4", "Differentiator: canonical semantics remain portable through public/open ontology formats.", RequirementStatus.PARTIAL, ("src/autofde_lab/autofde/ontology.py",), "Core ontology cannot be exported independently."),
    CrownRequirement("D5", "Differentiator: repeated task economics exhibit a persistent crossover versus model-centric baseline.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/metrics.py", "tests/fabric/test_metrics.py"), "Only one-off benchmark wins exist; no persistent crossover."),
    CrownRequirement("D6", "Differentiator: bounded controllers can reduce causal distance by executing near effectors.", RequirementStatus.MISSING, (), "No local-controller placement/evidence exists."),
    CrownRequirement("D7", "Differentiator: full causal chain has reproducible content-bound receipts and replay.", RequirementStatus.PARTIAL, ("src/autofde_lab/agent/ledger.py", "src/autofde_lab/fabric/vendor_materialization.py"), "Replay cannot detect material identity drift."),
    CrownRequirement("D8", "Differentiator: successful cold-path cognition becomes durable indexed/manufactured capability.", RequirementStatus.PARTIAL, ("src/autofde_lab/fabric/cognition_debt.py", "src/autofde_lab/fabric/selection_store.py"), "Cold success cannot reduce later model dependence."),
)


def crown_report(requirements: Iterable[CrownRequirement] = _REQUIREMENTS) -> CrownReport:
    report = CrownReport(tuple(requirements))
    problems = report.validate()
    if problems:
        raise ValueError("invalid Crown requirement registry: " + "; ".join(problems))
    return report
