"""PTD campaign manifest (v2): validation, typed parsing, canonical digest.

Optional sections: ``disclosures`` (+ ``disclosure_weight``) and ``techniques_observed``.
There is deliberately no v1 -> v2 migration: v1 trials
(``autofde-lab.ptd.experiment/v1``) carry no semantic or realization digests and no epoch
identity, and inventing them would manufacture evidence from absence. v1 manifests are
evaluated by ``autofde_lab.ptd.summarize_trials``.
"""

from __future__ import annotations

from .identity import canonical_digest
from .models import AttackObservation, EpochObservation, PTDThresholds

SCHEMA = "autofde-lab.ptd.campaign/v2"
REQUIRED = {"schema", "experiment_id", "subject_id", "epochs", "attacks", "criteria"}


def validate_manifest(data):
    # Schema first: a v1 (or unknown) manifest must be refused for what it is, not for
    # whichever v2 field it happens to lack.
    if data.get("schema") != SCHEMA:
        raise ValueError("unsupported PTD schema")
    missing = REQUIRED - data.keys()
    if missing:
        raise ValueError("missing: " + ",".join(sorted(missing)))
    if len(data["epochs"]) < 2:
        raise ValueError("at least two epochs required")


def manifest_digest(data):
    validate_manifest(data)
    return canonical_digest(data)


def parse_manifest(data):
    """Return ``(epochs, attacks, thresholds, allowed_authorities)`` as typed observations."""
    validate_manifest(data)
    fs = frozenset
    epochs = [
        EpochObservation(
            **{
                **e,
                "surface": fs(e.get("surface", ())),
                "critical": fs(e.get("critical", ())),
                "nondeterministic": fs(e.get("nondeterministic", ())),
            }
        )
        for e in data["epochs"]
    ]
    attacks = [
        AttackObservation(
            **{
                **a,
                "stale_facts": fs(a.get("stale_facts", ())),
                "predicted_surface": fs(a.get("predicted_surface", ())),
            }
        )
        for a in data["attacks"]
    ]
    return (
        epochs,
        attacks,
        PTDThresholds(**data["criteria"]),
        tuple(data.get("allowed_authorities", ())),
    )
