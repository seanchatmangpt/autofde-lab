# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The three-tier certification ladder — `cloud-cert-wbpr-prd.md` FR2.

Pure evaluation logic over caller-supplied trial standings; this module
never runs a trial itself (that's FR1/FR6's job) and never invents a
scenario registry (per Correction 7, none exist yet — Professional-tier
evaluation here takes a real `StrideSample` and a real, caller-supplied
mapping of scenario ID -> trial standing; it is inert until both exist for
a real domain).

Every tier result carries a standing from `.claude/rules/standing-law.md`'s
vocabulary, never a bare boolean — a `PartialAlive` professional-tier result
with a 6.7% pass rate is still a real, reportable result (per `docs/
STATUS.md`'s own precedent of publishing a real negative finding), not a
failure to be hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .stride_sampler import StrideSample

_ALIVE = "ALIVE"


class CertificationTier(str, Enum):
    ASSOCIATE = "associate"
    PROFESSIONAL = "professional"
    EXPERT = "expert"


@dataclass(frozen=True)
class TierResult:
    """The real, checkable outcome of evaluating one tier for one domain."""

    domain: str
    tier: CertificationTier
    standing: str
    """A `standing-law.md` value: `ALIVE`/`PARTIAL_ALIVE`/`BLOCKED:<reason>`
    — never a bare pass/fail boolean. `ALIVE` means the tier's own admission
    rule is satisfied by real evidence; it does NOT mean every sampled trial
    passed (see `pass_rate` for that, at Professional tier)."""
    pass_rate: float | None = None
    """Only set at Professional tier: fraction of the stride sample whose
    trials had standing ALIVE. Published honestly even when low — per
    `docs/STATUS.md` Pass 20's own precedent (6.7% reported, not
    suppressed)."""
    evidence: dict[str, str] = field(default_factory=dict)
    """Scenario/trial ID -> the real trial standing that was evaluated."""
    detail: str = ""


def evaluate_associate(*, domain: str, trial_standing: str, trial_id: str = "") -> TierResult:
    """Associate tier: one clean `standing: ALIVE` receipted trial per
    domain — the PRD's own admission rule, verbatim."""
    if trial_standing == _ALIVE:
        return TierResult(
            domain=domain,
            tier=CertificationTier.ASSOCIATE,
            standing=_ALIVE,
            evidence={trial_id or domain: trial_standing},
            detail="one real ALIVE trial admits Associate tier",
        )
    return TierResult(
        domain=domain,
        tier=CertificationTier.ASSOCIATE,
        standing=f"BLOCKED:ASSOCIATE_TRIAL_NOT_ALIVE:{trial_standing}",
        evidence={trial_id or domain: trial_standing},
        detail=(
            f"the one required trial has standing {trial_standing!r}, not "
            "ALIVE — Associate tier is not admitted"
        ),
    )


def evaluate_professional(
    *, domain: str, sample: StrideSample, trial_standings: dict[str, str]
) -> TierResult:
    """Professional tier: a stride-sampled representative set of scenario
    variants, with a published pass rate — never a single best run.

    Requires every ID in `sample.sample_ids` to have a real, recorded trial
    standing in `trial_standings` (missing entries mean the sample is
    incomplete, not that the missing trials silently count as failures or
    are dropped from the denominator — the tier itself refuses to be
    evaluated on a partial sample rather than mis-reporting a rate).
    """
    if sample.domain != domain:
        return TierResult(
            domain=domain,
            tier=CertificationTier.PROFESSIONAL,
            standing=f"BLOCKED:SAMPLE_DOMAIN_MISMATCH:{sample.domain}",
            detail=f"sample was drawn for domain {sample.domain!r}, not {domain!r}",
        )

    missing = [sid for sid in sample.sample_ids if sid not in trial_standings]
    if missing:
        return TierResult(
            domain=domain,
            tier=CertificationTier.PROFESSIONAL,
            standing=f"BLOCKED:INCOMPLETE_SAMPLE:{len(missing)}_of_{len(sample.sample_ids)}_missing",
            evidence={sid: trial_standings.get(sid, "MISSING") for sid in sample.sample_ids},
            detail=(
                f"{len(missing)} of {len(sample.sample_ids)} sampled scenario IDs have no "
                "recorded trial — the sample is refused as incomplete, not silently scored "
                "on the subset that does exist"
            ),
        )

    evidence = {sid: trial_standings[sid] for sid in sample.sample_ids}
    alive_count = sum(1 for s in evidence.values() if s == _ALIVE)
    pass_rate = alive_count / len(sample.sample_ids) if sample.sample_ids else 0.0

    return TierResult(
        domain=domain,
        tier=CertificationTier.PROFESSIONAL,
        standing=_ALIVE,
        pass_rate=pass_rate,
        evidence=evidence,
        detail=(
            f"stride={sample.stride} sample of {len(sample.sample_ids)}/"
            f"{sample.registry_size} scenarios (registry_digest="
            f"{sample.registry_digest[:12]}...): pass_rate={pass_rate:.1%} — "
            "published as measured, not filtered to best cases"
        ),
    )
