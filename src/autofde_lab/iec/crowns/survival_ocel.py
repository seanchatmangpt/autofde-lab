"""Deterministic OCEL 2.0 projection for survival episodes."""

from __future__ import annotations

from typing import Any, Mapping

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import OcelAttribute, OcelAttributeValue, OcelObject

from .model import content_id
from .survival import _parse_episode, analyze_episode


def _attrs(**values: object) -> tuple[OcelAttribute, ...]:
    attrs: list[OcelAttribute] = []
    for key, value in values.items():
        if isinstance(value, bool):
            typed = OcelAttributeValue.boolean(value)
        elif isinstance(value, int):
            typed = OcelAttributeValue.integer(value)
        else:
            typed = OcelAttributeValue.string(str(value))
        attrs.append(OcelAttribute(key, typed))
    return tuple(attrs)


def episode_to_ocel_log(document: Mapping[str, Any]) -> OcelLog:
    """Project one exact survival episode to a validated, replay-stable OCEL log."""
    header, events = _parse_episode(document)
    report = analyze_episode(document)

    subject_id = "survival-subject:" + content_id(
        {
            "subject": header["subject"],
            "workload_id": header["workload_id"],
        }
    )
    policy_id = "survival-policy:" + content_id(
        {
            "policy_id": header["policy_id"],
            "horizon": header["horizon"],
        }
    )
    episode_id = f"survival-episode:{header['episode_id']}"

    objects: list[OcelObject] = [
        OcelObject(
            subject_id,
            "SurvivalSubject",
            _attrs(
                subject=header["subject"],
                workload_id=header["workload_id"],
            ),
        ),
        OcelObject(
            policy_id,
            "SurvivalPolicy",
            _attrs(
                policy_id=header["policy_id"],
                horizon=header["horizon"],
            ),
        ),
        OcelObject(
            episode_id,
            "SurvivalEpisode",
            _attrs(
                episode_id=header["episode_id"],
                failed=report["failed"],
                censored=report["censored"],
            ),
        ),
    ]

    receipt_ids = sorted(
        {
            event.receipt_id
            for event in events
            if event.receipt_id is not None
        }
    )
    objects.extend(
        OcelObject(
            f"survival-receipt:{receipt_id}",
            "Receipt",
            _attrs(receipt_id=receipt_id),
        )
        for receipt_id in receipt_ids
    )

    failure_types = sorted(
        {
            failure_type
            for event in events
            for failure_type in event.failure_types
        }
    )
    objects.extend(
        OcelObject(
            f"survival-failure:{failure_type}",
            "SurvivalFailure",
            _attrs(failure_type=failure_type),
        )
        for failure_type in failure_types
    )

    log = OcelLog.new(objects=objects)
    for event in events:
        links: list[str | tuple[str, str | None]] = [
            (subject_id, "subject"),
            (policy_id, "policy"),
            (episode_id, "episode"),
        ]
        if event.receipt_id is not None:
            links.append((f"survival-receipt:{event.receipt_id}", "receipt"))
        for failure_type in event.failure_types:
            links.append((f"survival-failure:{failure_type}", "failure"))

        log = log.append_event(
            f"{episode_id}:step:{event.step}",
            f"survival.{event.phase.lower()}",
            links,
            timestamp_ns=event.step * 1_000_000_000,
            attributes={
                "step": OcelAttributeValue.integer(event.step),
                "exact_subject": OcelAttributeValue.boolean(event.exact_subject),
                "authorized": OcelAttributeValue.boolean(event.authorized),
                "admitted": OcelAttributeValue.boolean(event.admitted),
                "terminal_ready": OcelAttributeValue.boolean(event.terminal_ready),
                "tool_invoked": OcelAttributeValue.boolean(event.tool_invoked),
                "llm_tokens": OcelAttributeValue.integer(event.llm_tokens),
            },
        )

    return log.validate(strict_qualifiers=True)


def episode_to_ocel2_json(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return literal OCEL 2.0 JSON after structural validation."""
    return episode_to_ocel_log(document).to_ocel2_json()
