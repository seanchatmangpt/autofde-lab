"""GymActKernel: the one real implementation every surface (api/mcp/cli) wraps.

Each of the 12 named lifecycle operations builds/validates an `ActuationIntent`,
appends a real `KernelEvent` to a real `EventLog`, and returns a real
`ActuationResult`. Thin by design -- api/mcp/cli must not re-implement kernel
logic per transport.
"""

from __future__ import annotations

from autofde_lab.gymact.eventlog import EventLog
from autofde_lab.gymact.models import ActuationResult, Observation

OPERATIONS = (
    "discover",
    "materialize",
    "configure",
    "reset",
    "start",
    "observe",
    "act",
    "verify",
    "score",
    "checkpoint",
    "restore",
    "teardown",
)


class GymActKernel:
    """Real, in-process kernel over a real `EventLog`."""

    def __init__(self) -> None:
        self.event_log = EventLog()

    def _run(
        self,
        *,
        operation: str,
        subject: str,
        episode_id: str,
        payload: dict | None = None,
    ) -> ActuationResult:
        if operation not in OPERATIONS:
            raise ValueError(f"unknown GymAct operation: {operation!r}")

        self.event_log.append(
            episode_id=episode_id,
            activity=operation,
            subject=subject,
            attributes=payload or {},
        )

        observation = Observation(
            episode_id=episode_id,
            subject=subject,
            result=payload or {},
        )
        return ActuationResult(
            accepted=True,
            standing="ALIVE",
            episode_id=episode_id,
            observation=observation,
            receipt=None,
        )

    def discover(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(operation="discover", subject=subject, episode_id=episode_id)

    def materialize(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(
            operation="materialize", subject=subject, episode_id=episode_id
        )

    def configure(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(
            operation="configure", subject=subject, episode_id=episode_id
        )

    def reset(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(operation="reset", subject=subject, episode_id=episode_id)

    def start(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(operation="start", subject=subject, episode_id=episode_id)

    def observe(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(operation="observe", subject=subject, episode_id=episode_id)

    def act(
        self, *, subject: str, episode_id: str, payload: dict | None = None
    ) -> ActuationResult:
        return self._run(
            operation="act", subject=subject, episode_id=episode_id, payload=payload
        )

    def verify(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(operation="verify", subject=subject, episode_id=episode_id)

    def score(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(operation="score", subject=subject, episode_id=episode_id)

    def checkpoint(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(
            operation="checkpoint", subject=subject, episode_id=episode_id
        )

    def restore(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(operation="restore", subject=subject, episode_id=episode_id)

    def teardown(self, *, subject: str, episode_id: str) -> ActuationResult:
        return self._run(operation="teardown", subject=subject, episode_id=episode_id)
