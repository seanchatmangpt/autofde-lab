# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Mutation-law falsifier for the Logic & Knowledge Hook Court (RFC-SA2A-002 v26.9.16).

Per this repo's ``.claude/rules/level4-completion-law.md`` "Mutation law":

    For every required relation R, construct an otherwise-complete episode,
    mutate exactly R's identity, and require admission to produce a typed
    non-ALIVE evidence object.

and ``.claude/rules/no-dual-bookkeeping.md``:

    An identity join may be established ONLY by an explicit typed edge.
    Co-reference is not relationship: an event naming two objects does not
    assert that those two objects are related to each other.

This module builds a real, otherwise-complete, currently-valid SA2A-HOOK-NO-DO
evidence episode (a real ``KnowledgeHookDefinition`` synthesized by the real
``HookSynthesizer``, registered with a real ``KnowledgeHookEngine``, evaluated
to produce a real ``HookExecutionRecord`` with an admitted ``HookVerdict``),
then mutates EXACTLY ONE identity field on that record — ``hook_iri`` — to a
wrong-but-well-formed identity: the IRI of a *different*, real
``KnowledgeHookDefinition`` that was never registered, never executed, and
never admitted into this episode's ``hooks``/``admitted_hook_namespaces``.

Expected (per the Mutation law): the court's ``verify_hook_no_do`` /
``run_full_court`` MUST reject a ``HookExecutionRecord`` whose ``hook_iri``
does not correspond to any hook actually admitted into the episode — an event
record naming a hook is not evidence that record was produced by that hook.

Observed (measured live against
``src/autofde_lab/sa2a/conformance/courts/logic_hook_court.py`` this session):
neither ``verify_hook_no_do`` nor ``run_full_court`` binds
``HookExecutionRecord.hook_iri`` to anything — ``verify_hook_no_do`` inspects
only ``record.verdict`` against ``{FIRED, NOT_FIRED, GATED}`` and never
cross-references the record's claimed ``hook_iri`` against any admitted or
registered hook. A record can therefore claim attribution to a completely
foreign, never-admitted hook identity and still be judged
SA2A-HOOK-NO-DO CONFORMANT, and the same foreign-identity record still makes
``run_full_court`` return an all-CONFORMANT, ``passed=True`` report.

This is a REAL, CONFIRMED DEFECT in the existing implementation (not a guess):
each mutation below was run live against the real court before this file was
finalized. Per instructions, the court source
(``courts/logic_hook_court.py``) and the existing passing test file
(``test_court_logic_hook.py``) are NOT modified here — this file only
DEMONSTRATES the gap by asserting the court's actual (wrong) current
behavior, with the required rejection named explicitly in each docstring.

