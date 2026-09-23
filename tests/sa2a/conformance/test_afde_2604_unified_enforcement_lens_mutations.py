# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Adversarial falsifiers against the AFDE-2604 "unified enforcement" architecture fix,
lensed specifically on: is there ANY real, reachable code path where `execute()` and
`execute_admitted()` (or their unified successor) behave differently for the SAME
`ConsequenceBoundary` configuration -- a residual caller-selectable bypass the
Local-Round-3 redesign missed?

This file is deliberately narrower than
`test_afde_2604_cross_entry_point_confused_deputy.py` (which the redesign already
defeats, per its own docstring): it does not re-attack CD-1/CD-2 directly. It probes
one level further out -- whether the redesign's own unification guarantee
("admission enforcement is a property of THIS INSTANCE's configuration, never of
which public method a caller happens to invoke") actually holds once a
`ConsequenceBoundary` is embedded inside its one real production wrapper,
`ReactiveSemanticLoop`, or once its own private configuration attribute is inspected
for tamper-resistance.

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real `AuthorityBroker` / `AuthorityGrant`, real `KnowledgeHookEngine`, real
  `AdmissionPipeline`, real `ReactiveSemanticLoop`.
- Real `RealDiskJournalActuator` / `IndependentDiskJournalVerifier` / genuine physical
  disk I/O + `DurableDiskReceiptStore`, the same real collaborators the sibling
  cross-entry-point file uses.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in
  this file.

RESULTS (both real, both run this session -- see the PASS/FAIL each test asserts):

  MUTATION UE-1 -- content-binding under raw `execute()` (control/sanity, not a new
    attack surface): DEFEATED. A `require_admission=True` boundary's raw `execute()`
    refuses an envelope carrying a real, `Standing.ADMITTED` `AdmissionResult` for
    UNRELATED content (never binding this exact action/target via the
    `afl:targetResource` triple) exactly as `execute_admitted()` would -- confirming
    the unification holds not just for "no admission at all" (already covered by
    `test_mutation_cd2...`) but also for "admission exists but doesn't cover this
    exact action/target," exercised through the raw-`execute()` surface specifically.

  MUTATION UE-2 -- `ReactiveSemanticLoop.admission_pipeline` / `ConsequenceBoundary
    .require_admission` desynchronization: SURVIVED. A real, reachable gap the
    Local-Round-3 "unified enforcement" fix does not close: `ReactiveSemanticLoop`
    and the `ConsequenceBoundary` it wraps are two INDEPENDENTLY configured objects
    with no invariant tying them together. Wiring a real `AdmissionPipeline` into the
    loop (so `run_reflex_cycle()` itself correctly refuses unbound content via
    `execute_admitted()`) does nothing to the boundary's own `require_admission`
    flag, which stays at its default (`False`) unless a caller separately,
    additionally passes `require_admission=True` to the `ConsequenceBoundary`
    constructor. `loop.consequence_boundary` is a plain public attribute (no leading
    underscore, no property indirection), so ANY code holding the loop also holds
    the exact boundary instance the loop uses -- and calling `.execute()` on that
    boundary DIRECTLY, for the identical sensitive action/target the loop's own
    dispatch just refused, actuates for real (real disk I/O observed). The
    Local-Round-3 fix unifies `execute()`/`execute_admitted()` for a GIVEN
    `require_admission` value; it does not unify "a caller wired a real admission
    pipeline somewhere in the call graph" with "the boundary itself requires
    admission." The only production call site (`sa2a/cli.py`'s `hook_reflex`)
    happens to tie both flags to the same `skip_admission_check` boolean, but that is
    a discipline convention at ONE call site, not an invariant the classes enforce --
    a different or future caller that wires `ReactiveSemanticLoop(...,
    admission_pipeline=AdmissionPipeline())` without ALSO passing
    `ConsequenceBoundary(..., require_admission=True)` gets a false sense of
    security: the loop's own reflex-cycle dispatch is fenced, the boundary
    underneath it is not, and both are reachable.

  MUTATION UE-3 (bonus, weaker/named honestly as low-severity) -- `_require_admission`
    is a plain mutable instance attribute, not enforced immutable by a frozen
    dataclass, `__slots__` write-guard, or property setter rejection. Any code
    holding a `ConsequenceBoundary` reference can set `boundary._require_admission =
    False` directly and thereby make `execute()` permissive while `execute_admitted()`
    (which always re-applies the gate regardless of the flag) remains strict on the
    SAME object -- a real, observable divergence. Named as low-severity because the
    `require_admission` property honestly reports the tampered value afterward (no
    caller is misled about the instance's actual configuration by inspecting it) --
    this is "the flag isn't tamper-proof," not "the flag lies about itself."
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import (
    REFUSED_ADMISSION_CONTENT_NOT_BOUND,
    REFUSED_NOT_ADMITTED,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.model import (
    HookEffectKind,
    HookEventTrigger,
    KnowledgeHookDefinition,
)
from autofde_lab.sa2a.hooks.reactive_loop import ReactiveSemanticLoop


def _real_boundary(
    tmp_path: Path, name: str, broker: AuthorityBroker, *, require_admission: bool
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
    return boundary, actuator, journal


# ---------------------------------------------------------------------------
# Mutation UE-1: content-not-bound admission, attacked via raw execute() directly
# (never execute_admitted()) on a require_admission=True instance.
# ---------------------------------------------------------------------------


def test_mutation_ue1_raw_execute_refuses_admitted_but_unbound_content(
    tmp_path: Path,
) -> None:
    """A real, genuinely `Standing.ADMITTED` `AdmissionResult` exists (a real
    `AdmissionPipeline().admit()` call actually ran and passed), but for UNRELATED
    content that never asserts the `afl:targetResource` triple binding this exact
    action/target. Attacked purely through raw `execute()` (never
    `execute_admitted()`) on a `require_admission=True` instance.
    """
    actor_id = "urn:agent:ue1-actor"
    action_iri = "urn:action:ue1:wire-transfer"
    target_resource = "urn:cap:ue1:treasury"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-ue1",
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )
    boundary, actuator, journal = _real_boundary(
        tmp_path, "ue1", broker, require_admission=True
    )

    # Real admission pipeline call -- genuinely reaches Standing.ADMITTED, but for
    # content that never mentions action_iri/target_resource at all, let alone binds
    # them via afl:targetResource.
    pipeline = AdmissionPipeline()
    unrelated_ttl = (
        '@prefix ex: <http://example.org/> . ex:unrelated-node ex:status "OK" .'
    )
    admission_result = pipeline.admit(
        unrelated_ttl,
        provenance_record={"issuer": actor_id, "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admission_result.standing == Standing.ADMITTED, (
        "Precondition failed: the admission call itself must genuinely succeed for "
        f"this to be a meaningful test of content-binding, not admission failure. Got "
        f"standing={admission_result.standing!r}, refusal_code="
        f"{admission_result.refusal_code!r}."
    )

    result = boundary.execute(
        ExecutionEnvelope(
            idempotency_token="idemp-ue1-raw-execute",
            action_iri=action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            admission_result=admission_result,
        )
    )

    assert result.success is False, (
        "MUTATION UE-1 SURVIVED: raw execute() on a require_admission=True instance "
        "actuated a sensitive action/target using a real, genuinely ADMITTED "
        f"AdmissionResult that never bound that exact action/target via the "
        f"afl:targetResource triple. result={result!r}"
    )
    assert result.refusal_code == REFUSED_ADMISSION_CONTENT_NOT_BOUND
    assert actuator.call_count == 0
    assert journal.exists() is False


# ---------------------------------------------------------------------------
# Mutation UE-2: ReactiveSemanticLoop.admission_pipeline vs. ConsequenceBoundary
# .require_admission desynchronization -- the actual finding.
# ---------------------------------------------------------------------------


def test_mutation_ue2_loop_admission_pipeline_does_not_imply_boundary_require_admission(
    tmp_path: Path,
) -> None:
    """A `ReactiveSemanticLoop` wired with a real `AdmissionPipeline` correctly fences
    its OWN `run_reflex_cycle()` dispatch (via `execute_admitted()`). But the
    `ConsequenceBoundary` it wraps was constructed WITHOUT `require_admission=True`
    (the class default, `False` -- nothing forces a caller to also pass this), and
    `loop.consequence_boundary` is a plain public attribute. Calling `.execute()`
    directly on that SAME boundary instance, for the SAME sensitive action/target the
    loop's own dispatch just refused, must (per the "unified enforcement" guarantee's
    spirit) either be impossible or itself refuse -- if it instead actuates for real,
    the redesign has a residual, reachable bypass one level outside the
    `ConsequenceBoundary` class itself.
    """
    actor_id = "urn:agent:ue2-actor"
    action_iri = "urn:action:ue2:delete-all-records"
    target_resource = "urn:resource:ue2:critical-database"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-ue2",
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )

    # The caller DOES wire a real admission pipeline into the loop, believing this
    # secures the whole reflex path -- but never passes require_admission=True to the
    # boundary (the class default stays False; nothing warns or refuses this).
    boundary, actuator, journal = _real_boundary(
        tmp_path, "ue2", broker, require_admission=False
    )
    assert boundary.require_admission is False

    engine = KnowledgeHookEngine()
    engine.register_hook(
        KnowledgeHookDefinition(
            iri="http://example.org/hook/ue2_reflex",
            name="ue2_reflex_hook",
            on=HookEventTrigger.ASSERT,
            effect=HookEffectKind.GROUND_ACTION,
            action_iri=action_iri,
            target_capability_iri=target_resource,
            goal_iri="urn:goal:ue2_containment",
        )
    )

    loop = ReactiveSemanticLoop(
        hook_engine=engine,
        authority_broker=broker,
        consequence_boundary=boundary,
        admission_pipeline=AdmissionPipeline(),
    )

    base_ttl = '@prefix ex: <http://example.org/> . ex:cluster ex:status "OK" .'
    unbound_event_ttl = (
        '@prefix ex: <http://example.org/> . ex:pod ex:status "CRASH_LOOP" .'
    )

    trace = loop.run_reflex_cycle(
        base_ttl,
        unbound_event_ttl,
        actor_id=actor_id,
        delta_generator=lambda r: "",  # quiesce after one step, same as sa2a/cli.py's hook_reflex
    )

    # Confirm the loop's OWN dispatch really is fenced: the hook fired, an intent was
    # synthesized, but it was refused before real actuation (content never bound via
    # afl:targetResource, exactly like CD-1's unbound case).
    assert len(trace.steps) == 1
    step = trace.steps[0]
    assert len(step.intents_synthesized) == 1, (
        "The hook must have fired for this to be a meaningful control."
    )
    assert [r.state for r in step.final_receipts] == [TerminalReceiptState.REFUSED], (
        f"Precondition failed: loop.run_reflex_cycle()'s own gated dispatch must "
        f"refuse this unbound content for the bypass below to be meaningful. "
        f"receipt states={[r.state for r in step.final_receipts]!r}"
    )
    assert [r.refusal_code for r in step.final_receipts] == [
        REFUSED_ADMISSION_CONTENT_NOT_BOUND
    ] or [r.refusal_code for r in step.final_receipts] == [REFUSED_NOT_ADMITTED]
    assert actuator.call_count == 0
    assert journal.exists() is False, (
        "Zero real actuation via the loop's own gated dispatch."
    )

    # THE BYPASS: the exact same ConsequenceBoundary instance the "secured" loop just
    # used, reached via the loop's own public attribute, called directly with NO
    # admission_result at all.
    bypass_env = ExecutionEnvelope(
        idempotency_token="idemp-ue2-direct-boundary-bypass",
        action_iri=action_iri,
        target_resource=target_resource,
        actor_id=actor_id,
        admission_result=None,
    )
    bypassed = loop.consequence_boundary.execute(bypass_env)

    if bypassed.success is True:
        # SURVIVED -- named, precise, not patched here.
        assert bypassed.state == TerminalReceiptState.EXECUTED
        assert actuator.call_count == 1, (
            "MUTATION UE-2 SURVIVED: loop.consequence_boundary.execute(), called "
            "directly (never through ReactiveSemanticLoop.run_reflex_cycle() or "
            "execute_admitted()), fully actuated the exact sensitive "
            f"action_iri={action_iri!r} / target_resource={target_resource!r} that "
            "the loop's own admission-fenced dispatch just refused one line above -- "
            "using only a real, already-registered AuthorityGrant and ZERO admission "
            f"binding. bypassed={bypassed!r}"
        )
        assert journal.exists(), (
            "Real physical disk consequence via the direct-boundary bypass."
        )
    else:
        # If this ever fails, the desync this test targets has been closed --
        # documented here so a future run's flip is visible and expected, not a
        # silent regression of THIS test's own control assumptions.
        raise AssertionError(
            "MUTATION UE-2 now DEFEATED (unexpected relative to source read this "
            f"session): loop.consequence_boundary.execute() refused directly. "
            f"bypassed={bypassed!r}. If this is a genuine fix, boundary.require_admission "
            f"is presumably no longer independent of loop.admission_pipeline -- update "
            "this test's docstring and expectations to match the new invariant."
        )


# ---------------------------------------------------------------------------
# Mutation UE-3 (bonus, named low-severity): _require_admission is a plain mutable
# attribute, not frozen/immutable.
# ---------------------------------------------------------------------------


def test_mutation_ue3_require_admission_flag_is_not_tamper_resistant(
    tmp_path: Path,
) -> None:
    """`ConsequenceBoundary._require_admission` is an ordinary instance attribute (no
    `__slots__` write guard, no frozen dataclass, no property setter rejection).
    Any code holding a boundary reference can flip it post-construction. Named
    low-severity: `boundary.require_admission` honestly reports the tampered value
    afterward, so this is "not tamper-proof," not "lies about its own state."
    """
    actor_id = "urn:agent:ue3-actor"
    action_iri = "urn:action:ue3:freeze-account"
    target_resource = "urn:cap:ue3:accounts"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-ue3",
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )
    boundary, actuator, journal = _real_boundary(
        tmp_path, "ue3", broker, require_admission=True
    )

    # Control: execute_admitted() refuses, as expected, before tampering.
    gated = boundary.execute_admitted(
        ExecutionEnvelope(
            idempotency_token="idemp-ue3-control",
            action_iri=action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            admission_result=None,
        )
    )
    assert gated.success is False
    assert actuator.call_count == 0

    # Tamper: no API prevents this.
    boundary._require_admission = False  # type: ignore[attr-defined]
    assert boundary.require_admission is False, (
        "The property honestly reflects the tampered value -- this is the "
        "low-severity half of the finding."
    )

    tampered = boundary.execute(
        ExecutionEnvelope(
            idempotency_token="idemp-ue3-post-tamper",
            action_iri=action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            admission_result=None,
        )
    )

    if tampered.success is True:
        assert actuator.call_count == 1
        assert journal.exists()
        # And execute_admitted() on the SAME, now-tampered instance still refuses --
        # confirming the divergence is real and reachable post-tamper.
        still_gated = boundary.execute_admitted(
            ExecutionEnvelope(
                idempotency_token="idemp-ue3-post-tamper-admitted",
                action_iri=action_iri,
                target_resource=target_resource,
                actor_id=actor_id,
                admission_result=None,
            )
        )
        assert still_gated.success is False, (
            "execute_admitted() always re-applies the gate regardless of "
            "_require_admission -- it must still refuse even on a tampered instance."
        )
    else:
        raise AssertionError(
            f"MUTATION UE-3 now DEFEATED (unexpected relative to source read this "
            f"session): execute() refused even after _require_admission was set to "
            f"False directly. tampered={tampered!r}"
        )
