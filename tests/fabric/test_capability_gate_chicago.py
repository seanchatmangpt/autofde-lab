"""Chicago-style tests for `autofde_lab.fabric.gymact_capability_gate`.

Real collaborators throughout: a real TOML manifest file on disk (both the
shipped `gymact_capabilities.toml` and, for the malformed/refusal cases, a
real temp file written by the test itself), real TOML parsing, and -- where
the exact external `gymact.gyms.sregym` package is importable -- real
`SREGYM_CAPABILITIES` `Capability` objects checked against the gate. No
`unittest.mock` / `Mock` / `patch` / `monkeypatch` anywhere in this module.

The manifest/parsing/refusal courts do not depend on the private external
gymact repository. The cross-repository courts skip individually when that
exact module is unavailable; a missing collaborator never suppresses the
local admission tests and a skip is never upgraded into cross-repo proof.
"""

from __future__ import annotations

import pytest

from autofde_lab.fabric.gymact_capability_gate import (
    DEFAULT_MANIFEST_PATH,
    CapabilityGate,
    CapabilityRefused,
)


def _real_sregym_capabilities():
    module = pytest.importorskip(
        "gymact.gyms.sregym",
        reason="real external gymact.gyms.sregym module is not available",
    )
    return module.SREGYM_CAPABILITIES


def test_default_manifest_exists_and_parses() -> None:
    """The shipped manifest is a real file that really parses."""
    assert DEFAULT_MANIFEST_PATH.exists()
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)
    assert gate.environment == "sregym"
    assert gate.allowed_names == frozenset(
        {
            "observe_cluster_state",
            "run_kubectl",
            "get_benchmark_status",
            "submit_diagnosis",
            "submit_mitigation",
        }
    )


def test_listed_capability_is_permitted() -> None:
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)
    entry = gate.entry("run_kubectl")
    assert entry.name == "run_kubectl"
    assert entry.consequence == "DO"
    assert "diagnostic" in entry.reason.lower()
    gate.check("observe_cluster_state")


def test_unlisted_capability_is_refused_with_named_error() -> None:
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)

    with pytest.raises(CapabilityRefused) as excinfo:
        gate.check("get_injected_fault")

    err = excinfo.value
    assert err.binding == "get_injected_fault"
    assert err.environment == "sregym"
    assert "get_injected_fault" not in err.allowed
    assert "run_kubectl" in err.allowed
    assert "REFUSED:CAPABILITY_NOT_IN_MANIFEST" in str(err)


def test_unlisted_capability_entry_also_refuses() -> None:
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)
    with pytest.raises(CapabilityRefused):
        gate.entry("score_submission")


def test_real_toml_file_written_to_disk_round_trips(tmp_path) -> None:
    manifest = tmp_path / "manifest.toml"
    manifest.write_text(
        """
        [gymact]
        environment = "sregym"

        [[capability]]
        name = "observe_cluster_state"
        consequence = "READ"
        reason = "test fixture"
        """,
        encoding="utf-8",
    )
    gate = CapabilityGate.from_toml(manifest)
    assert gate.allowed_names == frozenset({"observe_cluster_state"})
    gate.check("observe_cluster_state")
    with pytest.raises(CapabilityRefused):
        gate.check("run_kubectl")


def test_empty_manifest_refuses_at_load_time(tmp_path) -> None:
    manifest = tmp_path / "empty.toml"
    manifest.write_text('[gymact]\nenvironment = "sregym"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="EMPTY_CAPABILITY_MANIFEST"):
        CapabilityGate.from_toml(manifest)


def test_missing_manifest_file_raises_file_not_found(tmp_path) -> None:
    missing = tmp_path / "does_not_exist.toml"
    with pytest.raises(FileNotFoundError):
        CapabilityGate.from_toml(missing)


# ---------------------------------------------------------------------------
# Cross-repository courts. These require the real private gymact package.
# Their skips are visible and are not evidence of integration success.
# ---------------------------------------------------------------------------


def test_real_sregym_capabilities_are_all_permitted() -> None:
    capabilities = _real_sregym_capabilities()
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)
    assert len(capabilities) == 5
    for capability in capabilities:
        permitted = gate.guard_capability(capability)
        assert permitted is capability


def test_real_gymact_capability_object_with_unlisted_binding_is_refused() -> None:
    models = pytest.importorskip(
        "gymact.models", reason="real external gymact.models module is not available"
    )
    Capability = models.Capability
    Consequence = models.Consequence

    hypothetical_ground_truth_capability = Capability(
        iri="urn:gymact:sregym:capability:get_injected_fault",
        title="Read the injected fault spec (ground truth, grading-only)",
        consequence=Consequence.READ,
        binding="get_injected_fault",
    )
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)
    with pytest.raises(CapabilityRefused) as excinfo:
        gate.guard_capability(hypothetical_ground_truth_capability)
    assert excinfo.value.binding == "get_injected_fault"


def test_stale_entries_is_empty_against_real_sregym_capabilities() -> None:
    capabilities = _real_sregym_capabilities()
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)
    real_names = frozenset(c.binding for c in capabilities)
    assert gate.stale_entries(real_names) == frozenset()


def test_stale_entries_detects_an_injected_fake_entry(tmp_path) -> None:
    capabilities = _real_sregym_capabilities()
    real_names = frozenset(c.binding for c in capabilities)
    assert "get_injected_fault_TYPO_DOES_NOT_EXIST" not in real_names

    manifest = tmp_path / "manifest_with_stale_entry.toml"
    manifest.write_text(
        """
        [gymact]
        environment = "sregym"

        [[capability]]
        name = "run_kubectl"
        consequence = "DO"
        reason = "real capability"

        [[capability]]
        name = "get_injected_fault_TYPO_DOES_NOT_EXIST"
        consequence = "READ"
        reason = "stale/typo'd entry that does not exist in real gymact"
        """,
        encoding="utf-8",
    )
    gate = CapabilityGate.from_toml(manifest)
    stale = gate.stale_entries(real_names)
    assert stale == frozenset({"get_injected_fault_TYPO_DOES_NOT_EXIST"})
