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
