"""Deterministic repository-analysis -> semantic-graph projection."""

from __future__ import annotations

from .engine import RepositoryAnalysis
from .graph_ir import SemanticEdge, SemanticGraph, SemanticNode
from .model import EvidenceKind


class RepositorySemanticProjector:
    """Project observed repository artifacts into a graph without inference."""

    def project(self, analysis: RepositoryAnalysis) -> SemanticGraph:
        repository = SemanticNode.create(
            kind="Repository",
            key=analysis.subject.repository,
            attributes={
                "revision": analysis.subject.revision,
                "default_branch": analysis.subject.default_branch,
                "visibility": analysis.subject.visibility,
            },
            evidence_ids=tuple(
                observation.observation_id
                for observation in analysis.observations
                if observation.predicate == "iec:path"
            ),
            evidence_kind=EvidenceKind.OBSERVED,
        )

        nodes = [repository]
        edges: list[SemanticEdge] = []
        generator_nodes: dict[str, SemanticNode] = {}

        for artifact in analysis.artifacts:
            attributes = {
                "path": artifact.path,
                "artifact_class": artifact.artifact_class.value,
                "content_digest": artifact.content_digest,
            }
            if artifact.unknown_reason:
                attributes["unknown_reason"] = artifact.unknown_reason
            if artifact.producer:
                attributes["producer"] = artifact.producer

            artifact_node = SemanticNode.create(
                kind="Artifact",
                key=f"{analysis.subject.repository}:{artifact.path}",
                attributes=attributes,
                evidence_ids=artifact.evidence_ids or (artifact.content_digest,),
                evidence_kind=EvidenceKind.DERIVED_DETERMINISTIC,
            )
            nodes.append(artifact_node)
            edges.append(
                SemanticEdge.create(
                    source=repository.node_id,
                    predicate="contains",
                    target=artifact_node.node_id,
                    evidence_ids=(artifact.content_digest,),
                    evidence_kind=EvidenceKind.DERIVED_DETERMINISTIC,
                )
            )

            if artifact.producer:
                generator = generator_nodes.get(artifact.producer)
                if generator is None:
                    generator = SemanticNode.create(
                        kind="Generator",
                        key=artifact.producer,
                        evidence_ids=(artifact.content_digest,),
                        evidence_kind=EvidenceKind.DERIVED_DETERMINISTIC,
                    )
                    generator_nodes[artifact.producer] = generator
                    nodes.append(generator)
                edges.append(
                    SemanticEdge.create(
                        source=artifact_node.node_id,
                        predicate="generatedBy",
                        target=generator.node_id,
                        evidence_ids=(artifact.content_digest,),
                        evidence_kind=EvidenceKind.DERIVED_DETERMINISTIC,
                    )
                )

        return SemanticGraph.build(nodes, edges)
