from autofde_lab.ptd_exp.invariants import *


def test_invariants():
    assert semantic_invariant(["a", "a"]) and realization_nonpersistent(["a", "b"])
