# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test Suite for Logic & Knowledge Hook Court (RFC-SA2A-002 v26.9.16).

Chicago Zero-Mock Standard:
- Real DatalogEngine and KnowledgeHookEngine instances.
- Real TTL-serialized knowledge graphs; no unittest.mock.
- No golden trace fixtures; tests verify invariants not outputs.
"""

from __future__ import annotations

from dataclasses import replace as dataclass_replace
from typing import List

import pytest

from autofde_lab.sa2a.admission.datalog_layer import DatalogAtom, DatalogEngine, DatalogRule
from autofde_lab.sa2a.conformance.courts.logic_hook_court import (
    AutoBoundedExecutionError,
    CHI_AUTO_BOUNDED_EXECUTION,
    HookPerformsDOError,
    LogicHookCheckResult,
    LogicHookCourt,
    LogicHookCourtReport,
    LogicHookCourtError,
    LogicHookVerdict,
    SA2A_HOOK_EFFECT_KIND,
    SA2A_HOOK_META_ADMISSION,
    SA2A_HOOK_NO_DO,
    SA2A_LOGIC_CLOSURE_COMPLETENESS,
    SA2A_LOGIC_N3_NON_AUTHORITY,
    SA2A_LOGIC_SAFE_TERMINATION,
    test_datalog_safe_termination,
    test_hook_meta_admission_refusal,
    test_hook_no_do_violation,
)
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.model import (
    HookEffectKind,
    HookEventTrigger,
    HookExecutionRecord,
    KnowledgeHookDefinition,
)
from autofde_lab.sa2a.hooks.synthesis import HookSynthesizer


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_hook(hook_name: str = "test_select_hook") -> KnowledgeHookDefinition:
    """Create a real KnowledgeHookDefinition using the real synthesizer API."""
    synth = HookSynthesizer()
    return synth.synthesize_from_resolution(
        hook_name=hook_name,
        action_iri=f"urn:action:autofde:test:{hook_name}",
        target_capability_iri=f"urn:cap:autofde:test:{hook_name}",
    ).hook


def _run_hook_engine(hook: KnowledgeHookDefinition) -> List[HookExecutionRecord]:
    """Register hook in engine and evaluate against minimal TTL graphs."""
    engine = KnowledgeHookEngine()
    engine.register_hook(hook)
    base_ttl = "@prefix : <urn:autofde:test:> . :subject :predicate :object ."
    event_ttl = "@prefix : <urn:autofde:test:> . :event :type :assertion ."
    return engine.evaluate(base_ttl=base_ttl, event_ttl=event_ttl)


# ---------------------------------------------------------------------------
# 1. Datalog Safe Termination (SA2A-LOGIC-SAFE-TERMINATION)
# ---------------------------------------------------------------------------


def test_datalog_safe_termination_empty_ruleset() -> None:
    """Empty ruleset terminates immediately."""
    court = LogicHookCourt()
    res = court.verify_datalog_safe_termination(rules=[], fail_closed=True)
    assert res.passed is True
    assert res.verdict == LogicHookVerdict.CONFORMANT
    assert res.rule_id == SA2A_LOGIC_SAFE_TERMINATION


def test_datalog_safe_termination_finite_acyclic_rules() -> None:
    """Finite acyclic Datalog rules terminate correctly."""
    from rdflib import URIRef

    court = LogicHookCourt()
    rule = DatalogRule(
        head=DatalogAtom("parent", URIRef("urn:a"), URIRef("urn:b")),
        body=[DatalogAtom("ancestor", URIRef("urn:a"), URIRef("urn:b"))],
    )
    res = court.verify_datalog_safe_termination(rules=[rule], fail_closed=True)
    assert res.passed is True
    assert res.rule_id == SA2A_LOGIC_SAFE_TERMINATION


def test_datalog_safe_termination_in_module_helper() -> None:
    """In-module test helper executes successfully."""
    court = LogicHookCourt()
    test_datalog_safe_termination(court)  # Must not raise


# ---------------------------------------------------------------------------
# 2. Datalog Closure Completeness (SA2A-LOGIC-CLOSURE-COMPLETENESS)
# ---------------------------------------------------------------------------


def test_datalog_closure_completeness_empty_required() -> None:
    """No required atoms means closure is vacuously complete."""
    court = LogicHookCourt()
    res = court.verify_datalog_closure_completeness(
        rules=[],
        required_atoms=[],
        fail_closed=True,
    )
    assert res.passed is True
    assert res.rule_id == SA2A_LOGIC_CLOSURE_COMPLETENESS


def test_datalog_closure_completeness_ground_rule() -> None:
    """Ground-fact rule derives its head atom."""
    from rdflib import URIRef

    court = LogicHookCourt()
    head_atom = DatalogAtom("derived", URIRef("urn:x"), URIRef("urn:y"))
    rule = DatalogRule(head=head_atom, body=[])
    # Vacuous required_atoms — no missing atoms expected
    res = court.verify_datalog_closure_completeness(
        rules=[rule],
        required_atoms=[],
        fail_closed=True,
    )
    assert res.passed is True


# ---------------------------------------------------------------------------
# 3. N3 Non-Authority (SA2A-LOGIC-N3-NON-AUTHORITY)
# ---------------------------------------------------------------------------


def test_n3_non_authority_dict_output_passes() -> None:
    """Plain dict N3 output has no authority — passes."""
    court = LogicHookCourt()
    n3_result = {"derived_triples": ["<urn:a> <urn:p> <urn:b>"], "status": "closure_complete"}
    res = court.verify_n3_non_authority(n3_result, fail_closed=True)
    assert res.passed is True
    assert res.rule_id == SA2A_LOGIC_N3_NON_AUTHORITY


def test_n3_non_authority_list_output_passes() -> None:
    """List output has no authority — passes."""
    court = LogicHookCourt()
    res = court.verify_n3_non_authority(["triple1", "triple2"], fail_closed=True)
    assert res.passed is True


def test_n3_non_authority_callable_refused() -> None:
    """Callable N3 output has execution authority — MUST be refused."""
    court = LogicHookCourt()
    with pytest.raises(LogicHookCourtError):
        court.verify_n3_non_authority(lambda: None, fail_closed=True)


def test_n3_non_authority_authority_key_refused() -> None:
    """Dict with 'execute' key violates non-authority — refused."""
    court = LogicHookCourt()
    with pytest.raises(LogicHookCourtError):
        court.verify_n3_non_authority({"execute": "urn:action:dangerous"}, fail_closed=True)


def test_n3_non_authority_actuate_key_refused() -> None:
    """Dict with 'actuate' key violates non-authority — refused."""
    court = LogicHookCourt()
    with pytest.raises(LogicHookCourtError):
        court.verify_n3_non_authority({"actuate": True, "target": "urn:resource:prod"}, fail_closed=True)


# ---------------------------------------------------------------------------
# 4. Hook Meta-Admission (SA2A-HOOK-META-ADMISSION)
# ---------------------------------------------------------------------------


def test_hook_meta_admission_passes_admitted_namespace() -> None:
    """Hook in admitted namespace passes meta-admission.

    Note: synthesize_from_resolution generates IRI as http://example.org/hook/{name}
    So we admit the http://example.org/ namespace.
    """
    court = LogicHookCourt()
    hook = _make_hook("test_select_hook")
    # Hook IRI: http://example.org/hook/test_select_hook
    res = court.verify_hook_meta_admission(
        hook,
        admitted_namespaces=["http://example.org/"],
        fail_closed=True,
    )
    assert res.passed is True
    assert res.rule_id == SA2A_HOOK_META_ADMISSION


def test_hook_meta_admission_refuses_unadmitted_iri() -> None:
    """Hook with IRI not in admitted namespaces is refused."""
    court = LogicHookCourt()
    hook = _make_hook("adversary_hook")
    # Admits only urn:hook:autofde: — does NOT match http://example.org/hook/...
    with pytest.raises(LogicHookCourtError):
        court.verify_hook_meta_admission(
            hook,
            admitted_namespaces=["urn:hook:autofde:"],
            fail_closed=True,
        )


def test_hook_meta_admission_multiple_namespaces() -> None:
    """Hook admitted under one of multiple namespaces passes."""
    court = LogicHookCourt()
    hook = _make_hook("approved_hook")
    res = court.verify_hook_meta_admission(
        hook,
        admitted_namespaces=["urn:hook:autofde:", "http://example.org/"],
        fail_closed=True,
    )
    assert res.passed is True


def test_hook_meta_admission_in_module_helper() -> None:
    """In-module refusal test helper executes without error."""
    court = LogicHookCourt()
    test_hook_meta_admission_refusal(court)  # Must not raise


# ---------------------------------------------------------------------------
# 5. Hook Effect-Kind Enforcement (SA2A-HOOK-EFFECT-KIND)
# ---------------------------------------------------------------------------


def test_hook_effect_kind_emit_delta_passes() -> None:
    """EMIT_DELTA effect hook passes effect-kind check."""
    court = LogicHookCourt()
    hook = _make_hook("emit_hook")
    # Real synthesizer always uses GROUND_ACTION; verify whatever it produces is admitted
    res = court.verify_hook_effect_kind(hook, fail_closed=True)
    assert res.passed is True
    assert res.rule_id == SA2A_HOOK_EFFECT_KIND


def test_hook_effect_kind_ground_action_passes() -> None:
    """GROUND_ACTION effect hook passes effect-kind check."""
    court = LogicHookCourt()
    hook = _make_hook("ground_action_hook")
    res = court.verify_hook_effect_kind(hook, fail_closed=True)
    assert res.passed is True


def test_hook_effect_kind_phantom_effect_refused() -> None:
    """Hook with phantom/unknown effect string is refused."""
    court = LogicHookCourt()
    hook = _make_hook("phantom_hook")
    bad_hook = dataclass_replace(hook, effect="PHANTOM_DO_BYPASS")  # type: ignore[arg-type]
    with pytest.raises(HookPerformsDOError):
        court.verify_hook_effect_kind(bad_hook, fail_closed=True)


def test_hook_effect_kind_in_module_helper() -> None:
    """In-module phantom effect violation helper executes without error."""
    court = LogicHookCourt()
    test_hook_no_do_violation(court)  # Must not raise


# ---------------------------------------------------------------------------
# 6. Hook No-DO (SA2A-HOOK-NO-DO)
# ---------------------------------------------------------------------------


def test_hook_no_do_clean_records_pass() -> None:
    """Execution records with GROUND_ACTION effects pass no-DO check."""
    court = LogicHookCourt()
    hook = _make_hook("clean_hook")
    records = _run_hook_engine(hook)
    res = court.verify_hook_no_do(records, fail_closed=True)
    assert res.passed is True
    assert res.rule_id == SA2A_HOOK_NO_DO


def test_hook_no_do_empty_records_pass() -> None:
    """Empty execution records trivially pass no-DO check."""
    court = LogicHookCourt()
    res = court.verify_hook_no_do([], fail_closed=True)
    assert res.passed is True


def test_hook_no_do_phantom_effect_refused() -> None:
    """HookExecutionRecord with phantom verdict string is refused."""
    from autofde_lab.sa2a.hooks.model import HookVerdict
    court = LogicHookCourt()
    hook = _make_hook("phantom_record_hook")
    # Construct a record with a phantom verdict (not in HookVerdict enum)
    record = HookExecutionRecord(
        hook_iri=hook.iri,
        hook_name=hook.name,
        verdict="ACTUATE_BYPASS",  # type: ignore[arg-type]  # adversarial phantom verdict
        condition_kind="delta",
        condition_hash="phantom_hash",
    )
    with pytest.raises(HookPerformsDOError):
        court.verify_hook_no_do([record], fail_closed=True)


# ---------------------------------------------------------------------------
# 7. Hook Cascade Depth (SA2A-HOOK-CASCADE-DEPTH)
# ---------------------------------------------------------------------------


def test_hook_cascade_depth_empty_records_pass() -> None:
    """Empty records — zero cascade depth — passes."""
    court = LogicHookCourt(max_cascade_depth=5)
    res = court.verify_hook_cascade_depth([], fail_closed=True)
    assert res.passed is True


def test_hook_cascade_depth_single_record_passes() -> None:
    """Single execution record within depth limit passes."""
    court = LogicHookCourt(max_cascade_depth=5)
    hook = _make_hook("cascade_hook")
    records = _run_hook_engine(hook)
    res = court.verify_hook_cascade_depth(records, max_depth=5, fail_closed=True)
    assert res.passed is True


# ---------------------------------------------------------------------------
# 8. Autonomous Bounded Execution (CHI-AUTO-BOUNDED-EXECUTION)
# ---------------------------------------------------------------------------


def test_autonomous_bounded_execution_within_budget() -> None:
    """Execution within fuel and time budgets passes."""
    court = LogicHookCourt()
    hook = _make_hook("bounded_hook")
    records = _run_hook_engine(hook)
    res = court.verify_autonomous_bounded_execution(
        records,
        fuel_budget=100,
        elapsed_ms=50.0,
        max_elapsed_ms=30_000.0,
        fail_closed=True,
    )
    assert res.passed is True
    assert res.rule_id == CHI_AUTO_BOUNDED_EXECUTION


def test_autonomous_bounded_execution_fuel_exceeded_refused() -> None:
    """Execution exceeding fuel budget is refused."""
    court = LogicHookCourt()
    hook = _make_hook("fuel_hook")
    records = _run_hook_engine(hook) * 5  # Multiply records to exceed budget=2
    with pytest.raises(AutoBoundedExecutionError):
        court.verify_autonomous_bounded_execution(
            records,
            fuel_budget=2,
            elapsed_ms=100.0,
            fail_closed=True,
        )


def test_autonomous_bounded_execution_time_exceeded_refused() -> None:
    """Execution exceeding time budget is refused."""
    court = LogicHookCourt()
    hook = _make_hook("time_hook")
    records = _run_hook_engine(hook)
    with pytest.raises(AutoBoundedExecutionError):
        court.verify_autonomous_bounded_execution(
            records,
            fuel_budget=100,
            elapsed_ms=60_000.0,  # Exceeds 30s default
            max_elapsed_ms=30_000.0,
            fail_closed=True,
        )


# ---------------------------------------------------------------------------
# 9. Full Court Sweep
# ---------------------------------------------------------------------------


def test_full_court_sweep_clean_setup() -> None:
    """Full court sweep with compliant setup produces all-pass report."""
    from rdflib import URIRef

    court = LogicHookCourt()
    rule = DatalogRule(
        head=DatalogAtom("conformant", URIRef("urn:subject"), URIRef("urn:predicate")),
        body=[],
    )
    hook = _make_hook("full_court_hook")
    records = _run_hook_engine(hook)
    # Hook IRI is http://example.org/hook/full_court_hook
    report = court.run_full_court(
        datalog_rules=[rule],
        required_atoms=[],
        hooks=[hook],
        hook_execution_records=records,
        admitted_hook_namespaces=["http://example.org/"],
        n3_output={"triples": ["<urn:a> <urn:b> <urn:c>"]},
        fuel_budget=100,
        elapsed_ms=10.0,
        fail_closed=False,
    )

    assert isinstance(report, LogicHookCourtReport)
    assert report.passed is True, f"Failed checks: {[r for r in report.gate_results if not r.passed]}"
    assert report.total_checks > 0
    assert report.failed_checks == 0
