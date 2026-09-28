from autofde_lab.ptd_exp.economics import *


def test_economics():
    assert regeneration_advantage(10, 2) == 5 and ptd_advantage(0.5, 10, 2) == 2.5
