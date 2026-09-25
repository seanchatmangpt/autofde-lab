"""Pure tests for the TLA+ projection extensions the TLC court depends on.

Real IR objects and real rendered text only; no tool execution here.
"""

from __future__ import annotations

import dataclasses

import pytest

from autofde_lab.iec.brce_mutants import EXPECTED_VIOLATION, BrceMutant, brce_mutant
from autofde_lab.iec.brce_reference import brce_reference_system
from autofde_lab.iec.formal import make_tlc_intent
from autofde_lab.iec.protocol_ir import (
    Fairness,
    Invariant,
    StateVariable,
    TransitionSystem,
    UnboundConstantError,
    make_action,
)
from autofde_lab.iec.tla_projection import render_cfg, render_tla


def _counter(**overrides) -> TransitionSystem:
    base = dict(
        name="Counter",
        variables=(StateVariable("x", "0"),),
        actions=(make_action("Inc", guard="x < Max", updates={"x": "x + 1"}),),
        invariants=(Invariant("Bounded", "x <= Max"),),
        constants=("Max",),
        constant_values=(("Max", "3"),),
    )
    base.update(overrides)
    return TransitionSystem(**base)


def test_reference_spec_carries_weak_fairness_conjunct() -> None:
    projection = render_tla(brce_reference_system())
    assert (
        "vars == <<phase, authority, receipt, verified, standing, consequenceCount>>"
        in projection.tla
    )
    assert "Spec == Init /\\ [][Next]_vars /\\ WF_vars(Next)" in projection.tla
    assert projection.warnings == ()


def test_liveness_without_fairness_is_warned_not_hidden() -> None:
    projection = render_tla(brce_mutant(BrceMutant.NO_FAIRNESS))
    assert "WF_vars" not in projection.tla
    assert projection.warnings == ("LIVENESS_WITHOUT_FAIRNESS",)


def test_unbound_constant_is_refused_at_construction() -> None:
    with pytest.raises(UnboundConstantError) as info:
        _counter(constant_values=())
    assert "UNBOUND_CONSTANT" in str(info.value)
    assert info.value.code == "UNBOUND_CONSTANT"


def test_value_for_undeclared_constant_is_refused() -> None:
    with pytest.raises(ValueError, match="undeclared constants"):
        _counter(constant_values=(("Max", "3"), ("Min", "0")))


def test_constants_and_constraints_render_into_cfg() -> None:
    system = _counter(
        state_constraints=(Invariant("SmallX", "x <= 10"),),
        fairness=(Fairness("SF", "Inc"),),
    )
    projection = render_tla(system)
    assert "CONSTANTS Max" in projection.tla
    assert "SmallX ==\n    x <= 10" in projection.tla
    assert "SF_vars(Inc)" in projection.tla
    assert projection.cfg == (
        "SPECIFICATION Spec\nCONSTANT Max = 3\nCONSTRAINT SmallX\nINVARIANT Bounded\n"
    )


def test_single_property_cfg_selects_exactly_one_property() -> None:
    system = brce_reference_system()
    cfg = render_cfg(system, invariants=("AtMostOneConsequence",), properties=())
    assert cfg == "SPECIFICATION Spec\nINVARIANT AtMostOneConsequence\n"
    live = render_cfg(system, invariants=(), properties=("AdmittedEventuallyTerminal",))
    assert live == "SPECIFICATION Spec\nPROPERTY AdmittedEventuallyTerminal\n"
    with pytest.raises(ValueError, match="unknown invariant"):
        render_cfg(system, invariants=("Nope",))


def test_fairness_rejects_unknown_kind_and_action() -> None:
    with pytest.raises(ValueError):
        Fairness("XF")
    with pytest.raises(ValueError, match="unknown action"):
        _counter(fairness=(Fairness("WF", "Dec"),))


def test_every_mutant_differs_from_reference_and_names_a_declared_property() -> None:
    reference = brce_reference_system()
    for kind in BrceMutant:
        mutant = brce_mutant(kind)
        assert mutant.system_id != reference.system_id
        declared = {i.name for i in mutant.invariants} | {
            p.name for p in mutant.liveness
        }
        assert EXPECTED_VIOLATION[kind] in declared
    duplicate = brce_mutant(BrceMutant.DUPLICATE_CONSEQUENCE)
    assert "CONSTRAINT ConsequenceBound" in render_tla(duplicate).cfg


def test_do_without_authority_still_declares_authority_required() -> None:
    mutant = brce_mutant(BrceMutant.DO_WITHOUT_AUTHORITY)
    actuate = next(a for a in mutant.actions if a.name == "Actuate")
    # Declaring authority is not enforcing it: the static gap check passes,
    # which is exactly why the TLC court must refute it dynamically.
    assert actuate.authority_required and mutant.authority_gaps() == ()
    assert "authority" not in actuate.guard


def test_tlc_intent_with_jar_pins_classpath() -> None:
    projection = render_tla(brce_reference_system())
    intent = make_tlc_intent(
        projection,
        tool_version="2.19",
        executable_digest="sha256:" + "0" * 64,
        module_path="BRCEReference.tla",
        config_path="BRCEReference.cfg",
        jar_path="tla2tools.jar",
        flags=("-tool", "-workers", "1"),
    )
    assert intent.argv == (
        "java",
        "-cp",
        "tla2tools.jar",
        "tlc2.TLC",
        "-tool",
        "-workers",
        "1",
        "-config",
        "BRCEReference.cfg",
        "BRCEReference.tla",
    )
    legacy = dataclasses.replace(intent, argv=("java", "tlc2.TLC"))
    assert legacy.authority == "NONE"
