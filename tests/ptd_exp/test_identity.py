from autofde_lab.ptd_exp.identity import *


def test_identity():
    assert len(canonical_digest({"b": 2, "a": 1})) == 64
