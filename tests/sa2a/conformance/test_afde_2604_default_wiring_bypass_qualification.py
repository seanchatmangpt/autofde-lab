# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Adversarial falsifiers against the AFDE-2604 default-wiring fix, lensed on
DEFAULT-WIRING AND OPT-OUT ABUSE (per this session's own task framing): is "secure by
default" a property of the underlying `ReactiveSemanticLoop`/`ConsequenceBoundary`
primitives, or only a property of the one shipped `sa2a/cli.py hook reflex` Typer
command that happens to construct them a specific way?

These are DELIBERATELY DIFFERENT mutations from
`test_afde_2604_cross_entry_point_confused_deputy.py` (CD-1/CD-2, which attack the
`execute()` vs `execute_admitted()` method choice on an ALREADY-CONSTRUCTED
`ConsequenceBoundary`, and drive the real Typer `app` via `CliRunner` for the CLI
side). This file never disputes that `sa2a/cli.py hook reflex`, invoked as a CLI
command, is secure by default -- it is. It asks whether a caller who never goes
through Click's own CLI dispatch (a library import, a script, a different command
wrapper) can reach the exact same real actuation with admission silently absent,
without ever passing `--skip-admission-check` or asking for anything resembling
"skip".

  MUTATION DW-1 -- direct-library-construction bypass: `ReactiveSemanticLoop` and
    `ConsequenceBoundary` constructed directly, exactly as any library consumer of
    `autofde_lab.sa2a` could (never touching `sa2a/cli.py`'s `app` or `hook_reflex`
    at all), using ONLY their own bare default constructor arguments
    (`ConsequenceBoundary(...)` with no `require_admission=`; `ReactiveSemanticLoop
    (...)` with no `admission_pipeline=`). Real `AuthorityBroker`/`AuthorityGrant`,
    real `KnowledgeHookEngine` + hand-built hook, real disk actuator/verifier/store.
    Event content carries NO relational admission-binding triple at all (arbitrary,
    unrelated assertion) -- if the fence is real at the library level, this should
    still be refused; if it is only real at the CLI-wiring level, real actuation
    reaches EXECUTED.

  MUTATION DW-2 -- Typer `OptionInfo` sentinel-default bypass on a direct function
    call: `sa2a/cli.py`'s real, unmodified, shipped `hook_reflex` function object is
    imported and called directly as a plain Python function (never through
    `typer.testing.CliRunner` or Click's own argument-binding machinery), supplying
    real values for every parameter EXCEPT `skip_admission_check` -- exactly what a
    caller would do who has never heard of that flag and is relying on the function's
    own documented "SECURE BY DEFAULT" behavior. `typer.Option(False, ...)` is not the
    literal Python default `False` in the function's own `__defaults__`/signature; it
    is a `typer.models.OptionInfo` sentinel object, and `bool(OptionInfo(...))` is
    `True` (confirmed live this session: `not typer.Option(False, ...)` evaluates to
    `False`). Click substitutes the real, intended default only while parsing a CLI
    invocation; calling the underlying function object directly skips that
    substitution entirely. So `require_admission=not skip_admission_check` becomes
    `require_admission=False` and `admission_pipeline=None if skip_admission_check
    else AdmissionPipeline()` becomes `admission_pipeline=None` -- the exact fully
    permissive configuration `--skip-admission-check` produces -- triggered by NOT
    passing anything, on the exact real shipped function, with no CLI flag, no
    `--skip-admission-check` string anywhere in the call, and no way for the caller to
    have "opted out" of anything by name.

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real `AuthorityBroker`/`AuthorityGrant`, real `KnowledgeHookEngine`, real
  `ReactiveSemanticLoop`, real `ConsequenceBoundary`.
- Real `RealDiskJournalActuator`/`IndependentDiskJournalVerifier` (genuine physical
  disk I/O) and a real `DurableDiskReceiptStore`, the same real collaborators
  `test_afde_2604_cross_entry_point_confused_deputy.py` and
  `test_afde_2604_fresh_mutations_qualification.py` use.
- Mutation DW-2 calls the REAL, unmodified `autofde_lab.sa2a.cli.hook_reflex` function
  object directly -- the exact same code Click dispatches to for the real `sa2a hook
  reflex` CLI command, not a reimplementation or a hand-copied construction.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in
  this file. `pytest`'s built-in `capsys` fixture (stdout capture, not a test double
  for any collaborator under test) is used only to read the real JSON `hook_reflex`
  itself prints via `typer.echo`.

