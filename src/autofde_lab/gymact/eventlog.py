"""Real, in-memory, flat OCEL-shaped event log.

No external event-store dependency -- a real Python list backing real appends and
real reads, sufficient for the ERRC-scoped v1 (single object type: episode).
"""

from __future__ import annotations

from autofde_lab.gymact.models import KernelEvent


class EventLog:
    """Append-only log of `KernelEvent`s, ordered by insertion."""

    def __init__(self) -> None:
        self._events: list[KernelEvent] = []
        self._next_timestamp = 0

    def append(self, *, episode_id: str, activity: str, subject: str,
               attributes: dict | None = None) -> KernelEvent:
        event = KernelEvent(
            episode_id=episode_id,
            activity=activity,
            timestamp=self._next_timestamp,
            subject=subject,
            attributes=attributes or {},
        )
        self._next_timestamp += 1
        self._events.append(event)
        return event

    def events_for_episode(self, episode_id: str) -> list[KernelEvent]:
        return [e for e in self._events if e.episode_id == episode_id]

    def all_events(self) -> list[KernelEvent]:
        return list(self._events)
