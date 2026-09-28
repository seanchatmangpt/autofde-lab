"""Disclosure surfaces: buyer value vs opposing-party (red-team) value of exposing an artifact."""

from dataclasses import dataclass

from .buyer_value import buyer_value
from .redteam_value import redteam_value


@dataclass(frozen=True)
class Disclosure:
    name: str
    buyer_utility: float
    attacker_utility: float


def disclosure_score(x, w=1.0):
    return x.buyer_utility - w * x.attacker_utility


def frontier(items, w=1.0):
    return sorted(items, key=lambda x: (disclosure_score(x, w), x.name), reverse=True)


def disclosure_frontier(specs, w=1.0):
    """Ranked disclosure options from declared dimensions, or ``None`` when none were declared.

    ``None`` is UNKNOWN, not zero: an experiment that declares no disclosure surface has
    not established that disclosure is harmless or valuable.
    """
    if not specs:
        return None
    items = []
    for spec in specs:
        try:
            items.append(
                Disclosure(
                    spec["name"],
                    buyer_value(**spec["buyer"]),
                    redteam_value(**spec["redteam"]),
                )
            )
        except (KeyError, TypeError) as error:
            raise ValueError(f"malformed disclosure spec: {error!r}") from error
    if len({i.name for i in items}) != len(items):
        raise ValueError("duplicate disclosure names")
    return [
        {
            "name": x.name,
            "buyer_value": x.buyer_utility,
            "redteam_value": x.attacker_utility,
            "score": disclosure_score(x, w),
        }
        for x in frontier(items, w)
    ]
