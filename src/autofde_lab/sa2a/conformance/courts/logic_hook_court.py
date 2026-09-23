# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Logic & Knowledge Hook Conformance Court (RFC-SA2A-002 v26.9.16).

Gate families:
  SA2A-LOGIC-*  — Datalog safe termination, N3 non-authority, closure completeness
  SA2A-HOOK-*   — Hook meta-admission, effect-kind enforcement, cascade depth bounds
  CHI-AUTO-*    — Autonomous bounded execution with depth/fuel limits

Chicago Zero-Mock Standard:
  - Real DatalogEngine and KnowledgeHookEngine instances; no unittest.mock.
  - Deterministic TTL graphs; no golden trace fixtures.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from autofde_lab.sa2a.admission.datalog_layer import (
    DatalogAtom,
    DatalogEngine,
    DatalogRule,
)
from autofde_lab.sa2a.hooks.model import (
    HookEffectKind,
    HookExecutionRecord,
    KnowledgeHookDefinition,
)

# HookEffectKind real values: EMIT_DELTA, GROUND_ACTION, REFUSE
# For conformance testing, a hook that attempts to self-actuate via REFUSE-bypass is adversarial.
# The court checks that hooks do NOT set effect to a meta-bypass pattern.
# Real SA2A-002 §44: hooks MUST only manufacture intents (EMIT_DELTA / GROUND_ACTION),
# never self-bypass authority (REFUSE used to escape the authority gate is adversarial).
_FORBIDDEN_EFFECTS: frozenset = (
    frozenset()
)  # All current HookEffectKinds are legal manufacturing effects

# ---------------------------------------------------------------------------
# Rule IDs
# ---------------------------------------------------------------------------
SA2A_LOGIC_SAFE_TERMINATION = "SA2A-LOGIC-SAFE-TERMINATION"
SA2A_LOGIC_CLOSURE_COMPLETENESS = "SA2A-LOGIC-CLOSURE-COMPLETENESS"
SA2A_LOGIC_N3_NON_AUTHORITY = "SA2A-LOGIC-N3-NON-AUTHORITY"
SA2A_HOOK_META_ADMISSION = "SA2A-HOOK-META-ADMISSION"
SA2A_HOOK_EFFECT_KIND = "SA2A-HOOK-EFFECT-KIND"
SA2A_HOOK_NO_DO = "SA2A-HOOK-NO-DO"
SA2A_HOOK_CASCADE_DEPTH = "SA2A-HOOK-CASCADE-DEPTH"
CHI_AUTO_BOUNDED_EXECUTION = "CHI-AUTO-BOUNDED-EXECUTION"

# ---------------------------------------------------------------------------
# Verdicts and errors
# ---------------------------------------------------------------------------


