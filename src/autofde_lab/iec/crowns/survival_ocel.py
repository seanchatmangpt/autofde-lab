"""Project autonomic-survival episodes into the canonical OCEL working model.

The source survival episode remains authoritative. This module only renders its
already-declared semantics into the repository's existing OcelLog so process
analysis can reuse the same validated event/object machinery.

No phase, authority, admission, execution, or standing is inferred here.
Logical step order is encoded as deterministic nanosecond timestamps; no wall
clock is consulted.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import OcelAttribute, OcelAttributeValue, OcelObject

from .model import IECRefusal, content_id
from .survival import _parse_episode, analyze_episode

__all__ = [
    "episode_to_ocel2_json",
    "episode_to_ocel_log",
    "survival_episode_to_ocel",
    "survival_episodes_to_ocel",
]


def _object_id(kind: str, value: str) -> str:
    return f"{kind}:{content_id(value).split(':', 1)[1][:24]}"


def survival_episode_to_ocel(document: Mapping[str, Any]) -> OcelLog:
    """Return one strictly-qualified, structurally validated OCEL projection."""

    report = analyze_episode(document)
    episode_object = _object_id("survival-episode", str(report["episode_id"]))
    subject_object = _object_id("subject", str(report["subject"]))
    policy_object = _object_id("policy", str(report["policy_id"]))

    log = OcelLog().with_objects(
        OcelObject(
            episode_object,
            "SurvivalEpisode",
            (
                OcelAttribute(
                    "episodeId",
                    OcelAttributeValue.string(str(report["episode_id"])),
                ),
                OcelAttribute(
                    "workloadId",
                    OcelAttributeValue.string(str(report["workload_id"])),
                ),
                OcelAttribute(
                    "horizon",
                    OcelAttributeValue.integer(int(report["horizon"])),
                ),
            ),
        ),
        OcelObject(
            subject_object,
            "Subject",
            (
                OcelAttribute(
                    "exactSubject",
                    OcelAttributeValue.string(str(report["subject"])),
                ),
            ),
        ),
        OcelObject(
            policy_object,
            "Policy",
            (
                OcelAttribute(
                    "policyId",
                    OcelAttributeValue.string(str(report["policy_id"])),
                ),
            ),
        ),
    )

    rows = sorted(document.get("events", ()), key=lambda row: int(row["step"]))
    for row in rows:
        step = int(row["step"])
        phase = str(row["phase"])
        guards = row.get("guards_installed", ())
        attributes = {
            "step": OcelAttributeValue.integer(step),
            "phase": OcelAttributeValue.string(phase),
            "exactSubject": OcelAttributeValue.boolean(
                bool(row.get("exact_subject", True))
            ),
            "authorized": OcelAttributeValue.boolean(bool(row.get("authorized", True))),
            "admitted": OcelAttributeValue.boolean(bool(row.get("admitted", True))),
            "terminalReady": OcelAttributeValue.boolean(
                bool(row.get("terminal_ready", True))
            ),
            "toolInvoked": OcelAttributeValue.boolean(
                bool(row.get("tool_invoked", False))
            ),
            "llmTokens": OcelAttributeValue.integer(int(row.get("llm_tokens", 0))),
            "replayVerified": OcelAttributeValue.boolean(
                bool(row.get("replay_verified", False))
            ),
            "receiptId": OcelAttributeValue.string(str(row.get("receipt_id") or "")),
            "guardsInstalled": OcelAttributeValue.string(
                json.dumps(list(guards or ()), sort_keys=True, separators=(",", ":"))
            ),
        }
        log = log.append_event(
            f"{episode_object}:step:{step}",
            f"survival.{phase.lower()}",
            (
                (episode_object, "episode"),
                (subject_object, "subject"),
                (policy_object, "policy"),
            ),
            timestamp_ns=step * 1_000_000_000,
            attributes=attributes,
        )

    return log.validate(strict_qualifiers=True)


def survival_episodes_to_ocel(documents: tuple[Mapping[str, Any], ...]) -> OcelLog:
    """Compose exact episode projections into one validated campaign log."""

    if not documents:
        raise IECRefusal(
            "REFUSED_SURVIVAL_OCEL_EMPTY",
            "at least one survival episode is required",
        )

    logs = tuple(survival_episode_to_ocel(document) for document in documents)
    objects: dict[str, OcelObject] = {}
    events = []
    event_object_links = []
    object_object_links = []
    object_changes = []

    for log in logs:
        for obj in log.objects:
            existing = objects.get(obj.id)
            if existing is not None and existing != obj:
                raise IECRefusal(
                    "REFUSED_SURVIVAL_OCEL_OBJECT_COLLISION",
                    f"object id {obj.id!r} projects to conflicting values",
                )
            objects[obj.id] = obj
        events.extend(log.events)
        event_object_links.extend(log.event_object_links)
        object_object_links.extend(log.object_object_links)
        object_changes.extend(log.object_changes)

    composed = OcelLog.new(
        objects=tuple(objects[key] for key in sorted(objects)),
        events=tuple(events),
        event_object_links=tuple(event_object_links),
        object_object_links=tuple(object_object_links),
        object_changes=tuple(object_changes),
    )
    return composed.validate(strict_qualifiers=True)


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
        {event.receipt_id for event in events if event.receipt_id is not None}
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
        {failure_type for event in events for failure_type in event.failure_types}
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
