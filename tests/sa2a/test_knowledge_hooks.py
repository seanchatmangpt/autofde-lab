"""Tests for Knowledge Hooks subsystem and reactive semantic network in AutoFDE-Lab."""

from __future__ import annotations


from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import (
    ConsequenceBoundary,
)
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.model import (
    HookEffectKind,
    HookEventTrigger,
    HookVerdict,
    KnowledgeHookDefinition,
    SemanticIntent,
)
from autofde_lab.sa2a.hooks.reactive_loop import ReactiveSemanticLoop


class DummyActuator:
    def actuate(self, action_iri, target_resource, parameters):
        return {"effect_applied": True, "action": action_iri, "ts": 123456789}

    def actuator_digest(self):
        return "actuator:dummy:v1"


class DummyVerifier:
    def verify_postcondition(self, action_iri, target_resource, parameters, evidence):
        return evidence is not None and evidence.get("effect_applied") is True

    def verifier_digest(self):
        return "verifier:dummy:v1"


def test_knowledge_hook_definition_turtle_serialization():
    hook = KnowledgeHookDefinition(
        iri="http://example.org/hook/overdue_payment",
        name="overdue_payment_hook",
        on=HookEventTrigger.ASSERT,
        condition_kind="delta",
        effect=HookEffectKind.GROUND_ACTION,
        action_iri="http://example.org/action/freeze_account",
        target_capability_iri="urn:cap:billing:freeze",
        goal_iri="urn:goal:account_secured",
        reason="Invoice is overdue by 30 days",
        priority=10,
    )
    ttl = hook.to_turtle()
    assert "a kh:Hook ;" in ttl
    assert 'kh:name "overdue_payment_hook" ;' in ttl
    assert 'kh:on "assert" ;' in ttl
    assert "kh:action <http://example.org/action/freeze_account> ;" in ttl
    assert 'kh:goal "urn:goal:account_secured" ;' in ttl


def test_hook_engine_intent_synthesis_without_do():
    """Verify Hook -> Intent: hook produces intent, but DOES NOT execute DO."""
    engine = KnowledgeHookEngine()
    hook = KnowledgeHookDefinition(
        iri="http://example.org/hook/h1",
        name="invoice_overdue_hook",
        on=HookEventTrigger.ASSERT,
        effect=HookEffectKind.GROUND_ACTION,
        action_iri="urn:action:freeze_credit",
        target_capability_iri="urn:cap:credit:freeze",
        goal_iri="urn:goal:risk_mitigation",
    )
    engine.register_hook(hook)

    base_ttl = "@prefix ex: <http://example.org/> . ex:acc ex:balance '100' ."
    event_ttl = "@prefix ex: <http://example.org/> . ex:acc ex:status 'OVERDUE' ."

    records = engine.evaluate(base_ttl, event_ttl, parameters={"account_id": "acc-99"})
    assert len(records) == 1
    rec = records[0]

    assert rec.verdict == HookVerdict.FIRED
    assert rec.intent is not None
    assert isinstance(rec.intent, SemanticIntent)
    assert rec.intent.action_iri == "urn:action:freeze_credit"
    assert rec.intent.parameters["account_id"] == "acc-99"
    assert len(rec.intent.intent_digest) == 64


