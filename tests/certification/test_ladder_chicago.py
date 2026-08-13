# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `certification.ladder` —
`docs/jira/v26.8.12/cloud-cert-wbpr-prd.md` FR2.

Real `StrideSample`/`TierResult` dataclasses throughout; no mocks. State-
based assertions on the real returned `TierResult`, matching this session's
Chicago-TDD discipline.
"""

from __future__ import annotations

from autofde_lab.certification.ladder import (
    CertificationTier,
    evaluate_associate,
    evaluate_professional,
)
from autofde_lab.certification.stride_sampler import StrideSample


def test_associate_tier_admits_on_real_alive_trial() -> None:
    result = evaluate_associate(domain="azuregoat_privesc", trial_standing="ALIVE", trial_id="t1")

    assert result.tier is CertificationTier.ASSOCIATE
    assert result.standing == "ALIVE"
    assert result.evidence == {"t1": "ALIVE"}


def test_associate_tier_refuses_on_non_alive_trial() -> None:
    result = evaluate_associate(domain="cloudgoat_iam_privesc", trial_standing="BUILD_BROKEN")

    assert result.standing.startswith("BLOCKED:ASSOCIATE_TRIAL_NOT_ALIVE:")
    assert "BUILD_BROKEN" in result.standing


def _sample(domain: str, ids: tuple[str, ...]) -> StrideSample:
    return StrideSample(
        domain=domain,
        stride=5,
        registry_size=len(ids) * 5,
        registry_digest="deadbeef",
        sample_ids=ids,
    )


def test_professional_tier_reports_real_mixed_pass_rate_honestly() -> None:
    sample = _sample("sregym", ("s1", "s2", "s3", "s4"))
    trial_standings = {"s1": "ALIVE", "s2": "BLOCKED:TIMEOUT", "s3": "ALIVE", "s4": "BUILD_BROKEN"}

    result = evaluate_professional(domain="sregym", sample=sample, trial_standings=trial_standings)

    assert result.tier is CertificationTier.PROFESSIONAL
    assert result.standing == "ALIVE"
    assert result.pass_rate == 0.5
    assert result.evidence == trial_standings


def test_professional_tier_refuses_incomplete_sample_rather_than_mis_scoring() -> None:
    sample = _sample("sregym", ("s1", "s2", "s3"))
    trial_standings = {"s1": "ALIVE", "s2": "ALIVE"}  # s3 missing

    result = evaluate_professional(domain="sregym", sample=sample, trial_standings=trial_standings)

    assert result.standing.startswith("BLOCKED:INCOMPLETE_SAMPLE:1_of_3_missing")
    assert result.pass_rate is None


def test_professional_tier_refuses_domain_mismatched_sample() -> None:
    sample = _sample("azuregoat_privesc", ("s1",))

    result = evaluate_professional(
        domain="cloudgoat_iam_privesc", sample=sample, trial_standings={"s1": "ALIVE"}
    )

    assert result.standing == "BLOCKED:SAMPLE_DOMAIN_MISMATCH:azuregoat_privesc"


def test_professional_tier_low_pass_rate_is_still_alive_and_published_honestly() -> None:
    """Mirrors docs/STATUS.md Pass 20's own precedent: a real 6.7%-shaped
    result is reported as ALIVE (the measurement itself is real and
    complete), not hidden or downgraded because the number is low."""
    sample = _sample("sregym", tuple(f"s{i}" for i in range(15)))
    trial_standings = {sid: ("ALIVE" if i == 0 else "BLOCKED:NO_MATCH") for i, sid in enumerate(sample.sample_ids)}

    result = evaluate_professional(domain="sregym", sample=sample, trial_standings=trial_standings)

    assert result.standing == "ALIVE"
    assert abs(result.pass_rate - (1 / 15)) < 1e-9
