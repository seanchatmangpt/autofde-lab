"""XPROD cross-product identity and authority-conservation court.

The court does not execute planners or actuators. It admits evidence that a
single exact subject survived projection through the required production
surfaces while producer identity was independently recomputed, relation
witnesses remained content-bound, and no projection minted authority.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Sequence

from .crowns.model import Verdict, canonical_json, content_id

__all__ = [
    "REQUIRED_SURFACES",
    "ProjectionEvidence",
    "RelationWitness",
    "XProdReceipt",
    "make_relation_witness",
    "qualify_xprod",
]

REQUIRED_SURFACES = (
    "GYMACT",
    "HDDL",
    "FOND",
    "POWL",
    "RECEIPT",
    "BRCE",
    "TLA+",
)


def _is_sha256(value: str) -> bool:
    if not value.startswith("sha256:"):
        return False
    payload = value[7:]
    return len(payload) == 64 and all(
        char in "0123456789abcdef" for char in payload
    )


def _bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class ProjectionEvidence:
    """Evidence for one projection of the same exact semantic subject."""

    surface: str
    exact_subject: str
    producer_digest: str
    artifact_digest: str
    evidence_digest: str
    observer_digest: str
    authority_delta: int = 0

    def canonical(self) -> dict[str, object]:
        return {
            "surface": self.surface,
            "exact_subject": self.exact_subject,
            "producer_digest": self.producer_digest,
            "artifact_digest": self.artifact_digest,
            "evidence_digest": self.evidence_digest,
            "observer_digest": self.observer_digest,
            "authority_delta": self.authority_delta,
        }


@dataclass(frozen=True)
class RelationWitness:
    """Content-bound witness relating two projection artifacts."""

    left_surface: str
    right_surface: str
    relation: str
    left_artifact_digest: str
    right_artifact_digest: str
    witness_digest: str

    def basis(self) -> dict[str, str]:
        return {
            "left_surface": self.left_surface,
            "right_surface": self.right_surface,
            "relation": self.relation,
            "left_artifact_digest": self.left_artifact_digest,
            "right_artifact_digest": self.right_artifact_digest,
        }


@dataclass(frozen=True)
class XProdReceipt:
    schema: str
    exact_subject: str
    verdict: Verdict
    projection_set_digest: str
    relation_set_digest: str
    failures: tuple[str, ...]
    authority: str
    replay_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "exact_subject": self.exact_subject,
            "verdict": self.verdict.value,
            "projection_set_digest": self.projection_set_digest,
            "relation_set_digest": self.relation_set_digest,
            "failures": list(self.failures),
            "authority": self.authority,
            "replay_digest": self.replay_digest,
        }


def make_relation_witness(
    *,
    left_surface: str,
    right_surface: str,
    relation: str,
    left_artifact_digest: str,
    right_artifact_digest: str,
) -> RelationWitness:
    basis = {
        "left_surface": left_surface,
        "right_surface": right_surface,
        "relation": relation,
        "left_artifact_digest": left_artifact_digest,
        "right_artifact_digest": right_artifact_digest,
    }
    return RelationWitness(**basis, witness_digest=content_id(basis))


def _connected(
    required: set[str], witnesses: Sequence[RelationWitness]
) -> bool:
    if not required:
        return True
    adjacency = {surface: set() for surface in required}
    for witness in witnesses:
        if witness.left_surface in required and witness.right_surface in required:
            adjacency[witness.left_surface].add(witness.right_surface)
            adjacency[witness.right_surface].add(witness.left_surface)
    pending = [next(iter(required))]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(adjacency[current] - seen)
    return seen == required


def qualify_xprod(
    *,
    exact_subject: str,
    projections: Sequence[ProjectionEvidence],
    witnesses: Sequence[RelationWitness],
    producer_materials: Mapping[str, bytes],
    required_surfaces: Sequence[str] = REQUIRED_SURFACES,
) -> XProdReceipt:
    """Qualify one exact subject across heterogeneous production projections."""

    failures: list[str] = []
    required = set(required_surfaces)
    by_surface: dict[str, ProjectionEvidence] = {}

    if not exact_subject.strip():
        failures.append("EMPTY_EXACT_SUBJECT")

    for projection in projections:
        if projection.surface in by_surface:
            failures.append(f"DUPLICATE_SURFACE:{projection.surface}")
            continue
        by_surface[projection.surface] = projection

    missing = sorted(required - set(by_surface))
    for surface in missing:
        failures.append(f"MISSING_SURFACE:{surface}")

    for surface, projection in sorted(by_surface.items()):
        if projection.exact_subject != exact_subject:
            failures.append(f"EXACT_SUBJECT_MISMATCH:{surface}")
        for field_name, value in (
            ("producer_digest", projection.producer_digest),
            ("artifact_digest", projection.artifact_digest),
            ("evidence_digest", projection.evidence_digest),
            ("observer_digest", projection.observer_digest),
        ):
            if not _is_sha256(value):
                failures.append(f"INVALID_DIGEST:{surface}:{field_name}")
        material = producer_materials.get(surface)
        if material is None:
            failures.append(f"PRODUCER_MATERIAL_MISSING:{surface}")
        elif _bytes_digest(material) != projection.producer_digest:
            failures.append(f"PRODUCER_DIGEST_MISMATCH:{surface}")
        if projection.observer_digest == projection.producer_digest:
            failures.append(f"OBSERVER_NOT_INDEPENDENT:{surface}")
        if projection.authority_delta != 0:
            failures.append(f"AUTHORITY_INCREASE:{surface}")

    for witness in witnesses:
        if witness.left_surface not in by_surface or witness.right_surface not in by_surface:
            failures.append(
                "RELATION_UNKNOWN_SURFACE:"
                f"{witness.left_surface}->{witness.right_surface}"
            )
            continue
        left = by_surface[witness.left_surface]
        right = by_surface[witness.right_surface]
        if witness.left_artifact_digest != left.artifact_digest:
            failures.append(f"RELATION_LEFT_ARTIFACT_MISMATCH:{witness.left_surface}")
        if witness.right_artifact_digest != right.artifact_digest:
            failures.append(f"RELATION_RIGHT_ARTIFACT_MISMATCH:{witness.right_surface}")
        if witness.witness_digest != content_id(witness.basis()):
            failures.append(
                "RELATION_WITNESS_DIGEST_MISMATCH:"
                f"{witness.left_surface}->{witness.right_surface}"
            )

    if required.issubset(by_surface) and not _connected(required, witnesses):
        failures.append("RELATION_GRAPH_DISCONNECTED")

    unique_failures = tuple(dict.fromkeys(failures))
    projection_basis = [
        by_surface[surface].canonical() for surface in sorted(by_surface)
    ]
    relation_basis = [
        {**witness.basis(), "witness_digest": witness.witness_digest}
        for witness in sorted(
            witnesses,
            key=lambda item: (
                item.left_surface, item.right_surface, item.relation, item.witness_digest
            ),
        )
    ]
    projection_set_digest = content_id(projection_basis)
    relation_set_digest = content_id(relation_basis)

    evidence_ceiling = any(
        failure.startswith("PRODUCER_MATERIAL_MISSING:")
        or failure.startswith("MISSING_SURFACE:")
        for failure in unique_failures
    )
    verdict = (
        Verdict.BLOCKED
        if evidence_ceiling
        else Verdict.COUNTEREXAMPLE
        if unique_failures
        else Verdict.PASS
    )

    replay_basis = {
        "schema": "autofde-lab.xprod/1",
        "exact_subject": exact_subject,
        "verdict": verdict.value,
        "projection_set_digest": projection_set_digest,
        "relation_set_digest": relation_set_digest,
        "failures": list(unique_failures),
        "authority": "none",
    }
    return XProdReceipt(
        schema="autofde-lab.xprod/1",
        exact_subject=exact_subject,
        verdict=verdict,
        projection_set_digest=projection_set_digest,
        relation_set_digest=relation_set_digest,
        failures=unique_failures,
        authority="none",
        replay_digest=content_id(canonical_json(replay_basis)),
    )