def test_reactive_semantic_loop_closed_reflex_cycle():
    """Verify the full autonomic reflex loop:
    Delta -> Hook 1 -> Intent 1 -> Authority -> BRCE DO -> Receipt 1 -> Delta 2 -> Quiescence.
    """
    hook_engine = KnowledgeHookEngine()
    hook = KnowledgeHookDefinition(
        iri="http://example.org/hook/h1",
        name="overdue_handler",
        on=HookEventTrigger.ASSERT,
        effect=HookEffectKind.GROUND_ACTION,
        action_iri="urn:action:freeze_credit",
        target_capability_iri="urn:cap:credit:freeze",
        goal_iri="urn:goal:risk_mitigation",
    )
    hook_engine.register_hook(hook)

    # Authority Broker grants authority for this action
    authority_broker = AuthorityBroker()
    grant = AuthorityGrant(
        grant_id="grant-autonomic-001",
        subject_id="urn:agent:autonomic-controller",
        action_iri="urn:action:freeze_credit",
        target_resource_iri="urn:cap:credit:freeze",
    )
    authority_broker.register_grant(grant)

    actuator = DummyActuator()
    verifier = DummyVerifier()
    boundary = ConsequenceBoundary(
        authority_broker=authority_broker,
        actuator=actuator,
        verifier=verifier,
    )

    loop = ReactiveSemanticLoop(
        hook_engine=hook_engine,
        authority_broker=authority_broker,
        consequence_boundary=boundary,
        max_cascade_depth=3,
    )

    base_ttl = "@prefix ex: <http://example.org/> . ex:acc ex:status 'ACTIVE' ."
    # AFDE-2604 fail-secure closure (this session): `ReactiveSemanticLoop`, when
    # constructed without an explicit `admission_pipeline` (as here), now builds a
    # real `AdmissionPipeline()` by default and admits `current_event` (this
    # `initial_event_ttl` on cycle 1) before any intent synthesized from it may
    # reach `AuthorityBroker.evaluate()`. Admission is incidental to what this test
    # actually verifies (the full Delta -> Hook -> Intent -> Authority -> BRCE DO ->
    # Receipt -> Quiescence reflex cycle), so the fix is to make the event content
    # independently reach `Standing.ADMITTED` AND explicitly bind this hook's own
    # `action_iri`/`target_capability_iri` (`urn:action:freeze_credit` /
    # `urn:cap:credit:freeze`) via the real `afl:targetResource`
    # (`urn:autofde-lab:targetResource`) predicate `ConsequenceBoundary`'s own
    # `_admission_covers_action_target()` gate requires -- the same real
    # content-binding pattern already used by this file's
    # `test_sa2a_cli_hook_evaluate_and_reflex` (see its `res_reflex` case). This is
    # not a test weakening: it demonstrates the new secure default's legitimate
    # happy path (real admission wired in), not a bypass of it.
    initial_event_ttl = (
        "@prefix ex: <http://example.org/> . ex:acc ex:status 'OVERDUE' . "
        "<urn:action:freeze_credit> <urn:autofde-lab:targetResource> "
        "<urn:cap:credit:freeze> ."
    )

    # Custom delta generator to stop loop on second cycle
    def delta_gen(final_receipt):
        return ""  # Empty delta causes next cycle to achieve quiescence

    trace = loop.run_reflex_cycle(
        base_ttl,
        initial_event_ttl,
        actor_id="urn:agent:autonomic-controller",
        delta_generator=delta_gen,
    )

    assert len(trace.steps) == 1
    step1 = trace.steps[0]
    assert "overdue_handler" in step1.triggered_hooks
    assert len(step1.intents_synthesized) == 1
    assert step1.intents_synthesized[0].action_iri == "urn:action:freeze_credit"
    assert len(step1.final_receipts) == 1
    assert step1.final_receipts[0].state == TerminalReceiptState.EXECUTED
    assert trace.quiescence_reached is True


def test_multi_step_cascade_reflex_bounded():
    """Verify multi-step autonomic cascades terminate deterministically when reaching bound."""
    hook_engine = KnowledgeHookEngine()
    hook = KnowledgeHookDefinition(
        iri="http://example.org/hook/cascader",
        name="cascade_hook",
        on=HookEventTrigger.ASSERT,
        effect=HookEffectKind.GROUND_ACTION,
        action_iri="urn:action:cascade_step",
        target_capability_iri="urn:cap:cascade",
        goal_iri="urn:goal:cascade",
    )
    hook_engine.register_hook(hook)

    authority_broker = AuthorityBroker()
    grant = AuthorityGrant(
        grant_id="grant-cascade",
        subject_id="urn:agent:cascade-agent",
        action_iri="urn:action:cascade_step",
        target_resource_iri="urn:cap:cascade",
    )
    authority_broker.register_grant(grant)

    boundary = ConsequenceBoundary(
        authority_broker=authority_broker,
        actuator=DummyActuator(),
        verifier=DummyVerifier(),
    )

    loop = ReactiveSemanticLoop(
        hook_engine=hook_engine,
        authority_broker=authority_broker,
        consequence_boundary=boundary,
        max_cascade_depth=3,
    )

    # Continually emit deltas to test bounded termination
    trace = loop.run_reflex_cycle(
        base_ttl="@prefix ex: <http://example.org/> . ex:s ex:p 'init' .",
        initial_event_ttl="@prefix ex: <http://example.org/> . ex:s ex:p 'e0' .",
        actor_id="urn:agent:cascade-agent",
        delta_generator=lambda r: f"@prefix ex: <http://example.org/> . ex:s ex:p '{r.receipt_id}' .",
    )

    assert len(trace.steps) == 3
    assert trace.stopped_by_bound is True
    assert trace.quiescence_reached is False
    assert trace.total_receipts == 3


