"""Sample statistics for PTD campaigns, delegated to stdlib/scipy rather than hand-rolled."""
from __future__ import annotations

import statistics as _st

from scipy import stats as _sps

mean = _st.fmean


def population_stddev(xs):
    return _st.pstdev(xs)


def confidence_band(xs, level: float = 0.95):
    """Student-t interval on the mean, or ``None`` when n < 2.

    One sample carries no variance estimate; returning a band would manufacture
    certainty from absence, so the caller receives UNKNOWN (``None``).
    """
    xs = list(xs)
    if len(xs) < 2:
        return None
    m = _st.fmean(xs)
    s = _st.stdev(xs)
    if s == 0:
        return (m, m)
    lo, hi = _sps.t.interval(level, len(xs) - 1, loc=m, scale=s / len(xs) ** 0.5)
    return (float(lo), float(hi))
