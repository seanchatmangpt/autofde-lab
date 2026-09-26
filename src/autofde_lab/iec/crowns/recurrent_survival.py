"""Competing-risk and recurrent-event analysis for autonomy survival courts.

This module extends the first-failure court in :mod:`survival` without
changing its admission semantics. First-failure survival answers "when did a
trajectory first violate a consequential invariant?" This layer answers three
additional questions:

* which typed edge caused the first failure (competing risks),
* whether the same failure edge recurs after repair/guard installation, and
* how much of observed consequential execution is receipted/replay-verified
  and how much still depends on LLM tokens.

Guard metadata is observational. Declaring a guard never suppresses a failure;
only subsequent observed events can establish that the edge did not recur.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .survival import (
    FAILURE_ORDER,
    SurvivalEvent,
    analyze_episode,
    survival_report,
)

__all__ = [
    "cause_specific_survival_report",
    "recurrent_episode_report",
    "recurrent_survival_report",
]


def _ordered_rows(document: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """Validate through the owning court and return raw rows in step order."""

    analyze_episode(document)
    rows = document.get("events")
    if not isinstance(rows, list):
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_EPISODE",
            "events must be a list",
        )
    return tuple(sorted(rows, key=lambda row: int(row["step"])))


def _primary_failure_type(failures: Sequence[str]) -> str:
    for failure_type in FAILURE_ORDER:
        if failure_type in failures:
            return failure_type
    raise IECRefusal(
        "REFUSED_INVALID_SURVIVAL_EPISODE",
        "failure event has no recognized failure type",
    )


def cause_specific_survival_report(
    documents: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Estimate discrete cause-specific first-failure hazards.

    Multiple invalid predicates may hold on one DO. Competing-risk accounting
    must be mutually exclusive, so the primary cause is selected by the
    stable `FAILURE_ORDER`; the base episode report still preserves every
    predicate that failed on that same step.
    """

    base = survival_report(documents)
    reports = [analyze_episode(document) for document in documents]
    horizon = int(base["horizon"])
    by_step: dict[int, Counter[str]] = defaultdict(Counter)
    for report in reports:
        step = report["first_failure_step"]
        if step is None:
            continue
        cause = _primary_failure_type(report["first_failure_types"])
        by_step[int(step)][cause] += 1

    survival_before = 1.0
    cumulative_incidence = {cause: 0.0 for cause in FAILURE_ORDER}
    curve: list[dict[str, Any]] = []
    failed_before = 0

    for step in range(1, horizon + 1):
        at_risk = len(reports) - failed_before
        counts = by_step.get(step, Counter())
        hazards = {
            cause: (counts[cause] / at_risk if at_risk else 0.0)
            for cause in FAILURE_ORDER
        }
        for cause in FAILURE_ORDER:
            cumulative_incidence[cause] += survival_before * hazards[cause]
        all_failures = sum(counts.values())
        all_hazard = all_failures / at_risk if at_risk else 0.0
        survival_after = survival_before * (1.0 - all_hazard)
        curve.append(
            {
                "step": step,
                "at_risk": at_risk,
                "failures": dict(sorted(counts.items())),
                "hazards": hazards,
                "all_cause_hazard": all_hazard,
                "survival": survival_after,
                "cumulative_incidence": dict(cumulative_incidence),
            }
        )
        failed_before += all_failures
        survival_before = survival_after

    result = {
        "schema": "autofde-lab.competing-risk-survival/1",
        "subject": base["subject"],
        "workload_id": base["workload_id"],
        "policy_id": base["policy_id"],
        "horizon": horizon,
        "episodes": len(reports),
        "cause_order": list(FAILURE_ORDER),
        "curve": curve,
        "claim_ceiling": (
            "descriptive cause-specific hazards over exact observed episodes; "
            "primary-cause ordering does not prove causal mechanism"
        ),
    }
    result["id"] = content_id(result)
    return result


def _guards_from_row(row: Mapping[str, Any]) -> tuple[str, ...]:
    guards = row.get("guards_installed", ())
    if guards is None:
        return ()
    if not isinstance(guards, (list, tuple)):
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_EPISODE",
            "guards_installed must be a list or tuple",
        )
    result = tuple(str(item) for item in guards)
    unknown = sorted(set(result) - set(FAILURE_ORDER))
    if unknown:
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_EPISODE",
            f"unknown guard failure type(s): {', '.join(unknown)}",
        )
    return result


