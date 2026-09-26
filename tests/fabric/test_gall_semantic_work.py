from autofde_lab.fabric.gall import (
    Checkpoint,
    Dependency,
    MachineExperience,
    checkpoint_descriptor,
    execution_descriptor,
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


def test_descriptor_has_no_execution_authority_fields():
    value = checkpoint_descriptor(checkpoint("urn:gall:a"))

    assert value["checkpoint_iri"] == "urn:gall:a"
    assert "lease_token" not in value
    assert "epoch_id" not in value
    assert "worker_id" not in value


def test_machine_experience_refuses_unadmitted_selection():
    try:
        MachineExperience(
            checkpoint_iri="urn:gall:a",
            state_before="UNKNOWN",
            available_actions=("inspect", "edit"),
            admitted_actions=("inspect",),
            selected_action="edit",
            observation="none",
            state_after="UNKNOWN",
        )
    except ValueError as error:
        assert "admitted" in str(error)
    else:
        raise AssertionError("selection outside admitted actions must fail")


def test_execution_descriptor_matches_xaas_semantic_work_contract_without_authority():
    cp = checkpoint(
        "urn:gall:checkpoint:xaas:001",
        dependencies=(
            Dependency(
                "urn:gall:work-order:dep-1",
                "ALIVE",
                receipt_iri="urn:gall:receipt:dep-1",
                receipt_digest="sha256:" + "c" * 64,
            ),
        ),
    )

    value = execution_descriptor(
        cp,
        work_order_iri="urn:gall:work-order:xaas:001",
        execution_repo_alias="xaas",
        provider="zcode",
        execution_policy="continuous_epoch_run",
    )

    assert value == {
        "work_order_iri": "urn:gall:work-order:xaas:001",
        "checkpoint_iri": "urn:gall:checkpoint:xaas:001",
        "graph_digest": BASE["graph_digest"],
        "repository_identity": "seanchatmangpt/xaas",
        "execution_repo_alias": "xaas",
        "base_sha": BASE["base_sha"],
        "goal": BASE["goal"],
        "provider": "zcode",
        "verifier_suite": "xaas-dod",
        "execution_policy": "continuous_epoch_run",
        "dependencies": [
            {
                "work_order_iri": "urn:gall:work-order:dep-1",
                "required_standing": "ALIVE",
                "observed_standing": "ALIVE",
                "receipt_iri": "urn:gall:receipt:dep-1",
                "receipt_digest": "sha256:" + "c" * 64,
            }
        ],
        "standing": "UNKNOWN",
    }
    for forbidden in ("lease_token", "epoch_id", "worker_id", "authority"):
        assert forbidden not in value


def test_execution_descriptor_refuses_generic_alive_without_receipt_identity():
    cp = checkpoint(
        "urn:gall:checkpoint:xaas:001",
        dependencies=(Dependency("urn:gall:work-order:dep-1", "ALIVE"),),
    )

    try:
        execution_descriptor(
            cp,
            work_order_iri="urn:gall:work-order:xaas:001",
            execution_repo_alias="xaas",
            provider="zcode",
            execution_policy="continuous_epoch_run",
        )
    except ValueError as error:
        assert "exact receipt identity" in str(error)
    else:
        raise AssertionError(
            "generic ALIVE adjacency cannot satisfy XaaS execution admission"
        )
