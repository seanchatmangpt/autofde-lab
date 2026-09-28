import pytest
from scipy import stats

from autofde_lab.ptd_exp.statistics import confidence_band, mean, population_stddev


def test_statistics():
    assert mean([1, 2, 3]) == 2 and population_stddev([2, 2]) == 0


def test_band_is_student_t_on_sample_stddev():
    xs = [0.2, 0.3, 0.25, 0.4]
    lo, hi = confidence_band(xs)
    ref = stats.t.interval(0.95, 3, loc=mean(xs), scale=stats.sem(xs))
    assert (lo, hi) == pytest.approx(ref)
    assert confidence_band([0.1]) is None
