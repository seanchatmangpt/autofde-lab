from autofde_lab.ptd_exp.transfer import *


def test_transfer():
    assert knowledge_retention(2, 4) == 0.5 and knowledge_depreciation(2, 4) == 0.5