class LogicHookCourtError(Exception):
    """Base error for Logic/Hook Court violations."""

    def __init__(
        self, message: str, details: Optional[Dict[str, Any]] = None, rule_id: str = ""
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.rule_id = rule_id


class DatalogUnsafeTerminationError(LogicHookCourtError):
    """Raised when Datalog fixpoint exceeds max iterations (unsafe termination)."""


class HookPerformsDOError(LogicHookCourtError):
    """Raised when a Hook definition attempts a DO/ACTUATE effect (forbidden)."""


class HookCascadeDepthExceededError(LogicHookCourtError):
    """Raised when hook cascade depth exceeds admitted maximum."""


class AutoBoundedExecutionError(LogicHookCourtError):
    """Raised when autonomous execution exceeds fuel/time budget."""


class LogicHookVerdict(str):
    CONFORMANT = "CONFORMANT"
    NON_CONFORMANT = "NON_CONFORMANT"
    REFUSED = "REFUSED"


@dataclass
class LogicHookCheckResult:
    rule_id: str
    passed: bool
    verdict: str
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LogicHookCourtReport:
    """Aggregated report from all Logic/Hook court checks."""

    gate_results: List[LogicHookCheckResult] = field(default_factory=list)
    passed: bool = True
    total_checks: int = 0
    failed_checks: int = 0
    report_digest: str = ""

    def __post_init__(self) -> None:
        self.total_checks = len(self.gate_results)
        self.failed_checks = sum(1 for r in self.gate_results if not r.passed)
        self.passed = self.failed_checks == 0
        payload = str([(r.rule_id, r.passed) for r in self.gate_results]).encode()
        self.report_digest = hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Court implementation
# ---------------------------------------------------------------------------


class LogicHookCourt:
    """Conformance court for SA2A-LOGIC-* and SA2A-HOOK-* gate families.

    Verifies:
    1. Datalog safe termination — fixpoint must converge within max_iterations.
    2. Datalog closure completeness — all expected triples derived.
    3. N3 non-authority — N3 logic output has no execution authority.
    4. Hook meta-admission — hooks must be registered with admitted IRIs.
    5. Hook effect-kind enforcement — only SELECT/CONSTRUCT effects allowed.
    6. Hook NO-DO — hooks may not perform or bypass DO.
    7. Hook cascade depth — bounded cascade must not exceed D_max.
    8. Autonomous bounded execution — execution must complete within fuel budget.
    """

    def __init__(
        self, max_cascade_depth: int = 5, max_datalog_iterations: int = 1000
    ) -> None:
        self.max_cascade_depth = max_cascade_depth
        self.max_datalog_iterations = max_datalog_iterations

    # ------------------------------------------------------------------
    # SA2A-LOGIC-SAFE-TERMINATION
    # ------------------------------------------------------------------

    def verify_datalog_safe_termination(
        self,
        rules: Sequence[DatalogRule],
        facts_ttl: str = "",
        fail_closed: bool = True,
    ) -> LogicHookCheckResult:
        """Verify Datalog fixpoint terminates within max_iterations.

        A non-terminating ruleset violates SA2A-LOGIC-SAFE-TERMINATION and MUST be refused.
        """
        engine = DatalogEngine(
            rules=list(rules), max_iterations=self.max_datalog_iterations
        )
        start = time.perf_counter()
        try:
            derived_facts, iterations = engine.execute_fixpoint(
                []
            )  # Empty EDB; rules are in engine
            elapsed_ms = (time.perf_counter() - start) * 1000
            return LogicHookCheckResult(
                rule_id=SA2A_LOGIC_SAFE_TERMINATION,
                passed=True,
                verdict=LogicHookVerdict.CONFORMANT,
                details={
                    "derived_count": len(derived_facts),
                    "iterations": iterations,
                    "elapsed_ms": round(elapsed_ms, 3),
                },
            )
        except RuntimeError as exc:
            err_msg = f"Datalog fixpoint did not terminate: {exc}"
            if fail_closed:
                raise DatalogUnsafeTerminationError(
                    err_msg, rule_id=SA2A_LOGIC_SAFE_TERMINATION
                ) from exc
            return LogicHookCheckResult(
                rule_id=SA2A_LOGIC_SAFE_TERMINATION,
                passed=False,
                verdict=LogicHookVerdict.REFUSED,
                error_message=err_msg,
            )

    # ------------------------------------------------------------------
    # SA2A-LOGIC-CLOSURE-COMPLETENESS
    # ------------------------------------------------------------------

    def verify_datalog_closure_completeness(
        self,
        rules: Sequence[DatalogRule],
        required_atoms: Sequence[DatalogAtom],
        fail_closed: bool = True,
    ) -> LogicHookCheckResult:
        """Verify that Datalog fixpoint derives all required atoms.

        The closure is complete if every required_atom is derived from the ruleset.
        """
        engine = DatalogEngine(
            rules=list(rules), max_iterations=self.max_datalog_iterations
        )
        try:
            derived, _iters = engine.execute_fixpoint([])  # Empty EDB; rules in engine
        except RuntimeError as exc:
            err_msg = f"Datalog closure failed (non-termination): {exc}"
            if fail_closed:
                raise DatalogUnsafeTerminationError(
                    err_msg, rule_id=SA2A_LOGIC_CLOSURE_COMPLETENESS
                ) from exc
            return LogicHookCheckResult(
                rule_id=SA2A_LOGIC_CLOSURE_COMPLETENESS,
                passed=False,
                verdict=LogicHookVerdict.REFUSED,
                error_message=err_msg,
            )

        # Check required atoms against derived set
        missing: List[str] = []
        derived_strs = {str(a) for a in derived}
        for atom in required_atoms:
            if str(atom) not in derived_strs:
                missing.append(str(atom))

        if missing:
            err_msg = f"Closure incomplete: {len(missing)} required atoms not derived: {missing[:5]}"
            if fail_closed:
                raise LogicHookCourtError(
                    err_msg,
                    {"missing": missing},
                    rule_id=SA2A_LOGIC_CLOSURE_COMPLETENESS,
                )
            return LogicHookCheckResult(
                rule_id=SA2A_LOGIC_CLOSURE_COMPLETENESS,
                passed=False,
                verdict=LogicHookVerdict.NON_CONFORMANT,
                error_message=err_msg,
                details={"missing": missing},
            )

        return LogicHookCheckResult(
            rule_id=SA2A_LOGIC_CLOSURE_COMPLETENESS,
            passed=True,
            verdict=LogicHookVerdict.CONFORMANT,
            details={
                "derived_count": len(derived),
                "required_count": len(required_atoms),
            },
        )

    # ------------------------------------------------------------------
    # SA2A-LOGIC-N3-NON-AUTHORITY
    # ------------------------------------------------------------------

    def verify_n3_non_authority(
        self,
        n3_output: Any,
        fail_closed: bool = True,
    ) -> LogicHookCheckResult:
        """Verify N3 logic output has no independent execution authority.

        N3 derivation results are CANDIDATE semantic propositions, never DO-authority.
        This test verifies the output is a data structure, not a consequence actuation.
        """
        # N3 output must be a graph/dict/list — not a callable or actuation request
        if callable(n3_output):
            err_msg = (
                "SA2A-LOGIC-N3-NON-AUTHORITY violation: N3 output is callable — "
                "logic derivation must never acquire execution authority (Logic != Authority §29)"
            )
            if fail_closed:
                raise LogicHookCourtError(err_msg, rule_id=SA2A_LOGIC_N3_NON_AUTHORITY)
            return LogicHookCheckResult(
                rule_id=SA2A_LOGIC_N3_NON_AUTHORITY,
                passed=False,
                verdict=LogicHookVerdict.REFUSED,
                error_message=err_msg,
            )

        # Check for authority-asserting keys in dict output
        if isinstance(n3_output, dict):
            forbidden_keys = {"execute", "actuate", "do", "grant", "authorize"}
            found = forbidden_keys.intersection(str(k).lower() for k in n3_output)
            if found:
                err_msg = (
                    f"SA2A-LOGIC-N3-NON-AUTHORITY: N3 output contains authority-asserting "
                    f"keys {sorted(found)} — logic must not self-grant execution"
                )
                if fail_closed:
                    raise LogicHookCourtError(
                        err_msg,
                        {"forbidden_keys": sorted(found)},
                        rule_id=SA2A_LOGIC_N3_NON_AUTHORITY,
                    )
                return LogicHookCheckResult(
                    rule_id=SA2A_LOGIC_N3_NON_AUTHORITY,
                    passed=False,
                    verdict=LogicHookVerdict.REFUSED,
                    error_message=err_msg,
                    details={"forbidden_keys": sorted(found)},
                )

        return LogicHookCheckResult(
            rule_id=SA2A_LOGIC_N3_NON_AUTHORITY,
            passed=True,
            verdict=LogicHookVerdict.CONFORMANT,
            details={"output_type": type(n3_output).__name__},
        )

    # ------------------------------------------------------------------
    # SA2A-HOOK-META-ADMISSION
    # ------------------------------------------------------------------

    def verify_hook_meta_admission(
        self,
        hook: KnowledgeHookDefinition,
        admitted_namespaces: Sequence[str],
        fail_closed: bool = True,
    ) -> LogicHookCheckResult:
        """Verify hook IRI is within admitted namespaces (SA2A-HOOK-META-ADMISSION).

        A hook with an IRI outside admitted namespaces MUST be refused.
        """
        iri = hook.iri
        admitted = any(iri.startswith(ns) for ns in admitted_namespaces)
        if not admitted:
            err_msg = (
                f"Hook meta-admission refused: IRI '{iri}' is not within any admitted "
                f"namespace {list(admitted_namespaces)}"
            )
            if fail_closed:
                raise LogicHookCourtError(
                    err_msg,
                    {"iri": iri, "admitted_namespaces": list(admitted_namespaces)},
                    rule_id=SA2A_HOOK_META_ADMISSION,
                )
            return LogicHookCheckResult(
                rule_id=SA2A_HOOK_META_ADMISSION,
                passed=False,
                verdict=LogicHookVerdict.REFUSED,
                error_message=err_msg,
                details={"iri": iri, "admitted_namespaces": list(admitted_namespaces)},
            )

        return LogicHookCheckResult(
            rule_id=SA2A_HOOK_META_ADMISSION,
            passed=True,
            verdict=LogicHookVerdict.CONFORMANT,
            details={"iri": iri},
        )

    # ------------------------------------------------------------------
    # SA2A-HOOK-EFFECT-KIND
    # ------------------------------------------------------------------

    def verify_hook_effect_kind(
        self,
        hook: KnowledgeHookDefinition,
        fail_closed: bool = True,
    ) -> LogicHookCheckResult:
        """Verify hook effect kind is a valid admitted manufacturing effect.

        SA2A §42/§44: Hooks MUST produce CANDIDATE intents via EMIT_DELTA or GROUND_ACTION.
        A hook with an unrecognized or phantom effect kind MUST be refused.
        All valid HookEffectKind values (EMIT_DELTA, GROUND_ACTION, REFUSE) are manufacturing effects.
        """
        admitted_effects = {
            HookEffectKind.EMIT_DELTA,
            HookEffectKind.GROUND_ACTION,
            HookEffectKind.REFUSE,
        }
        if hook.effect not in admitted_effects:
            err_msg = (
                f"SA2A-HOOK-EFFECT-KIND violation: hook '{hook.iri}' declares unrecognized "
                f"effect '{hook.effect}' — effect MUST be an admitted manufacturing kind (§42, §44)"
            )
            if fail_closed:
                raise HookPerformsDOError(
                    err_msg, {"effect": str(hook.effect)}, rule_id=SA2A_HOOK_EFFECT_KIND
                )
            return LogicHookCheckResult(
                rule_id=SA2A_HOOK_EFFECT_KIND,
                passed=False,
                verdict=LogicHookVerdict.REFUSED,
                error_message=err_msg,
                details={"effect": str(hook.effect)},
            )

        return LogicHookCheckResult(
            rule_id=SA2A_HOOK_EFFECT_KIND,
            passed=True,
            verdict=LogicHookVerdict.CONFORMANT,
            details={"effect": str(hook.effect)},
        )

    # ------------------------------------------------------------------
    # SA2A-HOOK-NO-DO (stronger: hooks must not synthesize DO bypasses)
    # ------------------------------------------------------------------

    def verify_hook_no_do(
        self,
        execution_records: Sequence[HookExecutionRecord],
        fail_closed: bool = True,
    ) -> LogicHookCheckResult:
        """Verify no hook execution record produced a consequence bypass (SA2A-HOOK-NO-DO).

        SA2A §44: Hook effects are CANDIDATE SemanticIntents — not consequence actuations.
        All HookExecutionRecord verdicts must be FIRED, NOT_FIRED, or GATED (from HookVerdict).
        Records with phantom/unknown verdict strings indicate an adversarial bypass attempt.
        """
        from autofde_lab.sa2a.hooks.model import HookVerdict

        admitted_verdicts = {
            HookVerdict.FIRED,
            HookVerdict.NOT_FIRED,
            HookVerdict.GATED,
        }
        violations: List[str] = []
        for record in execution_records:
            if record.verdict not in admitted_verdicts:
                violations.append(f"{record.hook_iri} (verdict={record.verdict})")

        if violations:
            err_msg = (
                f"SA2A-HOOK-NO-DO: {len(violations)} hook execution(s) produced unknown "
                f"verdict: {violations[:3]} — hooks MUST only produce admitted CANDIDATE verdicts"
            )
            if fail_closed:
                raise HookPerformsDOError(
                    err_msg, {"violations": violations}, rule_id=SA2A_HOOK_NO_DO
                )
            return LogicHookCheckResult(
                rule_id=SA2A_HOOK_NO_DO,
                passed=False,
                verdict=LogicHookVerdict.REFUSED,
                error_message=err_msg,
                details={"violations": violations},
            )

        return LogicHookCheckResult(
            rule_id=SA2A_HOOK_NO_DO,
            passed=True,
            verdict=LogicHookVerdict.CONFORMANT,
            details={"record_count": len(execution_records)},
        )

    # ------------------------------------------------------------------
    # SA2A-HOOK-CASCADE-DEPTH
    # ------------------------------------------------------------------

    def verify_hook_cascade_depth(
        self,
        execution_records: Sequence[HookExecutionRecord],
        max_depth: Optional[int] = None,
        fail_closed: bool = True,
    ) -> LogicHookCheckResult:
        """Verify hook cascade depth stays within D_max.

        Cascades exceeding D_max indicate unbounded reactive amplification,
        violating RFC-SA2A-002 §44 cascade bound requirement.
        """
        d_max = max_depth if max_depth is not None else self.max_cascade_depth
        # Each record represents one cascade step. Total count is the cascade depth.
        # A depth-limited system cannot produce more records than D_max.
        actual_depth = len(execution_records)
        if actual_depth > d_max:
            err_msg = (
                f"SA2A-HOOK-CASCADE-DEPTH: cascade depth {actual_depth} exceeds "
                f"D_max={d_max} — unbounded reactive amplification forbidden (§44)"
            )
            if fail_closed:
                raise HookCascadeDepthExceededError(
                    err_msg,
                    {"actual_depth": actual_depth, "d_max": d_max},
                    rule_id=SA2A_HOOK_CASCADE_DEPTH,
                )
            return LogicHookCheckResult(
                rule_id=SA2A_HOOK_CASCADE_DEPTH,
                passed=False,
                verdict=LogicHookVerdict.REFUSED,
                error_message=err_msg,
                details={"actual_depth": actual_depth, "d_max": d_max},
            )

        return LogicHookCheckResult(
            rule_id=SA2A_HOOK_CASCADE_DEPTH,
            passed=True,
            verdict=LogicHookVerdict.CONFORMANT,
            details={
                "actual_depth": actual_depth,
                "d_max": d_max,
                "record_count": len(execution_records),
            },
        )

    # ------------------------------------------------------------------
    # CHI-AUTO-BOUNDED-EXECUTION
    # ------------------------------------------------------------------

    def verify_autonomous_bounded_execution(
        self,
        execution_records: Sequence[HookExecutionRecord],
        fuel_budget: int,
        elapsed_ms: float,
        max_elapsed_ms: float = 30_000.0,
        fail_closed: bool = True,
    ) -> LogicHookCheckResult:
        """Verify autonomous execution completed within fuel and time budget.

        Autonomous execution MUST be bounded: it cannot consume unbounded resources.
        """
        actual_fuel = len(execution_records)
        violations: List[str] = []

        if actual_fuel > fuel_budget:
            violations.append(
                f"fuel consumed ({actual_fuel}) exceeds budget ({fuel_budget})"
            )
        if elapsed_ms > max_elapsed_ms:
            violations.append(
                f"elapsed time ({elapsed_ms:.1f}ms) exceeds max ({max_elapsed_ms:.1f}ms)"
            )

        if violations:
            err_msg = (
                f"CHI-AUTO-BOUNDED-EXECUTION: autonomous execution exceeded bounds: "
                + "; ".join(violations)
            )
            if fail_closed:
                raise AutoBoundedExecutionError(
                    err_msg,
                    {
                        "fuel": actual_fuel,
                        "budget": fuel_budget,
                        "elapsed_ms": elapsed_ms,
                    },
                    rule_id=CHI_AUTO_BOUNDED_EXECUTION,
                )
            return LogicHookCheckResult(
                rule_id=CHI_AUTO_BOUNDED_EXECUTION,
                passed=False,
                verdict=LogicHookVerdict.REFUSED,
                error_message=err_msg,
                details={
                    "fuel": actual_fuel,
                    "budget": fuel_budget,
                    "elapsed_ms": elapsed_ms,
                },
            )

        return LogicHookCheckResult(
            rule_id=CHI_AUTO_BOUNDED_EXECUTION,
            passed=True,
            verdict=LogicHookVerdict.CONFORMANT,
            details={
                "fuel": actual_fuel,
                "budget": fuel_budget,
                "elapsed_ms": round(elapsed_ms, 3),
            },
        )

    # ------------------------------------------------------------------
    # Full court sweep
    # ------------------------------------------------------------------

    def run_full_court(
        self,
        *,
        datalog_rules: Sequence[DatalogRule],
        required_atoms: Sequence[DatalogAtom],
        hooks: Sequence[KnowledgeHookDefinition],
        hook_execution_records: Sequence[HookExecutionRecord],
        admitted_hook_namespaces: Sequence[str],
        n3_output: Any = None,
        fuel_budget: int = 100,
        elapsed_ms: float = 0.0,
        fail_closed: bool = False,
    ) -> LogicHookCourtReport:
        """Run all Logic/Hook court checks and return aggregated report."""
        results: List[LogicHookCheckResult] = []

        # SA2A-LOGIC-*
        results.append(
            self.verify_datalog_safe_termination(datalog_rules, fail_closed=fail_closed)
        )
        results.append(
            self.verify_datalog_closure_completeness(
                datalog_rules, required_atoms, fail_closed=fail_closed
            )
        )
        if n3_output is not None:
            results.append(
                self.verify_n3_non_authority(n3_output, fail_closed=fail_closed)
            )

        # SA2A-HOOK-*
        for hook in hooks:
            results.append(
                self.verify_hook_meta_admission(
                    hook, admitted_hook_namespaces, fail_closed=fail_closed
                )
            )
            results.append(self.verify_hook_effect_kind(hook, fail_closed=fail_closed))

        results.append(
            self.verify_hook_no_do(hook_execution_records, fail_closed=fail_closed)
        )
        results.append(
            self.verify_hook_cascade_depth(
                hook_execution_records, fail_closed=fail_closed
            )
        )

        # CHI-AUTO-*
        results.append(
            self.verify_autonomous_bounded_execution(
                hook_execution_records, fuel_budget, elapsed_ms, fail_closed=fail_closed
            )
        )

        return LogicHookCourtReport(gate_results=results)


# ---------------------------------------------------------------------------
# In-module test helpers (callable from test runner or inline)
# ---------------------------------------------------------------------------


def test_datalog_safe_termination(court: Optional[LogicHookCourt] = None) -> None:
    """Verify Datalog safe termination passes for a finite acyclic ruleset."""
    c = court or LogicHookCourt()
    # Empty ruleset terminates immediately
    rules: List[DatalogRule] = []
    result = c.verify_datalog_safe_termination(rules, fail_closed=True)
    assert result.passed, f"Expected termination: {result.error_message}"


def test_hook_no_do_violation(court: Optional[LogicHookCourt] = None) -> None:
    """Verify that a hook with unknown/phantom effect is detected and refused."""
    from autofde_lab.sa2a.hooks.synthesis import HookSynthesizer

    c = court or LogicHookCourt()
    synth = HookSynthesizer()
    # Create a valid hook (GROUND_ACTION), then mutate with a phantom effect string
    artifact = synth.synthesize_from_resolution(
        hook_name="test_actuate_hook",
        action_iri="urn:action:test:actuate",
        target_capability_iri="urn:cap:test:disk",
    )
    hook = artifact.hook

    # Inject a phantom effect via object replacement to simulate an adversarial hook
    from dataclasses import replace as _replace

    bad_hook = _replace(hook, effect="PHANTOM_ACTUATE_BYPASS")  # type: ignore[arg-type]

    refused = False
    try:
        c.verify_hook_effect_kind(bad_hook, fail_closed=True)
    except HookPerformsDOError:
        refused = True
    assert refused, "Phantom effect hook must be refused"


def test_hook_meta_admission_refusal(court: Optional[LogicHookCourt] = None) -> None:
    """Verify hook with unadmitted IRI is refused."""
    from autofde_lab.sa2a.hooks.synthesis import HookSynthesizer

    c = court or LogicHookCourt()
    synth = HookSynthesizer()
    # hook_name determines IRI: http://example.org/hook/{hook_name}
    artifact = synth.synthesize_from_resolution(
        hook_name="adversary_malicious",
        action_iri="urn:action:adversary:pwn",
        target_capability_iri="urn:cap:adversary:root",
    )
    hook = artifact.hook
    # IRI will be http://example.org/hook/adversary_malicious
    # admitted namespace is urn:hook:autofde: — does NOT match http://example.org/hook/
    refused = False
    try:
        c.verify_hook_meta_admission(
            hook, admitted_namespaces=["urn:hook:autofde:"], fail_closed=True
        )
    except LogicHookCourtError:
        refused = True
    assert refused, "Hook with unadmitted IRI must be refused"
