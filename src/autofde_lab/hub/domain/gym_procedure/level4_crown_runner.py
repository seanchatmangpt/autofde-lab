# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Frozen-crown execution harness.

Denominator-freezing discipline, enforced mechanically rather than by
convention:

* Seeds are drawn from an OS-entropy source **after** this process starts
  (`secrets.randbits`), so no concrete trial instance can have existed in
  any prior run, transcript, fixture, or training corpus.
* The frozen set is written to `crown_manifest.json` **before the first
  trial executes**, with a digest over the seed list. `verify_manifest`
  re-derives that digest afterwards -- a changed denominator, a dropped
  failing seed, or a swapped-in easier seed all fail the check.
* Every attempt is retained. `CrownRun.attempts` accumulates across
  repair-and-rerun cycles; nothing is overwritten, so an 8/10 followed by
  a 10/10 reports both, in order.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FrozenCrown:
    """An immutable, digest-bound trial set. Frozen before execution."""

    seeds: tuple[int, ...]
    provider_assignments: tuple[str, ...]  # provider key per seed, same order
    configs: tuple[dict, ...]
    manifest_digest: str
    frozen_at_step: str = "BEFORE_FIRST_TRIAL"

    def size(self) -> int:
        return len(self.seeds)


def _digest_manifest(
    seeds: tuple[int, ...], providers: tuple[str, ...], configs: tuple[dict, ...]
) -> str:
    payload = json.dumps(
        {"seeds": list(seeds), "providers": list(providers), "configs": list(configs)},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def freeze_crown(
    n_trials: int,
    provider_pool: list[str],
    config_for: Callable[[int, str], dict],
    manifest_path: Path,
) -> FrozenCrown:
    """Draw fresh seeds from OS entropy NOW (after process start), assign
    providers round-robin across the pool, write the manifest, return the
    frozen set. Refuses to overwrite an existing manifest -- re-freezing
    over a prior run is exactly the denominator-change this guards."""
    if manifest_path.exists():
        raise FileExistsError(
            f"CROWN_MANIFEST_EXISTS: {manifest_path} already holds a frozen denominator; "
            f"refusing to re-freeze (that would change the denominator after observing results)"
        )
    if n_trials < 10:
        raise ValueError(f"CROWN_DENOMINATOR_TOO_SMALL: {n_trials} < 10")
    if not provider_pool:
        raise ValueError("CROWN_PROVIDER_POOL_EMPTY")

    seeds = tuple(secrets.randbits(32) for _ in range(n_trials))
    providers = tuple(provider_pool[i % len(provider_pool)] for i in range(n_trials))
    configs = tuple(config_for(seed, prov) for seed, prov in zip(seeds, providers))
    digest = _digest_manifest(seeds, providers, configs)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "seeds": list(seeds),
                "providers": list(providers),
                "configs": list(configs),
                "manifest_digest": digest,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return FrozenCrown(
        seeds=seeds,
        provider_assignments=providers,
        configs=configs,
        manifest_digest=digest,
    )


def load_crown(manifest_path: Path) -> FrozenCrown:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    seeds = tuple(data["seeds"])
    providers = tuple(data["providers"])
    configs = tuple(data["configs"])
    recomputed = _digest_manifest(seeds, providers, configs)
    if recomputed != data["manifest_digest"]:
        raise ValueError(
            f"CROWN_MANIFEST_TAMPERED: recomputed digest {recomputed} != recorded {data['manifest_digest']}"
        )
    return FrozenCrown(
        seeds=seeds,
        provider_assignments=providers,
        configs=configs,
        manifest_digest=recomputed,
    )


def verify_manifest(crown: FrozenCrown, executed_seeds: list[int]) -> list[str]:
    """Return violations if what actually ran differs from what was frozen."""
    violations: list[str] = []
    frozen = list(crown.seeds)
    if sorted(executed_seeds) != sorted(frozen):
        missing = sorted(set(frozen) - set(executed_seeds))
        extra = sorted(set(executed_seeds) - set(frozen))
        if missing:
            violations.append(f"SUPPRESSED_TRIAL:seeds_not_executed={missing}")
        if extra:
            violations.append(f"POST_HOC_TRIAL_ADDED:seeds_not_in_manifest={extra}")
    if len(executed_seeds) != len(frozen):
        violations.append(
            f"DENOMINATOR_CHANGED:frozen={len(frozen)},executed={len(executed_seeds)}"
        )
    return violations


def _row_is_alive(row: dict) -> bool:
    """The full conjunction, matching `TrialReport.is_alive`.

    `real_goal_attained` is load-bearing and was previously missing here: a
    trial once reported independently_verified=True while the real world sat
    at counter=1, solved=False, because per-step postcondition verification
    only says the committed plan's PREDICTED consequence was observed -- not
    that the goal was reached. A scoreboard without this term scores the
    model's own prediction, which is the exact failure the typed-induction
    repair exists to prevent.

    Absence is not success. The collection terms below require the key to be
    PRESENT and empty, never merely falsy: `not row.get("replay_mismatches")`
    was true for `[]` *and* for a row that never wrote the field at all, so a
    trial with no replay evidence whatsoever scored identically to one whose
    replay verified. Combined with an exception-swallowing replay path in the
    bridge, that was two independent layers of the same absence-equals-success
    defect, and it is why every row of crown run 1 reported an empty mismatch
    tuple regardless of what replay actually did.

    `replay_ran`/`replay_valid`/`ocel_valid` are explicit conjuncts for the
    same reason: a factor that cannot fail is a factor that is not being
    checked.
    """

    def _present_and_empty(key: str) -> bool:
        return key in row and not row[key]

    return (
        row.get("real_goal_attained") is True
        and row.get("independently_verified") is True
        and row.get("ocel_valid") is True
        and row.get("replay_ran") is True
        and row.get("replay_valid") is True
        and _present_and_empty("ocel_ref_violations")
        and _present_and_empty("replay_mismatches")
    )


@dataclass
class CrownAttempt:
    """One full pass over the frozen set. All attempts are retained."""

    attempt_index: int
    results: list[dict] = field(default_factory=list)
    repair_note: str = ""

    def alive_count(self) -> int:
        return sum(1 for r in self.results if _row_is_alive(r))

    def summary(self) -> str:
        return f"attempt {self.attempt_index}: {self.alive_count()}/{len(self.results)} ALIVE"


@dataclass
class CrownRun:
    crown: FrozenCrown
    attempts: list[CrownAttempt] = field(default_factory=list)

    def record(self, attempt: CrownAttempt) -> None:
        self.attempts.append(attempt)

    def is_complete(self) -> bool:
        """100% ALIVE on the most recent full pass over the frozen set."""
        if not self.attempts:
            return False
        last = self.attempts[-1]
        return (
            len(last.results) == self.crown.size()
            and last.alive_count() == self.crown.size()
        )

    def failed_seeds(self) -> list[int]:
        if not self.attempts:
            return list(self.crown.seeds)
        last = self.attempts[-1]
        alive = {r["seed"] for r in last.results if _row_is_alive(r)}
        return [s for s in self.crown.seeds if s not in alive]

    def full_history(self) -> list[str]:
        """Every attempt, in order -- an 8/10 then 10/10 reports BOTH."""
        return [
            a.summary() + (f" [{a.repair_note}]" if a.repair_note else "")
            for a in self.attempts
        ]

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "manifest_digest": self.crown.manifest_digest,
                    "denominator": self.crown.size(),
                    "attempts": [
                        {
                            "attempt_index": a.attempt_index,
                            "repair_note": a.repair_note,
                            "alive": a.alive_count(),
                            "results": a.results,
                        }
                        for a in self.attempts
                    ],
                    "history": self.full_history(),
                    "complete": self.is_complete(),
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
