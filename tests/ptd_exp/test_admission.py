from autofde_lab.ptd_exp.admission import *


def test_admission():
    assert Admission("s", "e", True, True, []).admitted
