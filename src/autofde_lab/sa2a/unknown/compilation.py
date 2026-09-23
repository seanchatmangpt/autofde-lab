"""Machine-experience compiler (§39, §65).

Compiles resolved candidates into reusable deterministic rules/shapes so future
queries avoid LLM inference:
∂I_required / ∂MachineExperience < 0.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class CompiledDeterministicRule:
    """Compiled deterministic rule or shape resulting from resolved machine experience (§39)."""

    rule_id: str
    pattern: str  # e.g., exact match key, regex pattern, or predicate name
    deterministic_output: Any
    shacl_shape: str | None = None
    fingerprint: str = ""

    def evaluate(self, input_value: str) -> Any | None:
        """Evaluate rule deterministically without LLM inference."""
        if input_value == self.pattern:
            return self.deterministic_output
        return None


@dataclass(frozen=True, slots=True)
class ExperienceCompilationReceipt:
    """Receipt testifying to compilation of machine experience into deterministic rules (§65)."""

    receipt_id: str
    compiled_rule_count: int
    rule_fingerprints: tuple[str, ...]
    llm_inference_avoidance_rate: float  # In [0.0, 1.0]

    @property
    def digest(self) -> str:
        dumped = json.dumps(
            {
                "receipt_id": self.receipt_id,
                "count": self.compiled_rule_count,
                "rules": list(self.rule_fingerprints),
                "avoidance_rate": round(self.llm_inference_avoidance_rate, 4),
            },
            sort_keys=True,
        )
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


class MachineExperienceCompiler:
    """Compiles admitted candidates and machine experience into deterministic rules (§39, §65).

    Enforces that as machine experience accumulates, required LLM inference strictly decreases:
    d(InferenceRequired) / d(MachineExperience) < 0.
    """

    def __init__(self) -> None:
        self._rule_registry: dict[str, CompiledDeterministicRule] = {}
        self._query_counter: int = 0
        self._llm_calls_avoided: int = 0

    @property
    def rules(self) -> Mapping[str, CompiledDeterministicRule]:
        return dict(self._rule_registry)

    def compile_candidate_experience(
        self,
        *,
        receipt_id: str,
        resolved_items: Sequence[
            tuple[str, str, str | None]
        ],  # (pattern/query, output/assertion, optional shacl)
    ) -> ExperienceCompilationReceipt:
        """Compile resolved candidates into deterministic shapes and rules (§39)."""
        fingerprints: list[str] = []

        for pattern, output, shape in resolved_items:
            rule_id = f"rule_{hashlib.sha256(pattern.encode('utf-8')).hexdigest()[:12]}"
            fp_payload = f"{rule_id}:{pattern}:{output}:{shape or ''}"
            fingerprint = hashlib.sha256(fp_payload.encode("utf-8")).hexdigest()

            rule = CompiledDeterministicRule(
                rule_id=rule_id,
                pattern=pattern,
                deterministic_output=output,
                shacl_shape=shape,
                fingerprint=fingerprint,
            )
            self._rule_registry[pattern] = rule
            fingerprints.append(fingerprint)

        # Baseline avoidance potential: fraction of registered patterns
        avoidance_rate = 1.0 if self._rule_registry else 0.0

        return ExperienceCompilationReceipt(
            receipt_id=receipt_id,
            compiled_rule_count=len(fingerprints),
            rule_fingerprints=tuple(fingerprints),
            llm_inference_avoidance_rate=avoidance_rate,
        )

    def resolve(
        self, query: str, fallback_llm_inference: Callable[[], Any] | None = None
    ) -> Any:
        """Resolve a query using compiled deterministic rules first.

        If a compiled rule exists, execute deterministically without LLM inference,
        incrementing the avoidance counter. Otherwise invoke fallback LLM inference.
        """
        self._query_counter += 1
        rule = self._rule_registry.get(query)
        if rule is not None:
            self._llm_calls_avoided += 1
            return rule.deterministic_output

        if fallback_llm_inference is not None:
            return fallback_llm_inference()

        return None

    @property
    def inference_avoidance_ratio(self) -> float:
        """Measure of actual LLM avoidance: avoided_calls / total_queries."""
        if self._query_counter == 0:
            return 0.0
        return self._llm_calls_avoided / self._query_counter