RESULT (this session, reviewer lens -- NOT patched; per this task's own instruction,
a survived mutation here is reported, not fixed):

  MUTATION DW-1 -- SURVIVED (real, disclosed-but-real gap). Real actuation reaches
    `TerminalReceiptState.EXECUTED` for unrelated, unbound event content, with zero
    `AdmissionResult` ever computed, whenever `ReactiveSemanticLoop`/
    `ConsequenceBoundary` are constructed directly with their own bare defaults. This
    matches the sibling architecture-fix session's own stated scope note
    ("`ReactiveSemanticLoop`'s own class-level `admission_pipeline` default remains
    `None` for library-level backward compatibility... 7+ pre-existing call sites
    rely on it") -- i.e. it is a NAMED, deliberate scope boundary, not something the
    fix silently missed. Reported here because the task asked specifically to try
    "a code path that constructs the loop without going through cli.py real command
    wiring at all," and this is exactly that path, verified for real: "secure by
    default" is a property of the one `sa2a/cli.py hook_reflex` command's own
    construction choices, never of the underlying library classes themselves. Any
    other command, script, test helper, or future integration that constructs
    `ConsequenceBoundary`/`ReactiveSemanticLoop` directly (there is no dedicated
    "secure" factory/classmethod exposed) reproduces the fully permissive
    `candidate -> authority -> DO` path with zero code changes required and zero
    warning at construction time.

  MUTATION DW-2 -- SURVIVED when first found (real, not previously disclosed
    anywhere in the architecture-fix session's own notes or in `sa2a/cli.py`'s own
    docstrings/module comments); DEFEATED as of a later closure pass (see below).
    Calling the real, shipped `hook_reflex` function object directly (bypassing
    Click's own parameter-binding) used to silently reproduce the exact
    `--skip-admission-check` permissive configuration, even though the caller never
    named that flag, never passed anything truthy for it, and had no way to discover
    from `hook_reflex`'s own Python-level signature that omitting an argument here
    meant "skip the fence" rather than "use its documented default." This was
    precisely "an opt-out flag that is easier to trigger than intended" -- triggered
    by DOING NOTHING, on the exact production code path, for any caller (a test
    helper, a notebook, a future FastAPI/MCP wrapper that imports Typer command
    functions directly instead of shelling out to the CLI) that does not happen to go
    through `typer.testing.CliRunner` or a real subprocess invocation of the CLI.

DW-1 is exercised here as a regression fixture for visibility, not as a claim that it
was silently reintroduced by any later session -- it was already named by the
architecture-fix session, and it remains an intentional, disclosed scope boundary
(flipping `ConsequenceBoundary`'s/`ReactiveSemanticLoop`'s own class-level defaults
to secure-by-default is a real, wider breaking change affecting every existing
library-level call site, not attempted here or anywhere else in this repo without
an explicit decision to make it).

DW-2 closure (later pass, this repo): `sa2a/cli.py`'s `hook_reflex` now resolves
`skip_admission_check` defensively at the top of its body -- a non-`bool` value there
can only be Click's own unsubstituted `OptionInfo` sentinel (a real CLI invocation, or
any caller passing a real bool, is unaffected), and is resolved to the sentinel's own
configured default (`False`) rather than trusted as truthy. This is a narrow,
non-breaking bug fix, not the wider DW-1 default-flip: it makes "argument omitted"
mean "use the documented secure default" for THIS one parameter, on THIS one function,
regardless of call style -- it does not change `ConsequenceBoundary`'s or
`ReactiveSemanticLoop`'s own class-level defaults, and does not close DW-1.
`test_mutation_dw2_...` below now asserts the corrected, refused outcome.
"""

from __future__ import annotations

import json
from pathlib import Path

from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import ConsequenceBoundary, ExecutionEnvelope
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.model import HookEffectKind, HookEventTrigger, KnowledgeHookDefinition
from autofde_lab.sa2a.hooks.reactive_loop import ReactiveSemanticLoop


# ---------------------------------------------------------------------------
# MUTATION DW-1: direct-library-construction bypass (no cli.py involved at all)
# ---------------------------------------------------------------------------


def test_mutation_dw1_direct_library_construction_bypasses_admission_entirely(
    tmp_path: Path,
) -> None:
    """`ReactiveSemanticLoop`/`ConsequenceBoundary` constructed with ONLY their own
    bare default arguments -- no `require_admission=`, no `admission_pipeline=` --
    reach real EXECUTED actuation for event content that binds nothing to the exact
    action/target being actuated. `sa2a/cli.py` (`app`, `hook_reflex`) is never
    imported or touched anywhere in this test: this is the library surface any
    consumer of `autofde_lab.sa2a` sees, independent of any CLI wiring.
    """
    action_iri = "urn:action:freeze_credit"
    target_resource = "urn:cap:credit:freeze"
    actor_id = "urn:agent:library-caller"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-dw1",
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )

    journal = tmp_path / "dw1" / "journal.json"
    store = DurableDiskReceiptStore(tmp_path / "dw1" / "receipts")
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)

    # No `require_admission=` passed -- this instance uses the class's own default.
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=store,
    )
    assert boundary.require_admission is False, (
        "Precondition: ConsequenceBoundary's own bare default is require_admission=False."
    )

    engine = KnowledgeHookEngine()
    engine.register_hook(
        KnowledgeHookDefinition(
            iri="http://example.org/hook/dw1_direct",
            name="dw1_direct_hook",
            on=HookEventTrigger.ASSERT,
            effect=HookEffectKind.GROUND_ACTION,
            action_iri=action_iri,
            target_capability_iri=target_resource,
            goal_iri="urn:goal:dw1",
        )
    )

    # No `admission_pipeline=` passed -- this instance uses the class's own default.
    loop = ReactiveSemanticLoop(
        hook_engine=engine,
        authority_broker=broker,
        consequence_boundary=boundary,
        max_cascade_depth=2,
    )
    assert loop.admission_pipeline is None, (
        "Precondition: ReactiveSemanticLoop's own bare default is admission_pipeline=None."
    )

    # Event content is a real, unrelated triple -- it never asserts
    # <action_iri> <urn:autofde-lab:targetResource> <target_resource> anywhere, and no
    # AdmissionResult of any kind is ever computed on this path.
    event_ttl = '<urn:test:unrelated_subject> <urn:test:unrelated_predicate> "unrelated_value" .'

    trace = loop.run_reflex_cycle(
        base_ttl="",
        initial_event_ttl=event_ttl,
        actor_id=actor_id,
        delta_generator=lambda r: "",
    )

    assert len(trace.steps) == 1, f"Expected exactly one reflex step, got {trace.steps!r}"
    step = trace.steps[0]
    assert len(step.final_receipts) == 1, f"Expected exactly one final receipt, got {step!r}"
    final = step.final_receipts[0]

    # SURVIVED: real actuation, real disk journal write, zero admission ever computed.
    assert final.state == TerminalReceiptState.EXECUTED, (
        "MUTATION DW-1 DEFEATED (unexpected -- would mean the library-level default "
        f"itself now refuses without admission): final receipt was {final.to_dict()!r}"
    )
    assert journal.exists(), (
        "MUTATION DW-1 DEFEATED (unexpected): real disk actuation never occurred."
    )
    assert actuator.call_count == 1
    assert verifier.verification_count >= 1


# ---------------------------------------------------------------------------
# MUTATION DW-2: Typer OptionInfo sentinel-default bypass, real hook_reflex function
# ---------------------------------------------------------------------------


def test_mutation_dw2_calling_real_hook_reflex_function_directly_defaults_to_skip(
    tmp_path: Path, capsys
) -> None:
    """DEFEATED (closure pass): calling the REAL, shipped
    `autofde_lab.sa2a.cli.hook_reflex` function object directly (never through
    `typer.testing.CliRunner`, never through Click's own CLI dispatch), with every
    parameter supplied EXCEPT `skip_admission_check`, now correctly enforces the
    admission fence rather than silently reproducing `--skip-admission-check`.

    `hook_reflex`'s own Python-level *signature default* for `skip_admission_check`
    is still a truthy `typer.models.OptionInfo` sentinel (confirmed live below,
    unchanged -- that premise was never the bug, and Typer's decorator machinery
    still needs it for real CLI argument parsing to work); what changed is that the
    function body now resolves a non-`bool` value defensively to the sentinel's own
    configured default (`False`) instead of trusting `bool(OptionInfo(...))`
    (always `True`).
    """
    import typer

    from autofde_lab.sa2a.cli import hook_reflex

    # The load-bearing premise for this mutation is still real and unchanged: the
    # function's OWN signature default for skip_admission_check is a truthy
    # sentinel, never the boolean False a CLI invocation would supply. The fix is in
    # the function BODY's runtime resolution of that sentinel, not in the signature.
    import inspect

    sig = inspect.signature(hook_reflex)
    raw_default = sig.parameters["skip_admission_check"].default
    assert isinstance(raw_default, typer.models.OptionInfo), (
        f"Expected hook_reflex's own default for skip_admission_check to be a "
        f"typer.models.OptionInfo sentinel (confirming Click has not yet substituted "
        f"the real default), got {raw_default!r} of type {type(raw_default)!r}."
    )
    assert bool(raw_default) is True, (
        "Expected the OptionInfo sentinel to still be truthy (bool(OptionInfo(...)) "
        "is True for this typer version) -- confirming the fix works by resolving "
        "the sentinel explicitly in the function body, not by relying on its "
        "truthiness changing."
    )

    action_iri = "urn:action:freeze_credit"
    target_resource = "urn:cap:credit:freeze"
    actor_id = "urn:agent:direct-function-caller"

    # Real, unrelated event content -- no admission-binding triple, exactly as DW-1.
    event_ttl = '<urn:test:unrelated_subject> <urn:test:unrelated_predicate> "unrelated_value" .'

    # The real, shipped function, called directly -- exactly as any non-CLI caller
    # (a script, a notebook, a future in-process wrapper) would import and call it.
    # `skip_admission_check` is intentionally NEVER passed here -- the caller is not
    # asking to skip anything.
    hook_reflex(
        base_ttl="# dw2 base graph (empty string is a directory path via Path('').exists())\n",
        event_ttl=event_ttl,
        max_depth=2,
        actor_id=actor_id,
        action_iri=action_iri,
        target_resource=target_resource,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["ok"] is True
    assert payload["steps_count"] == 1, f"Unexpected trace shape: {payload!r}"
    receipt_states = payload["steps"][0]["receipt_states"]

    # DEFEATED: the unrelated/unbound event content is now correctly REFUSED --
    # calling the real production function directly and omitting an argument the
    # caller never knew existed no longer silently opts out of the admission fence.
    assert receipt_states == ["REFUSED"], (
        "MUTATION DW-2 SURVIVED (regression -- calling hook_reflex directly without "
        f"skip_admission_check reproduced the permissive path again): {payload!r}"
    )
