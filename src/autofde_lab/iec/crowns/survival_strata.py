"""Stratified survival analysis for GymAct-manufactured campaign evidence.

GymAct carries perturbation identity separately from policy identity. This
module uses that separation to compare policies only within the same explicit
scenario/factor/fault stratum.

Missing metadata is refused rather than inferred. A faulted run and a baseline
run are never silently pooled when fault stratification is enabled.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .survival_compare import compare_survival_policies

__all__ = ["stratified_survival_report"]


def _gymact(document: Mapping[str, Any]) -> Mapping[str, Any]:
    value = document.get("gymact")
    if not isinstance(value, Mapping):
        raise IECRefusal(
            "REFUSED_SURVIVAL_STRATUM_METADATA",
            f"episode {document.get('episode_id')!r} has no gymact metadata",
        )
    return value


def _factor_map(gymact: Mapping[str, Any], episode_id: str) -> dict[str, str]:
    raw = gymact.get("factor_assignments", ())
    if raw is None:
        raw = ()
    if not isinstance(raw, (list, tuple)):
        raise IECRefusal(
            "REFUSED_SURVIVAL_STRATUM_METADATA",
            f"episode {episode_id!r} factor_assignments must be a list",
        )
    result: dict[str, str] = {}
    for assignment in raw:
        if not isinstance(assignment, Mapping):
            raise IECRefusal(
                "REFUSED_SURVIVAL_STRATUM_METADATA",
                f"episode {episode_id!r} has malformed factor assignment",
            )
        name = str(assignment.get("name", "")).strip()
        level = str(assignment.get("level", "")).strip()
        if not name or not level:
            raise IECRefusal(
                "REFUSED_SURVIVAL_STRATUM_METADATA",
                f"episode {episode_id!r} has incomplete factor assignment",
            )
        if name in result:
            raise IECRefusal(
                "REFUSED_SURVIVAL_STRATUM_METADATA",
                f"episode {episode_id!r} repeats factor {name!r}",
            )
        result[name] = level
    return result


def _stratum(
    document: Mapping[str, Any],
    *,
    factor_names: tuple[str, ...],
    stratify_fault: bool,
) -> tuple[tuple[str, str], ...]:
    gymact = _gymact(document)
    episode_id = str(document.get("episode_id", ""))
    scenario_id = str(gymact.get("scenario_id", "")).strip()
    if not scenario_id:
        raise IECRefusal(
            "REFUSED_SURVIVAL_STRATUM_METADATA",
            f"episode {episode_id!r} has no scenario_id",
        )
    factors = _factor_map(gymact, episode_id)
    key: list[tuple[str, str]] = [("scenario_id", scenario_id)]
    for factor_name in factor_names:
        if factor_name not in factors:
            raise IECRefusal(
                "REFUSED_SURVIVAL_STRATUM_METADATA",
                f"episode {episode_id!r} missing factor {factor_name!r}",
            )
        key.append((f"factor:{factor_name}", factors[factor_name]))
    if stratify_fault:
        fault_plan_id = gymact.get("fault_plan_id")
        key.append(
            (
                "fault_plan_id",
                "baseline"
                if fault_plan_id in (None, "")
                else str(fault_plan_id),
            )
        )
    return tuple(key)


def stratified_survival_report(
    documents: Sequence[Mapping[str, Any]],
    *,
    factor_names: Sequence[str] = (),
    stratify_fault: bool = True,
) -> dict[str, Any]:
    """Compare policies within explicit campaign strata.

    A stratum with fewer than two policy ids is retained as a coverage finding
    rather than discarded; no cross-policy comparison is manufactured for it.
    """

    if not documents:
        raise IECRefusal(
            "REFUSED_SURVIVAL_STRATUM_EMPTY",
            "at least one episode is required",
        )
    names = tuple(str(name).strip() for name in factor_names)
    if any(not name for name in names) or len(names) != len(set(names)):
        raise IECRefusal(
            "REFUSED_SURVIVAL_STRATUM_METADATA",
            "factor_names must be unique non-empty names",
        )

    groups: dict[
        tuple[tuple[str, str], ...],
        list[Mapping[str, Any]],
    ] = defaultdict(list)
    for document in documents:
        groups[
            _stratum(
                document,
                factor_names=names,
                stratify_fault=stratify_fault,
            )
        ].append(document)

    strata: list[dict[str, Any]] = []
    complete_comparisons = 0
    for key in sorted(groups):
        rows = groups[key]
        by_policy: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        machinery_by_policy: dict[str, str] = {}
        for row in rows:
            policy_id = str(row.get("policy_id", "")).strip()
            if not policy_id:
                raise IECRefusal(
                    "REFUSED_POLICY_MISMATCH",
                    f"episode {row.get('episode_id')!r} has empty policy_id",
                )
            by_policy[policy_id].append(row)
            machinery = str(_gymact(row).get("machinery", "")).strip()
            if machinery:
                previous = machinery_by_policy.setdefault(policy_id, machinery)
                if previous != machinery:
                    raise IECRefusal(
                        "REFUSED_SURVIVAL_STRATUM_METADATA",
                        f"policy {policy_id!r} maps to multiple machinery values",
                    )

        comparison = None
        if len(by_policy) >= 2:
            comparison = compare_survival_policies(by_policy)
            complete_comparisons += 1
        strata.append(
            {
                "key": dict(key),
                "episodes": len(rows),
                "policy_ids": sorted(by_policy),
                "machinery_by_policy": dict(sorted(machinery_by_policy.items())),
                "comparison_status": (
                    "COMPARED" if comparison is not None else "INSUFFICIENT_POLICY_STRATA"
                ),
                "comparison": comparison,
            }
        )

    result = {
        "schema": "autofde-lab.stratified-survival/1",
        "factor_names": list(names),
        "stratify_fault": stratify_fault,
        "episodes": len(documents),
        "strata_count": len(strata),
        "compared_strata": complete_comparisons,
        "strata": strata,
        "claim_ceiling": (
            "descriptive within-stratum policy comparison only; explicit campaign "
            "metadata defines strata and no causal effect is inferred"
        ),
    }
    result["id"] = content_id(result)
    return result
