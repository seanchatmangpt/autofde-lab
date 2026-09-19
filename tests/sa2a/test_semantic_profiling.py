"""Checkpoint for the SA2A semantic profiling observation boundary.

This is deliberately not named a Chicago test: it exercises real repository
OCEL models and the real profiling implementation, but no kernel/eBPF
AgentSight source. It proves deterministic repo-local projection/folding only.
"""

from decimal import Decimal

import pytest

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import OcelAttributeValue, OcelObject
from autofde_lab.sa2a.profiling import (
    MissingProfileMeasure,
    MissingSemanticPath,
    ProfileView,
    fold_operations,
    operations_from_ocel,
)


def _log() -> OcelLog:
    log = OcelLog.new(
        objects=(
            OcelObject("session-1", "AgentSession"),
            OcelObject("session-2", "AgentSession"),
        )
    )
    log = log.append_event(
        "e1",
        "tool.execute",
        [("session-1", "session")],
        timestamp_ns=1,
        attributes={
            "session": OcelAttributeValue.string("session-1"),
            "agent": OcelAttributeValue.string("agent-a"),
            "tokens": OcelAttributeValue.integer(100),
            "duration_ms": OcelAttributeValue.integer(20),
        },
    )
    log = log.append_event(
        "e2",
        "system.process",
        [("session-2", "session")],
        timestamp_ns=2,
        attributes={
            "session": OcelAttributeValue.string("session-2"),
            "agent": OcelAttributeValue.string("agent-b"),
            "tokens": OcelAttributeValue.integer(200),
            "duration_ms": OcelAttributeValue.integer(30),
        },
    )
    return log.append_event(
        "e3",
        "tool.verify",
        [("session-2", "session")],
        timestamp_ns=3,
        attributes={
            "session": OcelAttributeValue.string("session-2"),
            "agent": OcelAttributeValue.string("agent-b"),
            "tokens": OcelAttributeValue.integer(50),
            "duration_ms": OcelAttributeValue.integer(100),
        },
    )


def _operations():
    return operations_from_ocel(
        _log(),
        semantic_paths={
            "e1": ("release v26.9.18", "diagnose authentication"),
            "e2": ("release v26.9.18", "diagnose authentication"),
            "e3": ("release v26.9.18", "verify endpoint"),
        },
        dimension_fields={"session": "session", "agent": "agent"},
        measure_fields={"tokens": "tokens", "duration_ms": "duration_ms"},
        source="agentsight-ocel",
    )


def test_semantic_responsibility_folds_across_sessions_and_conserves_weight():
    profile = fold_operations(
        _operations(),
        ProfileView(measure="tokens", stack_fields=("semantic_path",)),
    )

    assert profile.total_weight == Decimal("350")
    assert profile.selected_operations == 3
    assert profile.weight_for(
        ("release v26.9.18", "diagnose authentication")
    ) == Decimal("300")
    assert profile.weight_for(
        ("release v26.9.18", "verify endpoint")
    ) == Decimal("50")
    assert (
        sum((row.weight for row in profile.rows), Decimal(0))
        == profile.total_weight
    )


def test_same_operations_replay_under_another_additive_measure():
    profile = fold_operations(
        _operations(),
        ProfileView(measure="duration_ms", stack_fields=("semantic_path",)),
    )

    assert profile.total_weight == Decimal("150")
    assert profile.weight_for(
        ("release v26.9.18", "diagnose authentication")
    ) == Decimal("50")
    assert profile.weight_for(
        ("release v26.9.18", "verify endpoint")
    ) == Decimal("100")


def test_query_time_projection_uses_explicit_dimensions_without_rewriting():
    profile = fold_operations(
        _operations(),
        ProfileView(
            measure="tokens",
            stack_fields=("semantic_path", "session"),
        ),
    )

    assert profile.weight_for(
        (
            "release v26.9.18",
            "diagnose authentication",
            "session-1",
        )
    ) == Decimal("100")
    assert profile.weight_for(
        (
            "release v26.9.18",
            "diagnose authentication",
            "session-2",
        )
    ) == Decimal("200")


def test_missing_semantic_identity_fails_closed_instead_of_guessing():
    with pytest.raises(MissingSemanticPath):
        operations_from_ocel(
            _log(),
            semantic_paths={"e1": ("known",)},
            measure_fields={"tokens": "tokens"},
        )


def test_requested_measure_must_be_explicit_on_selected_operations():
    operations = operations_from_ocel(
        _log(),
        semantic_paths={
            "e1": ("task",),
            "e2": ("task",),
            "e3": ("task",),
        },
    )

    with pytest.raises(MissingProfileMeasure):
        fold_operations(
            operations,
            ProfileView(measure="tokens"),
        )


def test_profile_is_observational_evidence_not_actuation_authority():
    profile = fold_operations(
        _operations(),
        ProfileView(measure="operation_count"),
    )

    assert profile.consequence_class == "OBSERVATIONAL"
    assert profile.authorizes_actuation is False
    assert profile.to_collapsed_stacks()
