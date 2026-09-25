"""Deterministic N-Triples projection of IEC evidence.

This serializer is a projection of typed Python evidence, not a second source
of truth and not an RDF reasoner.
"""

from __future__ import annotations

import json
from typing import Iterable

from .model import ArtifactRecord, Observation, RepositorySubject, digest

IEC = "urn:autofde-lab:iec:"


def _iri(value: str) -> str:
    return "<urn:iec:id:" + digest(value).split(":", 1)[1] + ">"


def _literal(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _triple(subject: str, predicate: str, object_: str) -> str:
    return f"{subject} <{IEC}{predicate}> {object_} ."


def project_repository(
    subject: RepositorySubject,
    artifacts: Iterable[ArtifactRecord],
    observations: Iterable[Observation],
) -> str:
    """Project one exact analysis into sorted, deterministic N-Triples."""

    root = _iri(subject.subject_id)
    lines = {
        f"{root} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{IEC}RepositorySubject> .",
        _triple(root, "repository", _literal(subject.repository)),
        _triple(root, "revision", _literal(subject.revision)),
        _triple(root, "defaultBranch", _literal(subject.default_branch)),
        _triple(root, "visibility", _literal(subject.visibility)),
    }

    for artifact in artifacts:
        node = _iri(f"{artifact.subject_id}:{artifact.path}")
        lines.add(
            f"{node} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> "
            f"<{IEC}ArtifactRecord> ."
        )
        lines.add(_triple(node, "subjectDigest", _literal(artifact.subject_id)))
        lines.add(_triple(node, "sourcePath", _literal(artifact.path)))
        lines.add(_triple(node, "contentDigest", _literal(artifact.content_digest)))
        lines.add(
            _triple(node, "artifactClass", _literal(artifact.artifact_class.value))
        )
        if artifact.producer:
            lines.add(_triple(node, "producer", _literal(artifact.producer)))
        if artifact.unknown_reason:
            lines.add(_triple(node, "unknownReason", _literal(artifact.unknown_reason)))

    for observation in observations:
        node = _iri(observation.observation_id)
        lines.add(
            f"{node} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> "
            f"<{IEC}Observation> ."
        )
        lines.add(_triple(node, "observedAt", root))
        lines.add(_triple(node, "sourcePath", _literal(observation.provenance.path)))
        lines.add(_triple(node, "predicate", _literal(observation.predicate)))
        lines.add(_triple(node, "value", _literal(observation.value)))
        lines.add(
            _triple(node, "evidenceKind", _literal(observation.evidence_kind.value))
        )

    return "\n".join(sorted(lines)) + "\n"


def projection_digest(ntriples: str) -> str:
    return digest(ntriples)
