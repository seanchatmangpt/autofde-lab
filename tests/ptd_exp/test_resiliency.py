from autofde_lab.ptd_exp.resiliency import *


def test_resiliency():
    assert coverage({"diversity"}) == 0.125 and unknown_techniques({"x"}) == {"x"}
