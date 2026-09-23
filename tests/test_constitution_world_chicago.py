# Chicago-style, no mocks: see .claude/rules/testing-chicago-style.md
"""Chicago-style test for the real ggen-manufactured module `autofde_lab.constitution.world`.

No mocks: this test performs a real import of the manufactured module, constructs real
instances of every dataclass listed in `world.__all__` with every real field explicitly
filled with representative (non-default) values, and asserts on the real constructed
instance's real field values. It also verifies frozen-dataclass immutability by attempting
a real mutation and catching the real `dataclasses.FrozenInstanceError` it raises.

Source ontology: `ontology/world.ttl` (manufactured into
`src/autofde_lab/constitution/world.py` by `ggen sync run`; see that module's own docstring
for the manufacture provenance note).

Migrated 2026-09-16: `ggen.toml`'s `constitution-world` rule was flipped from
`mode = "Create"` to `mode = "Overwrite"` (see
`docs/jira/v26.9.16/AFDE-2608-projected-ephemeral-ontology-invariant.md` for the full
provenance) and a real `ggen sync run` was executed, regenerating `world.py` against the
*current* merged ontology graph for the first time since 2026-08-08. `ontology/
world-transformation-taxonomy.ttl` (commit `e0d82367`, 2026-08-11) types five individuals
(`obs_api_instance_count`, `obs_sql_primary_count`, `obs_db_publicly_reachable`,
`obs_p95_latency_ms`, `obs_failure_budget_exhausted`) as `a afl:AdmittedObservation`, and
`templates/constitution_module.py.tera` renders any class with bound individuals as a
`StandingValue` str-Enum instead of a `@dataclass` (the same shared-template mechanism
already exercised by `tests/test_constitution_standing_chicago.py` and
`tests/test_constitution_process_chicago.py`). The real `AdmittedObservation` dataclass
and its `derived_from_observation` field no longer exist in the manufactured module; this
file was updated to assert the new, real `StandingValue` enum shape rather than pin the
now-superseded dataclass shape.
"""

from __future__ import annotations

import dataclasses
import enum

import pytest

from autofde_lab.constitution import world


def test_world_module_exports_expected_names():
    """The real manufactured module exposes exactly the six constitution names -- five
    frozen dataclasses plus the `StandingValue` enum that replaced `AdmittedObservation`
    once `ontology/world-transformation-taxonomy.ttl`'s five bound individuals were picked
    up by a real `ggen sync run` under `mode = "Overwrite"`."""
    assert set(world.__all__) == {
        "StandingValue",
        "Environment",
        "Observation",
        "ObservationAdmission",
        "World",
        "WorldState",
    }


def test_standing_value_is_enum_subclass():
    assert issubclass(world.StandingValue, enum.Enum)


def test_standing_value_enum_carries_the_five_admitted_observation_individuals():
    """The manufactured `StandingValue` enum (the shared template's own name for any
    vocabulary-individual block, per `templates/constitution_module.py.tera`) carries
    exactly the five `afl:AdmittedObservation` individuals
    `ontology/world-transformation-taxonomy.ttl` declares -- real observation identifiers,
    not guessed values."""
    expected_names = {
        "obs_api_instance_count",
        "obs_db_publicly_reachable",
        "obs_failure_budget_exhausted",
        "obs_p95_latency_ms",
        "obs_sql_primary_count",
    }
    actual_names = {member.name for member in world.StandingValue}
    assert actual_names == expected_names
    assert len(world.StandingValue) == 5

    for name in expected_names:
        member = getattr(world.StandingValue, name)
        assert member.value == name
        assert isinstance(member, str)


def test_environment_real_construction():
    cls = getattr(world, "Environment")
    instance = cls()
    assert isinstance(instance, world.Environment)
    assert dataclasses.fields(instance) == ()


def test_observation_real_construction_and_fields():
    cls = getattr(world, "Observation")
    instance = cls(
        about_state=("urn:example:world-state-1",),
        observed_from=("urn:example:world-1",),
    )
    assert instance.about_state == ("urn:example:world-state-1",)
    assert instance.observed_from == ("urn:example:world-1",)


def test_observation_admission_real_construction_and_fields():
    cls = getattr(world, "ObservationAdmission")
    instance = cls(admits_observation=("urn:example:admitted-observation-1",))
    assert instance.admits_observation == ("urn:example:admitted-observation-1",)


def test_world_real_construction():
    cls = getattr(world, "World")
    instance = cls()
    assert isinstance(instance, world.World)
    assert dataclasses.fields(instance) == ()


def test_world_state_real_construction():
    cls = getattr(world, "WorldState")
    instance = cls()
    assert isinstance(instance, world.WorldState)
    assert dataclasses.fields(instance) == ()


def test_all_world_dataclass_names_are_frozen_dataclasses_constructible_with_real_fields():
    """For every name in `world.__all__` that is a frozen dataclass (i.e. excluding the
    `StandingValue` enum, which the shared template renders for any ontology class with
    bound individuals rather than as a `@dataclass` -- see the module-level migration
    note above), get the class via getattr, construct a real instance with all real
    fields explicitly filled with representative values, and assert on the real
    constructed instance's real field values."""
    representative_tuple_fields = {
        "about_state": ("urn:example:world-state-1",),
        "observed_from": ("urn:example:world-1",),
        "admits_observation": ("urn:example:admitted-observation-1",),
    }

    dataclass_names = [name for name in world.__all__ if name != "StandingValue"]
    assert dataclass_names == [
        "Environment",
        "Observation",
        "ObservationAdmission",
        "World",
        "WorldState",
    ]

    for name in dataclass_names:
        cls = getattr(world, name)
        assert dataclasses.is_dataclass(cls)

        field_defs = dataclasses.fields(cls)
        kwargs = {}
        for field in field_defs:
            assert field.name in representative_tuple_fields, (
                f"unexpected field {field.name!r} on {name}; "
                "test must be updated to supply a representative value"
            )
            kwargs[field.name] = representative_tuple_fields[field.name]

        instance = cls(**kwargs)

        for field in field_defs:
            assert getattr(instance, field.name) == kwargs[field.name]

    # StandingValue itself is real -- an Enum, not a dataclass -- confirmed explicitly
    # so this test's exclusion above is a documented fact, not a silent skip.
    assert not dataclasses.is_dataclass(world.StandingValue)
    assert issubclass(world.StandingValue, enum.Enum)


def test_observation_is_frozen_and_mutation_raises():
    instance = world.Observation(
        about_state=("urn:example:world-state-1",),
        observed_from=("urn:example:world-1",),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.about_state = ("urn:example:world-state-mutated",)
    assert instance.about_state == ("urn:example:world-state-1",)


def test_world_is_frozen_and_mutation_raises():
    """World has no fields; confirm frozen enforcement still fires for an
    arbitrary attribute assignment attempt on a no-field dataclass."""
    instance = world.World()
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.nonexistent_field = "anything"  # type: ignore[attr-defined]
