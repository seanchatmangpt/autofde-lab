"""Real Pydantic v2 kernel types for GymAct.

`ActuationIntent`/`Observation`/`ActuationResult` are the request/response shapes
already asserted against by `tests/test_models.py`. `KernelEvent` is the flat,
OCEL-shaped log entry emitted by every `GymActKernel` operation (see
`autofde_lab.gymact.eventlog`) -- one object type (episode) per the ERRC cut in
docs/plans (OCPM/multi-object logging deliberately deferred).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ActuationIntent(BaseModel):
    """What a caller asks the kernel to do."""

    model_config = ConfigDict(frozen=True)

    subject: str
    operation: str
    episode_id: str
    payload: dict[str, Any] = {}
    authority_ref: str | None = None
    idempotency_key: str | None = None


class Observation(BaseModel):
    """Evidence about the world after (or independent of) an actuation."""

    model_config = ConfigDict(frozen=True)

    episode_id: str
    subject: str
    result: dict[str, Any] = {}


class ActuationResult(BaseModel):
    """What the kernel returns for one lifecycle operation."""

    model_config = ConfigDict(frozen=True)

    accepted: bool
    standing: str
    episode_id: str
    observation: Observation | None = None
    receipt: str | None = None


class KernelEvent(BaseModel):
    """One flat OCEL-shaped log entry: (episode_id, activity, timestamp, subject).

    `timestamp` is a monotonically increasing integer sequence number assigned by
    `EventLog.append`, not wall-clock time -- deterministic and trivially
    orderable for conformance replay, with no `datetime.now()` nondeterminism to
    pin in tests.
    """

    model_config = ConfigDict(frozen=True)

    episode_id: str
    activity: str
    timestamp: int
    subject: str
    attributes: dict[str, Any] = {}