Chicago Zero-Mock Standard: real ``HookSynthesizer``, real
``KnowledgeHookEngine``, real ``LogicHookCourt`` throughout — no test
doubles of any kind for any collaborator in this file.
"""

from __future__ import annotations

from dataclasses import replace as dataclass_replace
from typing import List

from autofde_lab.sa2a.conformance.courts.logic_hook_court import (
    SA2A_HOOK_NO_DO,
    LogicHookCourt,
    LogicHookCourtReport,
    LogicHookVerdict,
)
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.model import (
    HookExecutionRecord,
    HookVerdict,
    KnowledgeHookDefinition,
)
from autofde_lab.sa2a.hooks.synthesis import HookSynthesizer

# ---------------------------------------------------------------------------
# Real-collaborator helpers (deliberately local to this file — the existing
# test_court_logic_hook.py is not imported from or modified).
# ---------------------------------------------------------------------------


def _make_hook(hook_name: str) -> KnowledgeHookDefinition:
    """Synthesize a real, well-formed KnowledgeHookDefinition via the real API."""
    synth = HookSynthesizer()
    return synth.synthesize_from_resolution(
        hook_name=hook_name,
        action_iri=f"urn:action:autofde:mutation:{hook_name}",
        target_capability_iri=f"urn:cap:autofde:mutation:{hook_name}",
    ).hook


def _run_hook_engine(hook: KnowledgeHookDefinition) -> List[HookExecutionRecord]:
    """Register a real hook in a real engine and evaluate it against real TTL graphs."""
    engine = KnowledgeHookEngine()
    engine.register_hook(hook)
    base_ttl = "@prefix : <urn:autofde:mutation:> . :subject :predicate :object ."
    event_ttl = "@prefix : <urn:autofde:mutation:> . :event :type :assertion ."
    return engine.evaluate(base_ttl=base_ttl, event_ttl=event_ttl)


# ---------------------------------------------------------------------------
# Mutation 1: verify_hook_no_do — hook_iri identity swap
# ---------------------------------------------------------------------------


def test_hook_iri_identity_swap_is_wrongly_accepted_by_verify_hook_no_do() -> None:
    """GAP: verify_hook_no_do does not bind HookExecutionRecord.hook_iri to any
    admitted/registered hook identity, so a record claiming a foreign hook's
    IRI is wrongly judged CONFORMANT.

    Otherwise-complete, currently-valid episode:
      - ``hook_admitted`` is a real hook, registered with a real
        ``KnowledgeHookEngine`` and evaluated to produce a real
        ``HookExecutionRecord`` carrying an admitted ``HookVerdict``
        (FIRED/NOT_FIRED/GATED). This baseline passes verify_hook_no_do,
        proving the episode is otherwise valid before any mutation.
      - ``hook_foreign`` is a second, real, independently synthesized hook
        that is NEVER registered with the engine and NEVER evaluated in
        this episode — it produced no execution record here.

    Mutation (exactly one field, wrong-but-well-formed identity):
      ``dataclasses.replace(record, hook_iri=hook_foreign.iri)`` — the
      record's verdict, condition_kind, and condition_hash are left
      untouched (still a legitimate, admitted verdict); only the referenced
      hook *identity* is swapped to a real, well-formed IRI that this
      episode never admitted and that never actually produced this record.

    Required (Mutation law / no-dual-bookkeeping "identity is explicit or it
    does not exist"): ``court.verify_hook_no_do([mutated], fail_closed=True)``
    MUST reject the record — a record naming a hook is not evidence that
    hook produced it; SA2A-HOOK-NO-DO's job is exactly to police what hook
    executions are admitted, and it cannot honestly do that while ignoring
    which hook a record claims to come from.

    Actual (measured live, this session, against the real, unmodified
    court): no exception is raised. ``result.passed is True`` and
    ``result.verdict == CONFORMANT`` — the foreign-identity record is
    accepted exactly as if it were legitimate. This assertion documents
    that real, current, wrong behavior; it is not the desired behavior.
    """
    court = LogicHookCourt()

    hook_admitted = _make_hook("mutation_hook_admitted")
    hook_foreign = _make_hook("mutation_hook_foreign")
    assert hook_admitted.iri != hook_foreign.iri, (
        "precondition: two distinct real hook identities"
    )

    records = _run_hook_engine(hook_admitted)
    assert len(records) >= 1, (
        "precondition: real engine evaluation produced at least one record"
    )
    real_record = records[0]
    assert real_record.hook_iri == hook_admitted.iri, (
        "precondition: record truthfully names its producing hook"
    )
    assert real_record.verdict in (
        HookVerdict.FIRED,
        HookVerdict.NOT_FIRED,
        HookVerdict.GATED,
    ), "precondition: record carries an admitted HookVerdict before mutation"

    # Baseline: the real, unmutated episode is CONFORMANT — proves the setup
    # is otherwise-complete and currently-valid before the single mutation.
    baseline = court.verify_hook_no_do(records, fail_closed=True)
    assert baseline.passed is True
    assert baseline.verdict == LogicHookVerdict.CONFORMANT
    assert baseline.rule_id == SA2A_HOOK_NO_DO

    # Mutation: swap exactly one field — the referenced hook identity — to a
    # real but foreign, never-admitted, never-executed hook's IRI.
    mutated_record = dataclass_replace(real_record, hook_iri=hook_foreign.iri)
    assert mutated_record.hook_iri == hook_foreign.iri
    assert mutated_record.verdict == real_record.verdict, (
        "only hook_iri identity was mutated"
    )

    # DEFECT DEMONSTRATION: the court SHOULD reject this (typed refusal /
    # non-CONFORMANT verdict, per SA2A-HOOK-NO-DO + the Mutation law), but
    # the real, unmodified implementation currently does not check hook_iri
    # provenance at all, so it silently accepts the foreign identity.
    result = court.verify_hook_no_do([mutated_record], fail_closed=True)
    assert (
        result.passed is True
    )  # WRONG: a foreign, never-admitted hook identity must not pass.
    assert (
        result.verdict == LogicHookVerdict.CONFORMANT
    )  # WRONG: should be REFUSED / NON_CONFORMANT.
    assert result.rule_id == SA2A_HOOK_NO_DO


# ---------------------------------------------------------------------------
# Mutation 2: run_full_court — the same identity swap survives the full sweep
# ---------------------------------------------------------------------------


def test_run_full_court_wrongly_reports_passed_with_foreign_hook_iri_in_records() -> (
    None
):
    """GAP: run_full_court's aggregate report does not cross-reference
    hook_execution_records' hook_iri against the hooks admitted into the
    same episode, so a foreign-identity record still yields an all-CONFORMANT,
    passed=True report.

    Otherwise-complete, currently-valid episode: ``hook_admitted`` is the
    ONLY hook passed in ``hooks=[...]`` (and therefore the only hook whose
    IRI was ever checked by SA2A-HOOK-META-ADMISSION in this episode); its
    real execution record baseline-passes the full court sweep unmutated.

    Mutation (exactly one field): the same real-but-foreign hook_iri swap as
    the unit-level test above, applied to the record before it is handed to
    ``run_full_court`` as ``hook_execution_records``.

    Required: a report cannot honestly claim ``passed=True`` /
    all-CONFORMANT while one of its ``hook_execution_records`` claims
    attribution to a hook identity that this same episode's ``hooks``
    sequence never admitted — that is precisely the
    admitted-hooks/execution-records join `no-dual-bookkeeping.md` requires
    to be explicit, not inferred from adjacency (both parameters happening
    to be passed to the same call is not a relationship).

    Actual (measured live, this session): ``report.passed is True`` and
    every one of the 8 gate_results is CONFORMANT, including
    SA2A-HOOK-NO-DO — the full sweep exhibits the identical gap as the
    unit-level check, because run_full_court performs no additional
    cross-referencing of its own.
    """
    court = LogicHookCourt()

    hook_admitted = _make_hook("mutation_full_court_admitted")
    hook_foreign = _make_hook("mutation_full_court_foreign")
    assert hook_admitted.iri != hook_foreign.iri

    records = _run_hook_engine(hook_admitted)
    assert len(records) >= 1
    real_record = records[0]
    assert real_record.hook_iri == hook_admitted.iri

    admitted_namespace = hook_admitted.iri.rsplit("/", 1)[0] + "/"

    # Baseline: otherwise-complete, currently-valid full-court episode with
    # ONLY the real, truthful record — proves the setup is valid pre-mutation.
    baseline_report = court.run_full_court(
        datalog_rules=[],
        required_atoms=[],
        hooks=[hook_admitted],
        hook_execution_records=records,
        admitted_hook_namespaces=[admitted_namespace],
        n3_output={"triples": []},
        fuel_budget=100,
        elapsed_ms=1.0,
        fail_closed=False,
    )
    assert isinstance(baseline_report, LogicHookCourtReport)
    assert baseline_report.passed is True
    assert baseline_report.failed_checks == 0

    # Mutation: swap exactly one field on the sole execution record — its
    # hook_iri — to hook_foreign's real IRI. hook_foreign is NOT in `hooks`,
    # so it was never admitted into this episode by SA2A-HOOK-META-ADMISSION.
    mutated_record = dataclass_replace(real_record, hook_iri=hook_foreign.iri)

    # DEFECT DEMONSTRATION: the report SHOULD be non-conformant (at minimum
    # SA2A-HOOK-NO-DO should refuse), but the real, unmodified run_full_court
    # currently reports full CONFORMANT / passed=True regardless.
    mutated_report = court.run_full_court(
        datalog_rules=[],
        required_atoms=[],
        hooks=[hook_admitted],  # hook_foreign is deliberately NOT admitted here
        hook_execution_records=[mutated_record],
        admitted_hook_namespaces=[admitted_namespace],
        n3_output={"triples": []},
        fuel_budget=100,
        elapsed_ms=1.0,
        fail_closed=False,
    )
    assert isinstance(mutated_report, LogicHookCourtReport)
    assert (
        mutated_report.passed is True
    )  # WRONG: a foreign-identity record must not yield a clean report.
    assert (
        mutated_report.failed_checks == 0
    )  # WRONG: SA2A-HOOK-NO-DO (at least) should have failed.

    no_do_results = [
        r for r in mutated_report.gate_results if r.rule_id == SA2A_HOOK_NO_DO
    ]
    assert len(no_do_results) == 1
    assert (
        no_do_results[0].passed is True
    )  # WRONG: same gap as the unit-level test, reached via the full sweep.
    assert (
        no_do_results[0].verdict == LogicHookVerdict.CONFORMANT
    )  # WRONG: should be REFUSED / NON_CONFORMANT.
