"""One OCEL 2.0 log per doctrine-lab episode, via the aloop deterministic Builder.

Times are logical (round index seconds from epoch 0), not wall clock, so the log
bytes are a pure function of the episode.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from autofde_lab.aloop.ocel_builder import Builder

from .matrix import EpisodeRecord

OBJECT_TYPES = ("Strategy", "World", "Opponent", "Round", "Receipt")
EVENT_TYPES = (
    "episode.start",
    "opponent.hold",
    "opponent.adapt",
    "round.execute",
    "episode.close",
)
_SECOND = 1_000_000_000


def episode_log(episode: EpisodeRecord) -> dict[str, Any]:
    b = Builder(OBJECT_TYPES, EVENT_TYPES)
    prefix = episode.id
    strategy = b.obj(f"strategy:{episode.strategy.id}", "Strategy")
    world = b.obj(f"world:{episode.world.id}", "World")
    opponent = b.obj(f"opponent:{prefix}", "Opponent")
    b.event(
        f"{prefix}:start",
        "episode.start",
        0,
        [("strategy", strategy), ("world", world), ("opponent", opponent)],
    )
    for record in episode.rounds:
        rnd = b.obj(f"round:{prefix}:{record.round}", "Round")
        t = record.round * _SECOND
        b.event(
            f"{prefix}:opp:{record.round}",
            "opponent.adapt" if record.move.adapted else "opponent.hold",
            t,
            [("opponent", opponent), ("round", rnd), ("world", world)],
        )
        receipt = b.obj(
            f"receipt:{record.receipt.replay_digest}",
            "Receipt",
            digest=record.receipt.replay_digest,
            locator=f"fortune5_safe.run_episode#{prefix}:{record.round}",
        )
        b.event(
            f"{prefix}:round:{record.round}",
            "round.execute",
            t + 1,
            [("strategy", strategy), ("round", rnd), ("receipt", receipt)],
        )
    episode_receipt = b.obj(
        f"receipt:{episode.receipt.episode_digest}",
        "Receipt",
        digest=episode.receipt.episode_digest,
        locator=f"doctrine_lab.matrix#{prefix}",
    )
    b.event(
        f"{prefix}:close",
        "episode.close",
        (len(episode.rounds) + 1) * _SECOND,
        [("strategy", strategy), ("world", world), ("receipt", episode_receipt)],
    )
    return b.document()


def log_bytes(document: dict[str, Any]) -> bytes:
    """Compact key-sorted bytes, identical to ``aloop.ocel_builder.dump`` output."""
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def log_sha256(document: dict[str, Any]) -> str:
    return hashlib.sha256(log_bytes(document)).hexdigest()
