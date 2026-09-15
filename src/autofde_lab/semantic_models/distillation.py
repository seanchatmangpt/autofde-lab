"""Optional TRL/PEFT manufacturing of small domain semantic transducers.

The student is an artifact manufactured from admitted O* examples.  It never becomes a
source of truth and its outputs still pass through SemanticAdmissionCourt.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from .admission import SemanticAdmissionCourt
from .constrained import parse_candidate_json
from .contracts import (
    CandidateGraphDelta,
    ModelQualificationRecord,
    SemanticExample,
)
from .dataset import distillation_records
from .evaluation import evaluate_candidate


@dataclass(frozen=True)
class LoraDistillationConfig:
    base_model: str
    output_dir: str
    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    learning_rate: float = 2e-4
    epochs: float = 1.0
    batch_size: int = 2
    max_length: int = 2048


def format_training_text(record: dict[str, str]) -> str:
    return (
        "<observation>\n"
        + record["observation"]
        + "\n</observation>\n<ontology>\n"
        + record["ontology_context"]
        + "\n</ontology>\n<candidate>\n"
        + record["target_json"]
        + "\n</candidate>"
    )


def train_lora_student(
    examples: Iterable[SemanticExample],
    *,
    config: LoraDistillationConfig,
):
    """Train a LoRA student using TRL SFTTrainer over admitted semantic examples."""
    records = distillation_records(examples)
    if not records:
        raise ValueError("distillation requires at least one admitted semantic example")
    try:
        from datasets import Dataset
        from peft import LoraConfig
        from trl import SFTConfig, SFTTrainer
    except ImportError as exc:  # pragma: no cover - optional dependency boundary
        raise RuntimeError("LoRA distillation requires datasets, peft and trl") from exc

    dataset = Dataset.from_list(
        [{"text": format_training_text(record)} for record in records]
    )
    peft_config = LoraConfig(
        r=config.r,
        lora_alpha=config.alpha,
        lora_dropout=config.dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )
    sft_config = SFTConfig(
        output_dir=config.output_dir,
        learning_rate=config.learning_rate,
        num_train_epochs=config.epochs,
        per_device_train_batch_size=config.batch_size,
        max_length=config.max_length,
        dataset_text_field="text",
        report_to="none",
    )
    trainer = SFTTrainer(
        model=config.base_model,
        args=sft_config,
        train_dataset=dataset,
        peft_config=peft_config,
    )
    trainer.train()
    trainer.save_model(config.output_dir)
    return trainer


def qualify_model_candidate(
    *,
    candidate_id: str,
    model_role: str,
    producer: Callable[[str, str], CandidateGraphDelta | str],
    eval_examples: Sequence[SemanticExample],
    court: SemanticAdmissionCourt,
    known_predicates: set[str] | frozenset[str],
    cost_per_1k_tokens: float,
    min_pass_rate: float = 0.95,
) -> ModelQualificationRecord:
    """Evaluate any model or pipeline variant under the exact same court and metric boundary."""
    if not eval_examples:
        raise ValueError("qualification requires at least one evaluation example")

    passed_court = 0
    exact_matches = 0
    latencies: list[float] = []

    for ex in eval_examples:
        t0 = time.monotonic()
        try:
            raw = producer(ex.observation, ex.ontology_context)
            candidate = parse_candidate_json(raw) if isinstance(raw, str) else raw
        except Exception:  # noqa: BLE001 - evaluation boundary catches parsing/runtime failures
            latencies.append(time.monotonic() - t0)
            continue
        latencies.append(time.monotonic() - t0)

        # 1. Court evaluation
        receipt, _ = court.admit(candidate)
        if receipt.standing.value == "ADMITTED":
            passed_court += 1

        # 2. Objective semantic evaluation
        eval_metrics = evaluate_candidate(
            candidate,
            ex.expected_delta,
            known_predicates=known_predicates,
            shacl_conforms=receipt.shacl_conforms or True,
        )
        if eval_metrics.graph_exactness == 1.0:
            exact_matches += 1

    total = len(eval_examples)
    court_pass_rate = float(passed_court / total)
    graph_exactness = float(exact_matches / total)

    sorted_lat = sorted(latencies)
    idx_p95 = int(len(sorted_lat) * 0.95)
    p95_ms = float(sorted_lat[min(idx_p95, len(sorted_lat) - 1)] * 1000.0)

    admissible = court_pass_rate >= min_pass_rate

    return ModelQualificationRecord(
        candidate_id=candidate_id,
        model_role=model_role,  # type: ignore[arg-type]
        court_pass_rate=court_pass_rate,
        graph_exactness=graph_exactness,
        p95_latency_ms=p95_ms,
        cost_per_1k_tokens=cost_per_1k_tokens,
        admissible=admissible,
    )
