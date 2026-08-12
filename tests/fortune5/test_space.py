from __future__ import annotations

from dataclasses import replace
from math import prod

import pytest

from autofde_lab.fortune5 import (
    Axis,
    CompatibilityLaw,
    FORTUNE5_SPACE,
    Option,
    StateSpace,
    pairwise_token_count,
)


def test_fortune5_upper_bound_and_axis_contract() -> None:
    assert len(FORTUNE5_SPACE.axes) == 14
    assert [axis.name for axis in FORTUNE5_SPACE.axes] == [
        "enterprise",
        "cloud",
        "geography",
        "environment",
        "cluster_profile",
        "workload",
        "traffic",
        "data_class",
        "availability",
        "release",
        "identity",
        "policy",
        "runtime_ai",
        "fault",
    ]
    assert FORTUNE5_SPACE.raw_upper_bound == prod(
        len(axis.options) for axis in FORTUNE5_SPACE.axes
    )
    assert FORTUNE5_SPACE.raw_upper_bound == 1_327_104_000


def test_mixed_radix_coordinate_access_does_not_materialize_the_space() -> None:
    first = FORTUNE5_SPACE.raw_coordinate_at(0)
    last = FORTUNE5_SPACE.raw_coordinate_at(FORTUNE5_SPACE.raw_upper_bound - 1)
    assert first.names()["enterprise"] == "enterprise-01"
    assert first.names()["fault"] == "healthy"
    assert last.names()["enterprise"] == "enterprise-05"
    assert last.names()["fault"] == "zone-loss"
    assert first.digest == FORTUNE5_SPACE.raw_coordinate_at(0).digest
    with pytest.raises(IndexError, match="REFUSED:COORDINATE_OUT_OF_RANGE"):
        FORTUNE5_SPACE.raw_coordinate_at(FORTUNE5_SPACE.raw_upper_bound)


def test_pairwise_basis_covers_every_pair_without_cartesian_materialization() -> None:
    candidates = FORTUNE5_SPACE.pairwise_candidates(candidate_limit=5_000)
    assert len(candidates) == 1_605
    expected_tokens = sum(
        len(left.options) * len(right.options)
        for index, left in enumerate(FORTUNE5_SPACE.axes)
        for right in FORTUNE5_SPACE.axes[index + 1 :]
    )
    assert expected_tokens == 2_415
    assert pairwise_token_count(candidates) == expected_tokens
    assert FORTUNE5_SPACE.raw_upper_bound / len(candidates) > 800_000


def test_pairwise_cover_is_deterministic_and_refuses_false_coverage() -> None:
    first = FORTUNE5_SPACE.pairwise_covering(candidate_limit=5_000)
    second = FORTUNE5_SPACE.pairwise_covering(candidate_limit=5_000)
    assert [scenario.digest for scenario in first] == [
        scenario.digest for scenario in second
    ]
    candidates = FORTUNE5_SPACE.pairwise_candidates(candidate_limit=5_000)
    assert pairwise_token_count(first) == pairwise_token_count(candidates)
    with pytest.raises(ValueError, match="REFUSED:PAIRWISE_COVERAGE_INCOMPLETE"):
        FORTUNE5_SPACE.pairwise_covering(candidate_limit=5_000, max_scenarios=2)


def test_same_name_parameter_smuggling_is_not_admitted() -> None:
    axis = Axis("cloud", (Option("aws"), Option("azure")))
    space = StateSpace((axis,))
    admitted = space.scenario({"cloud": "aws"})
    smuggled = replace(
        admitted,
        choices=(("cloud", Option.from_mapping("aws", {"region": "hidden"})),),
    )
    assert space.is_lawful(admitted)
    assert not space.is_lawful(smuggled)
    with pytest.raises(ValueError, match="REFUSED:OPTION_IDENTITY_NOT_ADMITTED"):
        space.scenario({"cloud": Option.from_mapping("aws", {"region": "hidden"})})


def test_compatibility_laws_fail_closed_at_admission() -> None:
    axes = (
        Axis("data", (Option("public"), Option("restricted"))),
        Axis("policy", (Option("baseline"), Option("zero-trust"))),
    )
    law = CompatibilityLaw.from_mappings(
        when={"data": "restricted"},
        require={"policy": "zero-trust"},
        reason="restricted data requires zero-trust in this bounded fixture",
    )
    space = StateSpace(axes, (law,))
    assert space.is_lawful(
        space.scenario({"data": "restricted", "policy": "zero-trust"})
    )
    assert not space.is_lawful(
        space.scenario({"data": "restricted", "policy": "baseline"})
    )

    unknown_axis = CompatibilityLaw.from_mappings(when={"ambient_authority": "yes"})
    with pytest.raises(ValueError, match="REFUSED:UNKNOWN_COMPATIBILITY_AXIS"):
        StateSpace(axes, (unknown_axis,))

    unknown_option = CompatibilityLaw.from_mappings(when={"policy": "root"})
    with pytest.raises(ValueError, match="REFUSED:UNKNOWN_COMPATIBILITY_OPTION"):
        StateSpace(axes, (unknown_option,))


def test_scenarios_have_no_actuation_authority() -> None:
    scenario = FORTUNE5_SPACE.raw_coordinate_at(7)
    assert scenario.authority == "NONE"
    assert scenario.standing == "CANDIDATE"
    assert not hasattr(scenario, "execute")
    assert not hasattr(scenario, "actuate")
    assert not hasattr(FORTUNE5_SPACE, "execute")
    assert not hasattr(FORTUNE5_SPACE, "actuate")
