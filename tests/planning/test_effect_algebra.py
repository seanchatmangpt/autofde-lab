from autofde_lab.planning.effects import Effect, check_parallel_candidate


def e(subject, op, *, reads=(), writes=(), known=True):
    return Effect(
        subject=subject,
        operation=op,
        read_set=frozenset(reads),
        write_set=frozenset(writes),
        footprint_known=known,
    )


def test_read_read_is_parallel_candidate():
    check = check_parallel_candidate(e("repo", "read1", reads={"A"}), e("repo", "read2", reads={"A"}))
    assert check.parallel_candidate
    assert check.reason == "DISJOINT_OR_READ_ONLY"


def test_write_read_overlap_conflicts():
    check = check_parallel_candidate(e("repo", "write", writes={"A"}), e("repo", "read", reads={"A"}))
    assert not check.parallel_candidate
    assert check.reason == "EFFECT_CONFLICT"
    assert check.conflict_set == frozenset({"A"})


def test_write_write_overlap_conflicts_even_for_different_tools():
    check = check_parallel_candidate(e("repo", "edit", writes={"A"}), e("repo", "shell", writes={"A"}))
    assert not check.parallel_candidate


def test_disjoint_writes_are_candidates():
    assert check_parallel_candidate(
        e("repo", "edit-a", writes={"A"}),
        e("repo", "edit-b", writes={"B"}),
    ).parallel_candidate


def test_unknown_footprint_fails_closed():
    check = check_parallel_candidate(e("repo", "opaque", known=False), e("repo", "read", reads={"A"}))
    assert not check.parallel_candidate
    assert check.reason == "UNKNOWN_EFFECT"


def test_explicit_commutativity_rule_can_admit_overlap():
    a = e("counter", "inc-left", writes={"counter"})
    b = e("counter", "inc-right", writes={"counter"})
    check = check_parallel_candidate(a, b, commutativity_rule=lambda _a, _b: True)
    assert check.parallel_candidate
    assert check.reason == "PROVEN_COMMUTATIVE"


def test_failed_commutativity_rule_preserves_conflict():
    a = e("state", "a", writes={"A"})
    b = e("state", "b", writes={"A"})
    assert not check_parallel_candidate(a, b, commutativity_rule=lambda _a, _b: False).parallel_candidate


def test_same_tool_different_subject_footprints_may_parallelize():
    assert check_parallel_candidate(
        e("repo@sha:path-a", "edit", writes={"path-a"}),
        e("repo@sha:path-b", "edit", writes={"path-b"}),
    ).parallel_candidate
