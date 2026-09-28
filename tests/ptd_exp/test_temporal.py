from autofde_lab.ptd_exp.temporal import *


def test_temporal():
    assert strong_temporal_regime(11, 10) and not strong_temporal_regime(10, 10)