def recurrent_episode_report(document: Mapping[str, Any]) -> dict[str, Any]:
    """Report every observed invariant failure and post-guard recurrence."""

    base = analyze_episode(document)
    rows = _ordered_rows(document)
    failure_steps: dict[str, list[int]] = {cause: [] for cause in FAILURE_ORDER}
    guard_step: dict[str, int] = {}

    do_count = 0
    receipted_do_count = 0
    replay_verified_do_count = 0
    llm_tokens = 0
    llm_active_steps = 0

    for row in rows:
        event = SurvivalEvent.from_mapping(row)
        llm_tokens += event.llm_tokens
        llm_active_steps += int(event.llm_tokens > 0)
        if event.phase == "DO":
            do_count += 1
            receipted_do_count += int(event.receipt_id is not None)
            replay = row.get("replay_verified", False)
            if not isinstance(replay, bool):
                raise IECRefusal(
                    "REFUSED_INVALID_SURVIVAL_EPISODE",
                    "replay_verified must be boolean",
                )
            replay_verified_do_count += int(event.receipt_id is not None and replay)
        for cause in event.failure_types:
            failure_steps[cause].append(event.step)
        for cause in _guards_from_row(row):
            guard_step.setdefault(cause, event.step)

    by_cause: dict[str, Any] = {}
    for cause in FAILURE_ORDER:
        steps = failure_steps[cause]
        installed = guard_step.get(cause)
        post_guard = (
            [step for step in steps if step > installed]
            if installed is not None
            else []
        )
        first = steps[0] if steps else None
        by_cause[cause] = {
            "occurrences": len(steps),
            "failure_steps": steps,
            "first_failure_step": first,
            "recurrences": max(0, len(steps) - 1),
            "inter_failure_steps": [
                current - previous for previous, current in zip(steps, steps[1:])
            ],
            "guard_installed_step": installed,
            "guard_install_latency_steps": (
                installed - first
                if installed is not None and first is not None and installed >= first
                else None
            ),
            "post_guard_failures": len(post_guard),
            "post_guard_failure_steps": post_guard,
            "guard_effective_observed": (
                None if installed is None else len(post_guard) == 0
            ),
        }

    receipt_coverage = receipted_do_count / do_count if do_count else None
    replay_coverage = (
        replay_verified_do_count / receipted_do_count
        if receipted_do_count
        else None
    )
    result = {
        "schema": "autofde-lab.recurrent-survival-episode/1",
        "episode_id": base["episode_id"],
        "subject": base["subject"],
        "workload_id": base["workload_id"],
        "policy_id": base["policy_id"],
        "horizon": base["horizon"],
        "first_failure_step": base["first_failure_step"],
        "failure_edges": by_cause,
        "do_count": do_count,
        "receipted_do_count": receipted_do_count,
        "replay_verified_do_count": replay_verified_do_count,
        "receipt_coverage": receipt_coverage,
        "replay_coverage": replay_coverage,
        "llm_tokens": llm_tokens,
        "llm_active_steps": llm_active_steps,
        "llm_dependency_fraction": (
            llm_active_steps / len(rows) if rows else 0.0
        ),
        "claim_ceiling": (
            "observed recurrence and guard effectiveness only; a declared guard "
            "has no effect unless later events demonstrate non-recurrence"
        ),
    }
    result["id"] = content_id(result)
    return result


def recurrent_survival_report(
    documents: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate recurrence, guard effectiveness, and evidence coverage."""

    base = survival_report(documents)
    cause_specific = cause_specific_survival_report(documents)
    episodes = [recurrent_episode_report(document) for document in documents]

    aggregate: dict[str, Any] = {}
    for cause in FAILURE_ORDER:
        occurrences = 0
        recurrences = 0
        guarded_episodes = 0
        post_guard_failures = 0
        pre_guard_exposure = 0
        post_guard_exposure = 0
        pre_guard_failures = 0

        for episode in episodes:
            edge = episode["failure_edges"][cause]
            occurrences += int(edge["occurrences"])
            recurrences += int(edge["recurrences"])
            installed = edge["guard_installed_step"]
            if installed is None:
                continue
            guarded_episodes += 1
            post_guard_failures += int(edge["post_guard_failures"])
            pre_guard_exposure += int(installed)
            post_guard_exposure += max(0, int(episode["horizon"]) - int(installed))
            pre_guard_failures += sum(
                1 for step in edge["failure_steps"] if step <= int(installed)
            )

        pre_rate = (
            pre_guard_failures / pre_guard_exposure
            if pre_guard_exposure
            else None
        )
        post_rate = (
            post_guard_failures / post_guard_exposure
            if post_guard_exposure
            else None
        )
        aggregate[cause] = {
            "occurrences": occurrences,
            "recurrences": recurrences,
            "guarded_episodes": guarded_episodes,
            "post_guard_failures": post_guard_failures,
            "pre_guard_failure_rate_per_step": pre_rate,
            "post_guard_failure_rate_per_step": post_rate,
            "failure_rate_delta_per_step": (
                pre_rate - post_rate
                if pre_rate is not None and post_rate is not None
                else None
            ),
        }

    total_do = sum(int(episode["do_count"]) for episode in episodes)
    total_receipted = sum(int(episode["receipted_do_count"]) for episode in episodes)
    total_replayed = sum(
        int(episode["replay_verified_do_count"]) for episode in episodes
    )
    total_rows = sum(
        int(document.get("events") and len(document["events"]) or 0)
        for document in documents
    )
    llm_active_steps = sum(int(episode["llm_active_steps"]) for episode in episodes)
    llm_tokens = sum(int(episode["llm_tokens"]) for episode in episodes)

    result = {
        "schema": "autofde-lab.recurrent-survival/1",
        "subject": base["subject"],
        "workload_id": base["workload_id"],
        "policy_id": base["policy_id"],
        "horizon": base["horizon"],
        "episodes": len(episodes),
        "first_failure_survival_id": base["id"],
        "cause_specific_survival_id": cause_specific["id"],
        "failure_edges": aggregate,
        "do_count": total_do,
        "receipt_coverage": total_receipted / total_do if total_do else None,
        "replay_coverage": (
            total_replayed / total_receipted if total_receipted else None
        ),
        "llm_tokens": llm_tokens,
        "llm_dependency_fraction": (
            llm_active_steps / total_rows if total_rows else 0.0
        ),
        "episode_ids": sorted(str(episode["episode_id"]) for episode in episodes),
        "claim_ceiling": (
            "descriptive recurrent-event evidence over exact observed episodes; "
            "before/after guard rates are not randomized causal estimates"
        ),
    }
    result["id"] = content_id(result)
    return result
