"""Fortune-5-scale combinatorial enterprise exploration surface."""

from .catalog import AXES, CATALOG_ROWS
from .space import (
    Axis,
    CompatibilityLaw,
    Option,
    Scenario,
    StateSpace,
    pairwise_covering,
    pairwise_token_count,
)

FORTUNE5_SPACE = StateSpace(axes=AXES)

__all__ = [
    "AXES",
    "CATALOG_ROWS",
    "FORTUNE5_SPACE",
    "Axis",
    "CompatibilityLaw",
    "Option",
    "Scenario",
    "StateSpace",
    "pairwise_covering",
    "pairwise_token_count",
]
