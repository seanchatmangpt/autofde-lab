import pytest

from autofde_lab.fabric.gall import (
    Checkpoint,
    Dependency,
    MachineExperience,
    checkpoint_descriptor,
    frontier,
    to_hddl_problem,
)


BASE = dict(
    repository="seanchatmangpt/xaas",
    base_sha="b" * 40,
    graph_digest="sha256:" + "a" * 64,
    goal="Implement the admitted semantic work subject",
    verifier="xaas-dod",
)


def checkpoint(iri: str, **overrides):
    values = {**BASE, "iri": iri, **overrides}
    return Checkpoint(**values)


def witnessed_dependency(iri: str = "urn:gall:work-order:dep") -> Dependency:
    return Dependency(
        iri,
        "ALIVE",
        receipt_iri="urn:gall:receipt:dep",
        receipt_digest="sha256:" + "c" * 64,
    )


def executable_checkpoint(iri: str, **overrides):
    values = {
        "work_order_iri": f"urn:gall:work-order:{iri.rsplit(':', 1)[-1]}",
        "provider": "zcode",
        "execution_policy": "autonomic_wave_attempt",
        **overrides,
    }
    return checkpoint(iri, **values)


def test_frontier_keeps_all_unknown_nodes_with_alive_dependencies():
    ready_b = checkpoint(
        "urn:gall:b",
        dependencies=(Dependency("urn:gall:dep", "ALIVE"),),
    )
    ready_a = checkpoint("urn:gall:a")
    blocked = checkpoint(
        "urn:gall:blocked",
        dependencies=(Dependency("urn:gall:dep2", "UNKNOWN"),),
    )
    done = checkpoint("urn:gall:done", standing="ALIVE")

    assert frontier([ready_b, blocked, done, ready_a]) == (ready_a, ready_b)


def test_hddl_projection_is_deterministic_and_does_not_select_a_winner():
    a = checkpoint("urn:gall:a")
    b = checkpoint("urn:gall:b")

    left = to_hddl_problem([b, a])
    right = to_hddl_problem([a, b])

    assert left == right
    assert "(task_0 (solve checkpoint_0))" in left
    assert "(task_1 (solve checkpoint_1))" in left


def test_execution_descriptor_binds_subject_policy_and_dependency_receipt():
    value = checkpoint_descriptor(
        executable_checkpoint(
            "urn:gall:a",
            dependencies=(witnessed_dependency(),),
        )
    )

    assert value["schema"] == "gall.work-order-execution/2"
    assert value["work_order_iri"] == "urn:gall:work-order:a"
    assert value["repository_identity"] == "seanchatmangpt/xaas"
    assert value["execution_policy"] == "autonomic_wave_attempt"
    assert value["authority"] == "NONE"
    assert value["dependencies"] == [
        {
            "work_order_iri": "urn:gall:work-order:dep",
            "required_standing": "ALIVE",
            "observed_standing": "ALIVE",
            "receipt_iri": "urn:gall:receipt:dep",
            "receipt_digest": "sha256:" + "c" * 64,
        }
    ]
    assert "lease_token" not in value
    assert "epoch_id" not in value
    assert "worker_id" not in value


def test_execution_descriptor_refuses_alive_without_receipt_evidence():
    candidate = executable_checkpoint(
        "urn:gall:a",
        dependencies=(Dependency("urn:gall:dep", "ALIVE"),),
    )

    with pytest.raises(ValueError, match="receipt evidence"):
        checkpoint_descriptor(candidate)


def test_execution_descriptor_requires_distinct_work_order_identity():
    candidate = checkpoint(
        "urn:gall:a",
        provider="zcode",
        execution_policy="continuous_epoch_run",
    )

    with pytest.raises(ValueError, match="work_order_iri"):
        checkpoint_descriptor(candidate)


def test_machine_experience_refuses_unadmitted_selection():
    with pytest.raises(ValueError, match="admitted"):
        MachineExperience(
            checkpoint_iri="urn:gall:a",
            state_before="UNKNOWN",
            available_actions=("inspect", "edit"),
            admitted_actions=("inspect",),
            selected_action="edit",
            observation="none",
            state_after="UNKNOWN",
        )
