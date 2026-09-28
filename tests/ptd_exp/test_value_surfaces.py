from autofde_lab.ptd_exp.buyer_value import buyer_value
from autofde_lab.ptd_exp.redteam_value import redteam_value


def test_values():
    assert buyer_value(1, 1, 1, 1, 1) == 1 and redteam_value(0, 0, 0, 0) == 0
