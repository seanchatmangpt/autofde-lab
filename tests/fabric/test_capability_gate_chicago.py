"""Chicago courts for the reviewed AutoFDE <-> GymAct SREGym capability contract.

Local manifest/refusal courts always execute. Cross-repository courts execute
only when the exact private GymAct package is present; those skips remain
visible and are never promoted to integration proof. No mocks are used.
"""

from __future__ import annotations

import pytest

from autofde_lab.fabric.gymact_capability_gate import (
    DEFAULT_MANIFEST_PATH,
    CapabilityGate,
    CapabilityRefused,
)

EXPECTED_SREGYM_BINDINGS = frozenset(
    {
        "observe_cluster_state",
        "run_kubectl",
        "get_benchmark_status",
        "jaeger_get_services",
        "jaeger_get_operations",
        "jaeger_get_traces",
        "jaeger_get_dependency_graph",
        "loki_get_logs",
        "loki_get_labels",
        "loki_get_label_values",
        "prometheus_get_metrics",
        "prometheus_get_alerts",
        "submit_diagnosis",
        "submit_mitigation",
    }
)


def _real_sregym_capabilities():
    module = pytest.importorskip(
        "gymact.gyms.sregym",
        reason="real external gymact.gyms.sregym module is not available",
    )
    return module.SREGYM_CAPABILITIES


def test_default_manifest_exists_and_parses() -> None:
    assert DEFAULT_MANIFEST_PATH.exists()
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)
    assert gate.environment == "sregym"
    assert gate.allowed_names == EXPECTED_SREGYM_BINDINGS


def test_observability_and_terminal_capabilities_are_explicitly_admitted() -> None:
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)
    for binding in (
        "run_kubectl",
        "jaeger_get_traces",
        "loki_get_logs",
        "prometheus_get_metrics",
        "submit_diagnosis",
        "submit_mitigation",
    ):
        entry = gate.entry(binding)
        assert entry.name == binding
        assert entry.consequence == "DO"
        assert entry.reason


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


def test_real_sregym_capabilities_exactly_match_reviewed_manifest() -> None:
    capabilities = _real_sregym_capabilities()
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)
    real_names = frozenset(capability.binding for capability in capabilities)

    assert len(capabilities) == 14
    assert real_names == EXPECTED_SREGYM_BINDINGS
    assert gate.allowed_names == real_names
    assert gate.stale_entries(real_names) == frozenset()
    for capability in capabilities:
        assert gate.guard_capability(capability) is capability


def test_real_gymact_capability_object_with_unlisted_binding_is_refused() -> None:
    models = pytest.importorskip(
        "gymact.models", reason="real external gymact.models module is not available"
    )
    hypothetical_ground_truth_capability = models.Capability(
        iri="urn:gymact:sregym:capability:get_injected_fault",
        title="Read injected fault ground truth",
        consequence=models.Consequence.READ,
        binding="get_injected_fault",
    )
    gate = CapabilityGate.from_toml(DEFAULT_MANIFEST_PATH)
    with pytest.raises(CapabilityRefused) as excinfo:
        gate.guard_capability(hypothetical_ground_truth_capability)
    assert excinfo.value.binding == "get_injected_fault"


def test_stale_entries_detects_an_injected_fake_entry(tmp_path) -> None:
    capabilities = _real_sregym_capabilities()
    real_names = frozenset(capability.binding for capability in capabilities)
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
        reason = "stale entry"
        """,
        encoding="utf-8",
    )
    gate = CapabilityGate.from_toml(manifest)
    assert gate.stale_entries(real_names) == frozenset(
        {"get_injected_fault_TYPO_DOES_NOT_EXIST"}
    )
