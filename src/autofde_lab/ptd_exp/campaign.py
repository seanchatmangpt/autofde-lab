from dataclasses import dataclass


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    subject_id: str
    epoch_ids: tuple[str, ...]
    seed: int


def validate_campaign(c):
    if len(c.epoch_ids) < 2 or len(set(c.epoch_ids)) != len(c.epoch_ids):
        raise ValueError("invalid epochs")
    if c.seed < 0:
        raise ValueError("seed must be nonnegative")
