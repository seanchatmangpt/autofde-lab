import math

import pytest

from autofde_lab.ptd_exp.buyer_value import buyer_value
from autofde_lab.ptd_exp.redteam_value import redteam_value


def test_values():
    assert buyer_value(1, 1, 1, 1, 1) == 1 and redteam_value(0, 0, 0, 0) == 0


@pytest.mark.parametrize("bad", [math.nan, -0.1, 1.1, math.inf])
def test_out_of_range_and_nan_dimensions_are_refused(bad):
    with pytest.raises(ValueError):
        buyer_value(bad, 1, 1, 1, 1)
    with pytest.raises(ValueError):
        redteam_value(0, 0, 0, bad)
