"""Optional TRL/PEFT manufacturing of small domain semantic transducers.

The student is an artifact manufactured from admitted O* examples.  It never becomes a
source of truth and its outputs still pass through SemanticAdmissionCourt.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .contracts import SemanticExample
from .dataset import distillation_records


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
