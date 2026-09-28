"""Semantic-parts benchmark surfaces.

Production discovery lives outside AutoFDE Lab. This package measures whether a
semantic retriever actually improves discovery of independently verified
substitutions; it does not manufacture equivalence labels itself.
"""

from .substitution_benchmark import (
    BehavioralWitness,
    SubstitutionCase,
    evaluate_at_cutoffs,
    evaluate_substitution_discovery,
)

__all__ = [
    "BehavioralWitness",
    "SubstitutionCase",
    "evaluate_at_cutoffs",
    "evaluate_substitution_discovery",
]
