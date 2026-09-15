"""DSPy compiler for O -> Candidate(O*) extraction.

DSPy optimizes the *proposal program*.  The output remains untrusted until admission.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from .contracts import CandidateGraphDelta, OptimizationReceipt, SemanticExample
from .evaluation import make_dspy_metric


@dataclass(frozen=True)
class DSPyCompileConfig:
    optimizer: str = "miprov2"
    auto: str = "light"
    max_bootstrapped_demos: int = 4
    max_labeled_demos: int = 8


def _require_dspy():
    try:
        import dspy
    except ImportError as exc:  # pragma: no cover - optional dependency boundary
        raise RuntimeError("DSPy support requires `autofde-lab[dspy]`") from exc
    return dspy


def build_semantic_extractor():
    """Build the typed DSPy module lazily so importing AutoFDE stays dependency-light."""
    dspy = _require_dspy()

    class ExtractSemanticDelta(dspy.Signature):
        """Map an observation to a candidate graph delta using only supplied ontology context."""

        observation: str = dspy.InputField()
        ontology_context: str = dspy.InputField()
        allowed_predicates: str = dspy.InputField()
        provenance_context: str = dspy.InputField()
        candidate_delta_json: str = dspy.OutputField(
            desc="Strict JSON matching CandidateGraphDelta; never invent predicates or provenance"
        )

    class SemanticExtractor(dspy.Module):
        def __init__(self) -> None:
            super().__init__()
            self.extract = dspy.Predict(ExtractSemanticDelta)

        def forward(
            self,
            observation: str,
            ontology_context: str,
            allowed_predicates: str,
            provenance_context: str,
        ):
            return self.extract(
                observation=observation,
                ontology_context=ontology_context,
                allowed_predicates=allowed_predicates,
                provenance_context=provenance_context,
            )

    return SemanticExtractor()


def _to_dspy_examples(examples: Iterable[SemanticExample]):
    dspy = _require_dspy()
    result = []
    for example in examples:
        allowed = sorted(
            {triple.predicate for triple in example.expected_delta.triples}
        )
        item = dspy.Example(
            observation=example.observation,
            ontology_context=example.ontology_context,
            allowed_predicates="\n".join(allowed),
            provenance_context="\n".join(example.expected_delta.source_iris),
            expected_delta_json=example.expected_delta.canonical_json(),
            candidate_delta_json=example.expected_delta.canonical_json(),
        ).with_inputs(
            "observation",
            "ontology_context",
            "allowed_predicates",
            "provenance_context",
        )
        result.append(item)
    return result


def compile_semantic_extractor(
    examples: Iterable[SemanticExample],
    *,
    known_predicates: set[str] | frozenset[str],
    config: DSPyCompileConfig | None = None,
):
    """Compile a semantic extractor against Chapman-native graph metrics."""
    dspy = _require_dspy()
    config = config or DSPyCompileConfig()
    trainset = _to_dspy_examples(examples)
    if not trainset:
        raise ValueError("at least one admitted SemanticExample is required")
    metric = make_dspy_metric(known_predicates=known_predicates)
    student = build_semantic_extractor()

    name = config.optimizer.lower()
    if name == "miprov2":
        optimizer = dspy.MIPROv2(metric=metric, auto=config.auto)
    elif name == "bootstrapfewshot":
        optimizer = dspy.BootstrapFewShot(
            metric=metric,
            max_bootstrapped_demos=config.max_bootstrapped_demos,
            max_labeled_demos=config.max_labeled_demos,
        )
    elif name == "gepa":
        if not hasattr(dspy, "GEPA"):
            raise RuntimeError("installed DSPy release does not expose GEPA")
        optimizer = dspy.GEPA(metric=metric, auto=config.auto)
    else:
        raise ValueError(f"unsupported DSPy optimizer: {config.optimizer}")
    return optimizer.compile(student, trainset=trainset)


def prediction_to_candidate(prediction) -> CandidateGraphDelta:
    """Convert DSPy output into the untrusted candidate contract."""
    return CandidateGraphDelta.model_validate_json(prediction.candidate_delta_json)


def compile_and_receipt_extractor(
    examples: Iterable[SemanticExample],
    *,
    known_predicates: set[str] | frozenset[str],
    dataset_hash: str,
    ontology_hash: str,
    config: DSPyCompileConfig | None = None,
    lm_identity: str | None = None,
) -> tuple[object, OptimizationReceipt]:
    """Compile a semantic extractor and manufacture an immutable OptimizationReceipt."""
    config = config or DSPyCompileConfig()
    compiled = compile_semantic_extractor(
        examples, known_predicates=known_predicates, config=config
    )
    metric_fn = make_dspy_metric(known_predicates=known_predicates)

    scores: list[float] = []
    trainset = _to_dspy_examples(examples)
    for ex in trainset:
        try:
            pred = compiled(
                observation=ex.observation,
                ontology_context=ex.ontology_context,
                allowed_predicates=ex.allowed_predicates,
                provenance_context=ex.provenance_context,
            )
            scores.append(metric_fn(ex, pred))
        except Exception:  # noqa: BLE001 - evaluation boundary catches program execution failures
            scores.append(0.0)

    mean_score = sum(scores) / len(scores) if scores else 0.0
    metric_vector = {
        "mean_score": mean_score,
        "sample_count": float(len(scores)),
    }

    prog_dump = repr(compiled)
    program_hash = hashlib.sha256(prog_dump.encode("utf-8")).hexdigest()

    receipt = OptimizationReceipt.manufacture(
        dataset_hash=dataset_hash,
        ontology_hash=ontology_hash,
        optimizer_name=config.optimizer,
        optimizer_config={
            "auto": config.auto,
            "max_bootstrapped_demos": config.max_bootstrapped_demos,
            "max_labeled_demos": config.max_labeled_demos,
        },
        metric_vector=metric_vector,
        program_hash=program_hash,
        lm_identity=lm_identity,
    )
    return compiled, receipt
