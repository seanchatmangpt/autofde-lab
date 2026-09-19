"""GALL-012 candidate-only semantic prediction and optional ML adapters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Sequence


class PredictionStanding(str, Enum):
    CANDIDATE = "CANDIDATE"


@dataclass(frozen=True, slots=True)
class PredictionCandidate:
    subject_id: str
    predicted_label: str
    score: float
    model_digest: str
    standing: PredictionStanding = PredictionStanding.CANDIDATE


def split_subjects(
    subject_ids: Sequence[str],
    *,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    unique = tuple(sorted(set(subject_ids)))
    if len(unique) < 3:
        raise ValueError("semantic predictor qualification requires at least three subjects")
    train_end = max(1, int(len(unique) * train_fraction))
    val_end = max(train_end + 1, int(len(unique) * (train_fraction + validation_fraction)))
    train = unique[:train_end]
    validation = unique[train_end:val_end]
    test = unique[val_end:]
    if not test:
        test = (validation[-1],)
        validation = validation[:-1]
    if set(train) & set(validation) or set(train) & set(test) or set(validation) & set(test):
        raise ValueError("semantic subject leakage across train/validation/test")
    return train, validation, test


class MajorityBaseline:
    """Deterministic no-dependency baseline before any GNN claim."""

    def __init__(self) -> None:
        self.label: str | None = None
        self.model_digest: str | None = None

    def fit(self, labels: Iterable[str]) -> "MajorityBaseline":
        counts: dict[str, int] = {}
        for label in labels:
            counts[label] = counts.get(label, 0) + 1
        if not counts:
            raise ValueError("baseline training labels are empty")
        self.label = min(counts, key=lambda key: (-counts[key], key))
        self.model_digest = "sha256:" + hashlib.sha256(
            json.dumps(counts, sort_keys=True).encode()
        ).hexdigest()
        return self

    def predict(self, subject_id: str) -> PredictionCandidate:
        if self.label is None or self.model_digest is None:
            raise RuntimeError("baseline is not fitted")
        return PredictionCandidate(
            subject_id=subject_id,
            predicted_label=self.label,
            score=1.0,
            model_digest=self.model_digest,
        )


class OptionalGraphSage:
    """Minimal GraphSAGE adapter; unavailable runtimes fail typed, never fall back semantically."""

    def __init__(self, in_channels: int, hidden_channels: int, out_channels: int) -> None:
        try:
            import torch
            from torch_geometric.nn import SAGEConv
        except ImportError as exc:  # pragma: no cover - depends on optional solver extra
            raise RuntimeError("UNSUPPORTED(torch-geometric GraphSAGE runtime)") from exc

        class _Model(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.conv1 = SAGEConv(in_channels, hidden_channels)
                self.conv2 = SAGEConv(hidden_channels, out_channels)

            def forward(self, x: Any, edge_index: Any) -> Any:
                return self.conv2(self.conv1(x, edge_index).relu(), edge_index)

        self.torch = torch
        self.model = _Model()

    def candidate(self, subject_id: str, x: Any, edge_index: Any) -> PredictionCandidate:
        with self.torch.no_grad():
            logits = self.model(x, edge_index)
            pooled = logits.mean(dim=0)
            score, index = pooled.softmax(dim=0).max(dim=0)
        state = {
            key: value.detach().cpu().tolist()
            for key, value in sorted(self.model.state_dict().items())
        }
        model_digest = "sha256:" + hashlib.sha256(
            json.dumps(state, sort_keys=True).encode()
        ).hexdigest()
        return PredictionCandidate(
            subject_id=subject_id,
            predicted_label=str(int(index)),
            score=float(score),
            model_digest=model_digest,
        )

    def export_onnx(self, path: str, x: Any, edge_index: Any) -> str:
        try:
            import onnx  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("UNSUPPORTED(onnx export runtime)") from exc
        self.torch.onnx.export(
            self.model,
            (x, edge_index),
            path,
            input_names=["x", "edge_index"],
            output_names=["logits"],
            opset_version=17,
        )
        raw = open(path, "rb").read()
        return "sha256:" + hashlib.sha256(raw).hexdigest()
