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
from .survival import analyze_episode

__all__ = ["survival_episode_to_ocel", "survival_episodes_to_ocel"]


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
            "authorized": OcelAttributeValue.boolean(
                bool(row.get("authorized", True))
            ),
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