def test_sa2a_cli_hook_evaluate_and_reflex():
    """Verify Typer CLI sa2a hook subcommands."""
    import json

    from typer.testing import CliRunner

    from autofde_lab.sa2a.cli import app

    runner = CliRunner()

    # 1. evaluate
    res_eval = runner.invoke(
        app,
        [
            "hook",
            "evaluate",
            "-b",
            "@prefix ex: <http://example.org/> . ex:a ex:b 1 .",
            "-e",
            "@prefix ex: <http://example.org/> . ex:a ex:b 2 .",
            "--hook-name",
            "test_eval_hook",
            "--action-iri",
            "urn:action:test_eval",
        ],
    )
    assert res_eval.exit_code == 0
    data_eval = json.loads(res_eval.stdout)
    assert data_eval["ok"] is True
    assert data_eval["evaluated_hooks_count"] == 1
    assert data_eval["records"][0]["hook_name"] == "test_eval_hook"
    assert data_eval["records"][0]["intent"]["action_iri"] == "urn:action:test_eval"

    # 2. reflex
    #
    # AFDE-2604 architecture fix (default-wiring closure): `hook reflex` now requires
    # admission by default (secure default -- see `.claude/rules` / the AFDE-2604
    # closure doc), so the event content must independently reach Standing.ADMITTED
    # AND explicitly bind this command's default action_iri/target_resource
    # (urn:action:freeze_credit / urn:cap:credit:freeze) via the real
    # `afl:targetResource` (urn:autofde-lab:targetResource) predicate before a real
    # DO can occur. The extra triple below is that real content binding, not a test
    # weakening -- it demonstrates the new secure default's legitimate happy path,
    # not the old unconditionally-permissive one.
    res_reflex = runner.invoke(
        app,
        [
            "hook",
            "reflex",
            "-b",
            "@prefix ex: <http://example.org/> . ex:a ex:b 1 .",
            "-e",
            (
                "@prefix ex: <http://example.org/> . ex:a ex:b 2 . "
                "<urn:action:freeze_credit> <urn:autofde-lab:targetResource> "
                "<urn:cap:credit:freeze> ."
            ),
        ],
    )
    assert res_reflex.exit_code == 0
    data_reflex = json.loads(res_reflex.stdout)
    assert data_reflex["ok"] is True
    assert data_reflex["quiescence_reached"] is True
    assert data_reflex["steps_count"] == 1
    assert data_reflex["steps"][0]["receipt_states"] == ["EXECUTED"]

    # AFDE-2604 regression check: the SAME command, WITHOUT the content-binding
    # triple, is now genuinely refused by default (proving the fence is real, not
    # merely documented) -- and `--skip-admission-check` explicitly restores the
    # old, permissive behavior for a caller that names that intent.
    res_unbound = runner.invoke(
        app,
        [
            "hook",
            "reflex",
            "-b",
            "@prefix ex: <http://example.org/> . ex:a ex:b 1 .",
            "-e",
            "@prefix ex: <http://example.org/> . ex:a ex:b 2 .",
        ],
    )
    assert res_unbound.exit_code == 0
    data_unbound = json.loads(res_unbound.stdout)
    assert data_unbound["steps"][0]["receipt_states"] == ["REFUSED"]

    res_skip = runner.invoke(
        app,
        [
            "hook",
            "reflex",
            "-b",
            "@prefix ex: <http://example.org/> . ex:a ex:b 1 .",
            "-e",
            "@prefix ex: <http://example.org/> . ex:a ex:b 2 .",
            "--skip-admission-check",
        ],
    )
    assert res_skip.exit_code == 0
    data_skip = json.loads(res_skip.stdout)
    assert data_skip["steps"][0]["receipt_states"] == ["EXECUTED"]
