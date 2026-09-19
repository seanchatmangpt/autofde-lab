"""Real torch-geometric GraphSAGE scorer behind the SA2A candidate fence.

The scorer performs learned link inference only. Its public output is always routed
through candidate_batch_from_scores(), which can manufacture CANDIDATE hypotheses
but cannot admit, authorize, actuate, or mint receipts.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from autofde_lab.sa2a.graph_learning.model import (
    CandidateBatch,
    SemanticFeatureGraph,
    candidate_batch_from_scores,
)


class GraphLearningBackendUnavailable(RuntimeError):
    """Raised when the optional real torch/torch-geometric backend is unavailable."""


class GraphSAGECandidateScorer:
    """Two-layer GraphSAGE encoder with dot-product link scoring.

    A seed makes initial weights replayable for bounded exploration. Production
    callers may load externally trained/qualified weights with load_state_dict().
    Model identity is content-addressed from the current real parameter tensors.
    Regardless of training quality, all outputs remain Standing.CANDIDATE.
    """

    def __init__(
        self,
        input_dim: int,
        *,
        hidden_dim: int = 32,
        output_dim: int = 32,
        seed: int = 0,
    ) -> None:
        if input_dim < 1 or hidden_dim < 1 or output_dim < 1:
            raise ValueError("GraphSAGE dimensions must all be >= 1")

        try:
            import torch
            from torch_geometric.nn import SAGEConv
        except ImportError as exc:
            raise GraphLearningBackendUnavailable(
                "GraphSAGE inference requires torch and torch-geometric; "
                "install autofde-lab with its solvers dependencies"
            ) from exc

        self._torch = torch
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.seed = seed

        # Do not perturb the caller's ambient RNG state merely by constructing
        # an exploratory scorer.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self._conv1 = SAGEConv(input_dim, hidden_dim)
            self._conv2 = SAGEConv(hidden_dim, output_dim)

        self._conv1.eval()
        self._conv2.eval()

    def state_dict(self) -> dict[str, Mapping[str, Any]]:
        """Return the real torch module state for external training/persistence."""
        return {
            "conv1": self._conv1.state_dict(),
            "conv2": self._conv2.state_dict(),
        }

    def load_state_dict(
        self,
        state: Mapping[str, Mapping[str, Any]],
        *,
        strict: bool = True,
    ) -> None:
        """Load externally trained weights into the real GraphSAGE modules."""
        if "conv1" not in state or "conv2" not in state:
            raise ValueError("state must contain conv1 and conv2 mappings")
        self._conv1.load_state_dict(state["conv1"], strict=strict)
        self._conv2.load_state_dict(state["conv2"], strict=strict)
        self._conv1.eval()
        self._conv2.eval()

    @property
    def model_identity(self) -> str:
        """Content-address current model architecture and parameter tensors."""
        hasher = hashlib.sha256()
        hasher.update(b"GraphSAGECandidateScorer:v1")
        hasher.update(
            f":{self.input_dim}:{self.hidden_dim}:{self.output_dim}".encode("ascii")
        )
        for module_name, module in (("conv1", self._conv1), ("conv2", self._conv2)):
            for name, tensor in sorted(module.state_dict().items()):
                value = tensor.detach().cpu().contiguous()
                hasher.update(module_name.encode("utf-8"))
                hasher.update(name.encode("utf-8"))
                hasher.update(str(value.dtype).encode("ascii"))
                hasher.update(str(tuple(value.shape)).encode("ascii"))
                hasher.update(value.numpy().tobytes())
        return f"sha256:{hasher.hexdigest()}"

    def _encode(self, graph: SemanticFeatureGraph):
        if graph.feature_dim != self.input_dim:
            raise ValueError(
                f"graph feature_dim={graph.feature_dim} does not match "
                f"model input_dim={self.input_dim}"
            )

        torch = self._torch
        features = torch.tensor(graph.features, dtype=torch.float32)
        if graph.edges:
            edge_index = torch.tensor(graph.edges, dtype=torch.long).t().contiguous()
        else:
            edge_index = torch.empty((2, 0), dtype=torch.long)

        with torch.no_grad():
            hidden = self._conv1(features, edge_index)
            hidden = torch.relu(hidden)
            encoded = self._conv2(hidden, edge_index)
        return encoded

    def score_pairs(
        self,
        graph: SemanticFeatureGraph,
        pairs: Sequence[tuple[str, str]],
    ) -> tuple[float, ...]:
        """Score candidate node pairs with sigmoid(dot(GraphSAGE(u), GraphSAGE(v)))."""
        node_index = {node_id: index for index, node_id in enumerate(graph.node_ids)}
        for pair in pairs:
            if pair[0] not in node_index or pair[1] not in node_index:
                raise ValueError(f"candidate pair references unknown node: {pair!r}")

        encoded = self._encode(graph)
        torch = self._torch
        scores: list[float] = []
        with torch.no_grad():
            for subject, object_ in pairs:
                raw = torch.dot(
                    encoded[node_index[subject]],
                    encoded[node_index[object_]],
                )
                scores.append(float(torch.sigmoid(raw).item()))
        return tuple(scores)

    def propose(
        self,
        graph: SemanticFeatureGraph,
        *,
        predicate: str,
        candidate_pairs: Sequence[tuple[str, str]],
        top_k: int | None = None,
        min_score: float = 0.0,
        exclude_observed: bool = True,
    ) -> CandidateBatch:
        """Run real GraphSAGE inference and manufacture only fenced candidates."""
        scores = self.score_pairs(graph, candidate_pairs)
        return candidate_batch_from_scores(
            graph=graph,
            model_identity=self.model_identity,
            predicate=predicate,
            pairs=candidate_pairs,
            scores=scores,
            top_k=top_k,
            min_score=min_score,
            exclude_observed=exclude_observed,
        )


__all__ = [
    "GraphLearningBackendUnavailable",
    "GraphSAGECandidateScorer",
]
