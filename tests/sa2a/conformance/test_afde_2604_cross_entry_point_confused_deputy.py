# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Adversarial falsifiers against the AFDE-2604 admission fence, lensed on
CROSS-ENTRY-POINT CONFUSED DEPUTY: is the fence a property of the resource/action being
protected, or merely a property of the one call site (`execute_admitted()`) a caller
*chooses* to use? Per `.claude/rules/level4-completion-law.md`'s Mutation law: construct
an otherwise-complete, currently-valid episode and mutate exactly the entry point used,
expecting refusal if the fence is real.

These are DELIBERATELY DIFFERENT mutations from `test_afde_2604_fresh_mutations_qualification.py`
(Mutations A/B/C, which all go through `execute_admitted()` itself). This file never calls
`execute_admitted()` as the attack surface -- it asks whether the fence can be walked
around entirely, via a different real entry point into the exact same objects.

  MUTATION CD-1 -- production `ReactiveSemanticLoop` / `sa2a/cli.py hook reflex` bypass:
    originally, `ReactiveSemanticLoop.__init__`'s `admission_pipeline` parameter defaulted
    to `None`, and `sa2a/cli.py`'s real, shipped `hook reflex` Typer command constructed
    `ReactiveSemanticLoop` with no `admission_pipeline=` argument at all -- so the ONLY
    currently-shipped CLI entry point that drives `ReactiveSemanticLoop` actuated real
    consequence with zero admission binding, for any caller of that command.

  MUTATION CD-2 -- same-object raw `execute()` bypass: a `ConsequenceBoundary` instance for
    which `execute_admitted()` correctly refuses an unadmitted envelope was, on the exact
    same instance with the exact same envelope, fully executable via `execute()` instead.
    Nothing on `ConsequenceBoundary` itself recorded "this instance/action requires
    admission" -- the fence was a second, independent method a caller could simply not
    call.

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real `AuthorityBroker` / `AuthorityGrant`, real `KnowledgeHookEngine`, real
  `HookSynthesizer.synthesize_from_resolution()`, real `ReactiveSemanticLoop`, and (for
  Mutation CD-1) the REAL, unmodified `sa2a/cli.py` Typer app, invoked in-process via
  `typer.testing.CliRunner` -- the same real-entry-point pattern
  `test_knowledge_hooks.py::test_sa2a_cli_hook_evaluate_and_reflex` already uses.
- Real `RealDiskJournalActuator` / `IndependentDiskJournalVerifier` (genuine physical
  disk I/O) and a real `DurableDiskReceiptStore`, the same real collaborators
  `test_afde_2604_fresh_mutations_qualification.py` uses.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this
  file.

RESULT (AFDE-2604 architecture fix, this session -- ARCHITECTURE, not per-instance patch;
see `src/autofde_lab/sa2a/brce/boundary.py`, `src/autofde_lab/sa2a/hooks/reactive_loop.py`,
`src/autofde_lab/sa2a/cli.py`):

  MUTATION CD-1 -- DEFEATED (unified enforcement, Problem 2, PLUS default wiring,
    Problem 3). `ConsequenceBoundary` gained a `require_admission: bool = False`
    constructor flag; when `True`, `execute()` itself applies the identical admission
    gate `execute_admitted()` always applied, so the two public methods become
    behaviorally identical for gating purposes on that instance. Separately,
    `sa2a/cli.py`'s `hook reflex` command now constructs its `ConsequenceBoundary` with
    `require_admission=True` and its `ReactiveSemanticLoop` with a real
    `AdmissionPipeline()` BY DEFAULT -- the SECURE behavior is the default, not an
    opt-in -- with an explicit, visible `--skip-admission-check` flag for a caller who
    genuinely needs the old permissive behavior (never a silent default). This test now
    drives the REAL, unmodified `sa2a/cli.py hook reflex` Typer command via `CliRunner`
    (not a hand-reproduction of its construction) and confirms: (a) by default, content
    that never binds the action/target to a real admitted triple is refused before any
    real actuation; (b) by default, content that DOES properly bind them (via the real
    `afl:targetResource`/`urn:autofde-lab:targetResource` predicate) still genuinely
    executes -- the fence gates on content, not on blanket refusal; (c) `--skip-
    admission-check` explicitly restores the prior permissive behavior, by name, never
    silently.

  MUTATION CD-2 -- DEFEATED (unified enforcement, Problem 2). The SAME
    `ConsequenceBoundary` instance, constructed with `require_admission=True`, now
    refuses an unadmitted envelope identically whether reached via `execute_admitted()`
    or via raw `execute()` -- there is no longer a caller-selectable bypass for an
    instance configured to require admission. `require_admission=False` (the default)
    leaves `execute()` byte-for-byte unchanged for every existing caller that never
    passes this flag; `require_admission=True` is what actually removes the two-method
    ambiguity this mutation exploited.

