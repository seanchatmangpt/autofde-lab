from autofde_lab.ptd_exp.predictor import *


def test_predictor():
    assert (
        normalized_prediction_error({"a"}, {"b"}) == 1
        and attacker_predictability([1, 1]) == 0
    )
