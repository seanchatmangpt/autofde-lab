"""Strict projection adapters into the autonomic-survival episode schema.

Adapters in this module do not infer missing semantics. A source event must
explicitly identify its decision phase. This is deliberate: adjacency to an
actuation-shaped activity is not proof that the event is DO, and an OCEL event
name is not authority.

The adapter produces both the neutral episode document consumed by the survival
court and a content-addressed projection receipt binding source identity to the
projected bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .survival import EPISODE_SCHEMA, PHASES

__all__ = [
    "ProjectionReceipt",
    "project_event_trace",
]


@dataclass(frozen=True)
class ProjectionReceipt:
    source_identity: str
    episode_id: str
    episode_document_id: str
    projected_events: int
    adapter: str = "autofde_lab.iec.crowns.survival_adapter.project_event_trace/1"

    @property
    def receipt_id(self) -> str:
        return content_id(
            self.adapter,
            self.source_identity,
            self.episode_id,
            self.episode_document_id,
            self.projected_events,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": "autofde-lab.survival-projection-receipt/1",
            "receipt_id": self.receipt_id,
            "adapter": self.adapter,
            "source_identity": self.source_identity,
            "episode_id": self.episode_id,
            "episode_document_id": self.episode_document_id,
            "projected_events": self.projected_events,
            "authority": "none",
            "actuation_performed": False,
        }


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IECRefusal(
            "REFUSED_SURVIVAL_PROJECTION",
            f"source event requires non-empty {key!r}",
        )
    return value.strip()


def _optional_bool(row: Mapping[str, Any], key: str, default: bool) -> bool:
    value = row.get(key, default)
    if not isinstance(value, bool):
        raise IECRefusal(
            "REFUSED_SURVIVAL_PROJECTION",
            f"source event {key!r} must be boolean",
        )
    return value


def _optional_nonnegative_int(row: Mapping[str, Any], key: str, default: int = 0) -> int:
    value = row.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IECRefusal(
            "REFUSED_SURVIVAL_PROJECTION",
            f"source event {key!r} must be a non-negative integer",
        )
    return value


def project_event_trace(
    events: Sequence[Mapping[str, Any]],
    *,
    source_identity: str,
    subject: str,
    workload_id: str,
    policy_id: str,
    episode_id: str,
    horizon: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project an explicit event trace into the neutral survival schema.

    Required source fields per event are step (positive integer) and phase
    (OBSERVE/SELECT/CONSTRUCT/VERIFY/DO). Optional survival fields are copied
    with strict typing. Extra source fields are ignored rather than interpreted.
    """

    for name, value in (
        ("source_identity", source_identity),
        ("subject", subject),
        ("workload_id", workload_id),
        ("policy_id", policy_id),
        ("episode_id", episode_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise IECRefusal(
                "REFUSED_SURVIVAL_PROJECTION",
                f"{name} must be non-empty",
            )
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise IECRefusal(
            "REFUSED_SURVIVAL_PROJECTION",
            "horizon must be a positive integer",
        )

    projected: list[dict[str, Any]] = []
    seen_steps: set[int] = set()
    for row in events:
        step = _optional_nonnegative_int(row, "step")
        if step < 1:
            raise IECRefusal(
                "REFUSED_SURVIVAL_PROJECTION",
                "source event step must be >= 1",
            )
        if step in seen_steps:
            raise IECRefusal(
                "REFUSED_SURVIVAL_PROJECTION",
                f"duplicate source event step {step}",
            )
        if step > horizon:
            raise IECRefusal(
                "REFUSED_SURVIVAL_PROJECTION",
                f"source event step {step} exceeds horizon {horizon}",
            )
        seen_steps.add(step)

        phase = _required_text(row, "phase")
        if phase not in PHASES:
            raise IECRefusal(
                "REFUSED_SURVIVAL_PROJECTION",
                f"source event phase {phase!r} is not admitted",
            )

        receipt_id = row.get("receipt_id")
        if receipt_id is not None:
            if not isinstance(receipt_id, str) or not receipt_id.strip():
                raise IECRefusal(
                    "REFUSED_SURVIVAL_PROJECTION",
                    "receipt_id must be null or non-empty text",
                )
            receipt_id = receipt_id.strip()

        guards = row.get("guards_installed", ())
        if guards is None:
            guards = ()
        if not isinstance(guards, (list, tuple)):
            raise IECRefusal(
                "REFUSED_SURVIVAL_PROJECTION",
                "guards_installed must be a list or tuple",
            )
        projected.append(
            {
                "step": step,
                "phase": phase,
                "exact_subject": _optional_bool(row, "exact_subject", True),
                "authorized": _optional_bool(row, "authorized", True),
                "admitted": _optional_bool(row, "admitted", True),
                "receipt_id": receipt_id,
                "terminal_ready": _optional_bool(row, "terminal_ready", True),
                "tool_invoked": _optional_bool(row, "tool_invoked", False),
                "llm_tokens": _optional_nonnegative_int(row, "llm_tokens"),
                "replay_verified": _optional_bool(row, "replay_verified", False),
                "guards_installed": [str(item) for item in guards],
            }
        )

    projected.sort(key=lambda event: int(event["step"]))
    document = {
        "schema": EPISODE_SCHEMA,
        "subject": subject.strip(),
        "workload_id": workload_id.strip(),
        "policy_id": policy_id.strip(),
        "episode_id": episode_id.strip(),
        "horizon": horizon,
        "events": projected,
    }
    document_id = content_id(document)
    receipt = ProjectionReceipt(
        source_identity=source_identity.strip(),
        episode_id=episode_id.strip(),
        episode_document_id=document_id,
        projected_events=len(projected),
    )
    return document, receipt.to_json()