Both mutations are exercised here as regression fixtures: PASS now means the
architecture fix genuinely defeats each construction; a future regression that
reintroduces either bypass would FAIL here with the same real disk/receipt evidence
this file's assertions already check for.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import (
    REFUSED_NOT_ADMITTED,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.cli import app
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)


def _boundary(
    tmp_path: Path, name: str, broker: AuthorityBroker, *, require_admission: bool = False
):
    journal = tmp_path / name / "journal.json"
    store = DurableDiskReceiptStore(tmp_path / name / "receipts")
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=store,
        require_admission=require_admission,
    )
    return boundary, actuator, store, journal


# ---------------------------------------------------------------------------
# Mutation CD-1: production ReactiveSemanticLoop / sa2a cli.py `hook reflex` bypass.
# ---------------------------------------------------------------------------


def test_mutation_cd1_reactive_loop_default_admission_pipeline_bypasses_fence_entirely() -> None:
    """Drive the REAL, unmodified `sa2a/cli.py hook reflex` Typer command in-process via
    `CliRunner` (not a hand-reproduction of its construction) and confirm the AFDE-2604
    architecture fix's default-wiring closure (Problem 3): SECURE BY DEFAULT.

    Three real invocations of the same real command:
      1. Default flags, content that never binds action_iri/target_resource via a real
         `afl:targetResource` triple -> refused before any real actuation (zero
         receipts for the synthesized intent).
      2. Default flags, content that DOES bind them -> genuinely executes (the fence
         gates on content, not blanket refusal -- legitimate use still works).
      3. `--skip-admission-check` explicitly passed, same unbound content as (1) ->
         restores the prior permissive behavior, by explicit, visible caller intent,
         never silently.

    Superseded finding (pre-fix): this test formerly hand-reproduced
    `ReactiveSemanticLoop(admission_pipeline=None)` (`sa2a/cli.py`'s old, permissive
    default construction) and confirmed real, physical actuation proceeded with ZERO
    `AdmissionPipeline`/`AdmissionResult` ever constructed -- MUTATION CD-1 SURVIVED.
    The architecture fix changed `sa2a/cli.py` itself (not merely `ReactiveSemanticLoop`'s
    own class-level default, which stays `None` for library-level backward
    compatibility -- see `reactive_loop.py`'s own docstring): the CLI command now wires a
    real `AdmissionPipeline()` and `ConsequenceBoundary(require_admission=True)` unless
    the caller explicitly opts out, so this test now exercises the real production entry
    point directly instead of a hand copy of its (now-outdated) construction.
    """
    runner = CliRunner()
    base_ttl = "@prefix ex: <http://example.org/> . ex:cluster ex:status \"OK\" ."
    unbound_event_ttl = "@prefix ex: <http://example.org/> . ex:pod ex:status \"CRASH_LOOP\" ."
    action_iri = "urn:action:fresh-mut-d:wire-transfer"
    target_resource = "urn:cap:fresh-mut-d:treasury"
    bound_event_ttl = (
        unbound_event_ttl
        + f" <{action_iri}> <urn:autofde-lab:targetResource> <{target_resource}> ."
    )

    def _invoke(event_ttl: str, *extra_args: str) -> dict:
        result = runner.invoke(
            app,
            [
                "hook",
                "reflex",
                "-b",
                base_ttl,
                "-e",
                event_ttl,
                "--action-iri",
                action_iri,
                "--target-resource",
                target_resource,
                *extra_args,
            ],
        )
        assert result.exit_code == 0, f"CLI invocation failed: {result.stdout!r}"
        return json.loads(result.stdout)

    # (1) SECURE DEFAULT, content that never binds action_iri/target_resource: refused
    # with a real, typed REFUSED receipt (produced by the boundary's own admission
    # gate) -- not silently dropped, and never EXECUTED.
    unbound_default = _invoke(unbound_event_ttl)
    assert unbound_default["steps"][0]["receipt_states"] == ["REFUSED"], (
        "MUTATION CD-1 SURVIVED: `python -m autofde_lab.sa2a.cli hook reflex`'s SECURE "
        "DEFAULT (no --skip-admission-check) let real actuation proceed for content "
        f"that never bound action_iri={action_iri!r}/target_resource={target_resource!r} "
        f"to a real admitted triple. Full CLI JSON output: {unbound_default!r}."
    )
    assert unbound_default["total_receipts"] == 1
    assert unbound_default["steps"][0]["intents_count"] == 1, (
        "The hook still fired and an intent was still synthesized -- refusal happened "
        "at the admission/content-binding fence, not because nothing was attempted."
    )

    # (2) SECURE DEFAULT, content that DOES bind them: genuinely executes.
    bound_default = _invoke(bound_event_ttl)
    assert bound_default["total_receipts"] == 1
    assert bound_default["steps"][0]["receipt_states"] == ["EXECUTED"], (
        "The SECURE DEFAULT must not merely refuse everything -- properly admitted, "
        f"content-bound input must still reach real EXECUTED consequence. Got: "
        f"{bound_default!r}."
    )

    # (3) Explicit, visible opt-out restores the OLD permissive behavior for the SAME
    # unbound content that (1) refused by default.
    skip_result = _invoke(unbound_event_ttl, "--skip-admission-check")
    assert skip_result["total_receipts"] == 1
    assert skip_result["steps"][0]["receipt_states"] == ["EXECUTED"], (
        "--skip-admission-check must explicitly restore the prior permissive "
        f"candidate -> authority -> DO behavior when the caller names that intent. "
        f"Got: {skip_result!r}."
    )


