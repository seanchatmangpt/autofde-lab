from __future__ import annotations

from ray.rllib.policy.sample_batch import concat_samples as _rllib_concat_samples
from ray.rllib.utils.typing import SampleBatchType


def original_concat_samples(samples: list[SampleBatchType]) -> SampleBatchType:
    """Original rllib concat_samples; its code object is swapped by the monkey patch."""
    return _rllib_concat_samples(samples)
