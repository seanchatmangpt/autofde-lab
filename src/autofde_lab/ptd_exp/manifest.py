"""PTD campaign manifest (v2): validation, typed parsing, canonical digest."""

from __future__ import annotations

from .identity import canonical_digest
from .models import AttackObservation, EpochObservation, PTDThresholds

SCHEMA = "autofde-lab.ptd.campaign/v2"
REQUIRED = {"schema", "experiment_id", "subject_id", "epochs", "attacks", "criteria"}


def validate_manifest(data):
    missing = REQUIRED - data.keys()
    if missing:
        raise ValueError("missing: " + ",".join(sorted(missing)))
    if data["schema"] != SCHEMA:
        raise ValueError("unsupported PTD schema")
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