# ---------------------------------------------------------------------------
# Mutation CD-2: same-object raw execute() bypass of execute_admitted()'s own fence.
# ---------------------------------------------------------------------------


def test_mutation_cd2_raw_execute_bypasses_execute_admitted_fence_on_same_instance(
    tmp_path: Path,
) -> None:
    """On a `ConsequenceBoundary` instance constructed with `require_admission=True`
    (AFDE-2604 architecture fix, Problem 2 -- unified enforcement), confirm that
    `execute_admitted()` refuses an unadmitted attempt (control, `token_gated`) AND
    that raw `execute()` on the SAME instance, for the SAME sensitive action/target
    and the SAME real `AuthorityGrant`, now refuses IDENTICALLY (`token_bypass`) --
    there is no longer a caller-selectable bypass for an instance configured to
    require admission. Two distinct tokens are used deliberately: reusing one token
    would let `execute_admitted()`'s own persisted refusal receipt short-circuit the
    later `execute()` call via ordinary idempotency replay (a real, separate
    protective side effect of the SHARED store, not of the admission check itself) --
    that would conflate "replay protection caught a repeated attempt on one token"
    with "the fence protects this action/target/instance," the actual property under
    test here.

    Superseded finding (pre-fix): on a boundary instance with no admission-requiring
    configuration at all (nothing on `ConsequenceBoundary` recorded "this instance
    requires admission"), raw `execute()` fully, physically actuated the exact
    action/target `execute_admitted()` correctly refused on the same instance --
    MUTATION CD-2 SURVIVED. The architecture fix adds `require_admission: bool =
    False` to `ConsequenceBoundary.__init__`; `True` makes `execute()` itself apply
    the identical admission gate `execute_admitted()` always applied, so admission
    enforcement is a property of the INSTANCE's configuration, never of which public
    method a caller happens to invoke. `require_admission=False` (the default) still
    leaves `execute()` byte-for-byte unchanged for every existing caller/test that
    never passes this flag.
    """
    actor_id = "urn:agent:fresh-mut-e-actor"
    sensitive_action = "urn:action:fresh-mut-e:delete-all-records"
    sensitive_target = "urn:resource:fresh-mut-e:critical-database"
    token_gated = "idemp-fresh-mut-e-gated-attempt"
    token_bypass = "idemp-fresh-mut-e-bypass-attempt"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-e",
            subject_id=actor_id,
            action_iri=sensitive_action,
            target_resource_iri=sensitive_target,
        )
    )
    # AFDE-2604 architecture fix: this instance is configured to REQUIRE admission --
    # the property that was previously entirely absent from ConsequenceBoundary.
    boundary, actuator, _store, journal = _boundary(
        tmp_path, "mut_e", broker, require_admission=True
    )
    assert boundary.require_admission is True

    # Control: a real caller routing through the strict entry point, for this exact
    # sensitive action/target, with no admission bound, is genuinely refused.
    gated = boundary.execute_admitted(
        ExecutionEnvelope(
            idempotency_token=token_gated,
            action_iri=sensitive_action,
            target_resource=sensitive_target,
            actor_id=actor_id,
            admission_result=None,
        )
    )
    assert gated.success is False
    assert gated.refusal_code == REFUSED_NOT_ADMITTED
    assert actuator.call_count == 0
    assert journal.exists() is False

    # FORMER MUTATION, NOW DEFEATED: the SAME require_admission=True boundary instance,
    # the SAME sensitive action/target, the SAME real AuthorityGrant -- but dispatching
    # straight to the OTHER public method (raw execute(), never execute_admitted()) with
    # a fresh idempotency token. Unified enforcement means this must refuse identically.
    bypassed = boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token_bypass,
            action_iri=sensitive_action,
            target_resource=sensitive_target,
            actor_id=actor_id,
            admission_result=None,
        )
    )

    assert bypassed.success is False, (
        "MUTATION CD-2 SURVIVED: ConsequenceBoundary.execute(), called directly (never "
        "through execute_admitted()) on a require_admission=True instance that "
        f"correctly refuses this exact action/target via execute_admitted(), fully "
        f"actuated {sensitive_action!r} on {sensitive_target!r} with ZERO admission "
        f"binding -- using only the real AuthorityGrant already registered on the "
        f"broker. bypassed.success={bypassed.success!r} state={bypassed.state!r} "
        f"actuator.call_count={actuator.call_count} journal.exists()={journal.exists()}. "
        "Unified enforcement (require_admission=True) should make execute() apply the "
        "identical admission gate execute_admitted() applies -- if this assertion now "
        "fails in a future run, that unification has regressed."
    )
    assert bypassed.state == TerminalReceiptState.REFUSED
    assert bypassed.refusal_code == REFUSED_NOT_ADMITTED
    assert actuator.call_count == 0, "Zero real actuation via raw execute() on a strict instance."
    assert journal.exists() is False, "Zero disk mutation via raw execute() on a strict instance."
    assert bypassed.final_receipt is not None
    assert bypassed.final_receipt.state == TerminalReceiptState.REFUSED

    # Both attempts -- one via execute_admitted(), one via raw execute() -- are refused
    # identically on this instance: unified enforcement, not a caller-selectable bypass.
    gated_final = boundary.receipt_store.get_final(token_gated)
    assert gated_final is not None
    assert gated_final.state == TerminalReceiptState.REFUSED

    bypass_final = boundary.receipt_store.get_final(token_bypass)
    assert bypass_final is not None
    assert bypass_final.state == TerminalReceiptState.REFUSED

    # Positive control: on a DIFFERENT (require_admission=False, the default) instance,
    # execute() remains byte-for-byte unchanged -- unified enforcement is opt-in per
    # instance, never a global behavior change for every existing caller/test.
    default_boundary, default_actuator, _default_store, default_journal = _boundary(
        tmp_path, "mut_e_default", broker
    )
    assert default_boundary.require_admission is False
    unfenced = default_boundary.execute(
        ExecutionEnvelope(
            idempotency_token="idemp-fresh-mut-e-default-instance",
            action_iri=sensitive_action,
            target_resource=sensitive_target,
            actor_id=actor_id,
            admission_result=None,
        )
    )
    assert unfenced.success is True
    assert unfenced.state == TerminalReceiptState.EXECUTED
    assert default_actuator.call_count == 1
    assert default_journal.exists()
