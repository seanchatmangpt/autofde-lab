from autofde_lab.ptd_exp.stress import phase_budget


def test_stress():
    assert phase_budget([2, 2, 2], 4) == 2
