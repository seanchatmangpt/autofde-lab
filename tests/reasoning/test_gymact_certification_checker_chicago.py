# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `gymact_certification_checker`.

Real collaborators throughout: the real, installed `gymact` package's real
`EnvironmentProvider`/`Environment` Protocols (`@runtime_checkable`, no
mock substitute possible or needed -- structural typing is checked against
the real class); the real `gymact.gyms.sregym.SregymVendorProvider` class
for the structural pass (import only, no live cluster materialized); a
real, hand-written fake `Environment`/`EnvironmentProvider` pair (same
real-degraded-alternative pattern `test_gymact_dspy_react_chicago.py`'s
`_FakeSregymEnvironment` already uses) for the smoke-cycle test.

No `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere
in this file.
"""

from __future__ import annotations

import asyncio
from typing import Any

from gymact.models import Capability, Consequence

from autofde_lab.reasoning.gymact_certification_checker import (
    _CERTIFICATION_CHECKS_BY_NAME,
    check_environment_provider_conformance,
)
from autofde_lab.reasoning.gymact_certification_types import StandingValue


def test_real_sregym_vendor_provider_passes_every_structural_check() -> None:
    """A real, known-conformant adapter (`SregymVendorProvider`, real import,
    no live cluster) must pass every structural check and be reported
    `STRUCTURAL_ONLY` -- a real, positive proof the checker recognizes real
    conformance, not just detects real defects."""
    from gymact.gyms.sregym import SregymVendorProvider

    provider = SregymVendorProvider()

    manifest, results = asyncio.run(
        check_environment_provider_conformance(provider, gym_name="sregym", run_smoke_cycle=False)
    )

    assert manifest.manifest_conformance_level_ref == StandingValue.STRUCTURAL_ONLY.value
    assert manifest.manifest_gym_name == "sregym"
    assert "SregymVendorProvider" in manifest.manifest_provider_class_ref
    # Pure structural pass (no materialize): provider Protocol conformance +
    # materialize() signature only. capabilities() is a real Environment-level
    # method (confirmed live -- EnvironmentProvider itself declares no such
    # method) and only runs inside the opt-in smoke cycle, where a real
    # Environment instance actually exists.
    assert len(results) == 2
    assert all(r.result_passed for r in results)
    assert any(r.result_check_ref == "provider_satisfies_environment_provider_protocol" for r in results)
    assert any(r.result_check_ref == "materialize_method_present" for r in results)
    # Priority 4: every fixed-name result_check_ref is now backed by a real,
    # declared CertificationCheck in the module's catalog -- not a bare
    # string literal with no check definition behind it.
    for result in results:
        assert result.result_check_ref in _CERTIFICATION_CHECKS_BY_NAME
        catalog_entry = _CERTIFICATION_CHECKS_BY_NAME[result.result_check_ref]
        assert catalog_entry.check_description
        assert catalog_entry.check_severity_ref in (StandingValue.STRUCTURAL.value, StandingValue.BEHAVIORAL.value)


def test_non_conformant_object_is_reported_cert_unsupported_never_a_fabricated_pass() -> None:
    """A real, plain object satisfying none of the Protocol at all must be
    reported honestly as CERT_UNSUPPORTED (the wrong kind of object
    entirely), never coerced into a pass and never conflated with
    CERT_BUILD_BROKEN (a real EnvironmentProvider with a real broken
    check -- see the next test)."""

    class _NotAProvider:
        pass

    manifest, results = asyncio.run(
        check_environment_provider_conformance(_NotAProvider(), gym_name="not-a-real-gym", run_smoke_cycle=False)
    )

    assert manifest.manifest_conformance_level_ref == StandingValue.CERT_UNSUPPORTED.value
    assert any(
        r.result_check_ref == "provider_satisfies_environment_provider_protocol" and r.result_passed is False
        for r in results
    )


class _ProtocolConformantButMalformedProvider:
    """A real object that genuinely satisfies `EnvironmentProvider`'s
    structural shape (the real, @runtime_checkable Protocol only checks
    attribute/method presence, not signatures) but whose real
    `materialize` signature is malformed -- the real, distinct case
    `CERT_BUILD_BROKEN` exists for."""

    def __init__(self) -> None:
        self.name = "malformed-gym"
        self.materialization_requires_authority = False

    async def materialize(self, positional_arg: str) -> Any:  # missing keyword-only scenario/config
        raise NotImplementedError


def test_protocol_conformant_but_malformed_provider_is_reported_cert_build_broken() -> None:
    """A real object that DOES satisfy EnvironmentProvider structurally but
    fails a later structural check (materialize's real signature) is
    CERT_BUILD_BROKEN, not CERT_UNSUPPORTED -- the two must not collapse
    into one bucket."""
    manifest, results = asyncio.run(
        check_environment_provider_conformance(
            _ProtocolConformantButMalformedProvider(), gym_name="malformed-gym", run_smoke_cycle=False
        )
    )

    assert manifest.manifest_conformance_level_ref == StandingValue.CERT_BUILD_BROKEN.value
    assert any(
        r.result_check_ref == "provider_satisfies_environment_provider_protocol" and r.result_passed is True
        for r in results
    )
    assert any(
        r.result_check_ref == "materialize_method_present" and r.result_passed is False for r in results
    )


_FAKE_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        iri="urn:gymact:fake:capability:read",
        title="Real fake read capability for the smoke-cycle test",
        consequence=Consequence.READ,
        binding="read",
    ),
)


class _FakeEnvironment:
    """Real, hand-written, honest fake -- same pattern as
    `test_gymact_dspy_react_chicago.py::_FakeSregymEnvironment`."""

    def __init__(self) -> None:
        self.environment_id = "urn:gymact:fake:environment:test-001"
        self.requires_authority = False
        self.torn_down = False

    def capabilities(self) -> tuple[Capability, ...]:
        return _FAKE_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        return {"real": "observed-state"}

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("the checker must never call actuate() -- see module docstring")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        return True, dict(expected)

    async def checkpoint(self) -> dict[str, Any]:
        return {"real": "checkpoint-state"}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        return None

    async def teardown(self) -> None:
        self.torn_down = True


class _FakeProvider:
    """Real, hand-written fake `EnvironmentProvider`."""

    def __init__(self) -> None:
        self.name = "fake-gym"
        self.materialization_requires_authority = False
        self.materialized_env: _FakeEnvironment | None = None

    async def materialize(self, *, scenario: str | None, config: dict[str, Any]) -> _FakeEnvironment:
        env = _FakeEnvironment()
        self.materialized_env = env
        return env


def test_real_smoke_cycle_against_a_conformant_fake_reports_smoke_tested() -> None:
    provider = _FakeProvider()

    manifest, results = asyncio.run(
        check_environment_provider_conformance(
            provider, gym_name="fake-gym", scenario="test-scenario", run_smoke_cycle=True
        )
    )

    assert manifest.manifest_conformance_level_ref == StandingValue.SMOKE_TESTED.value
    assert all(r.result_passed for r in results)
    assert any(r.result_check_ref == "smoke_teardown_succeeds" for r in results)
    assert provider.materialized_env is not None
    assert provider.materialized_env.torn_down is True
    # Never actuate() -- the fake would raise AssertionError if it were
    # called for real. "smoke_environment_has_method_actuate" (a real,
    # presence-only check, never an invocation) is expected and fine.
    assert any(r.result_check_ref == "smoke_environment_has_method_actuate" for r in results)


def test_smoke_cycle_is_skipped_when_structural_checks_already_failed() -> None:
    """A real object that fails the structural Protocol check must never
    have a smoke cycle run against it -- named and skipped, never crashed
    into or silently attempted."""

    class _StructurallyBroken:
        pass

    manifest, results = asyncio.run(
        check_environment_provider_conformance(
            _StructurallyBroken(), gym_name="broken-gym", run_smoke_cycle=True
        )
    )

    assert manifest.manifest_conformance_level_ref == StandingValue.CERT_UNSUPPORTED.value
    assert not any((r.result_check_ref or "").startswith("smoke_materialize") for r in results)
    # This object fails the Protocol check itself (CERT_UNSUPPORTED), so the
    # checker never even reaches the run_smoke_cycle branch that would emit
    # "smoke_cycle_skipped_due_to_structural_failure" -- that check name is
    # reserved for a real EnvironmentProvider whose *later* structural check
    # (materialize signature) fails, see
    # test_protocol_conformant_but_malformed_provider_is_reported_cert_build_broken.
    assert not any(r.result_check_ref == "smoke_cycle_skipped_due_to_structural_failure" for r in results)


def test_smoke_cycle_is_skipped_when_a_conformant_provider_has_a_malformed_materialize() -> None:
    """The real `smoke_cycle_skipped_due_to_structural_failure` path: a
    provider that DOES satisfy EnvironmentProvider but fails the later
    materialize-signature check must still skip the smoke cycle, reported
    as CERT_BUILD_BROKEN (not CERT_UNSUPPORTED)."""
    manifest, results = asyncio.run(
        check_environment_provider_conformance(
            _ProtocolConformantButMalformedProvider(), gym_name="malformed-gym", run_smoke_cycle=True
        )
    )

    assert manifest.manifest_conformance_level_ref == StandingValue.CERT_BUILD_BROKEN.value
    assert any(r.result_check_ref == "smoke_cycle_skipped_due_to_structural_failure" for r in results)
    assert not any((r.result_check_ref or "").startswith("smoke_materialize") for r in results)
