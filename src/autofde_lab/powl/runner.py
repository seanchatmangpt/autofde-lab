# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Concurrent POWL 2.0 orchestration runner.

The existing :mod:`autofde_lab.powl.executor` is deliberately a one-fire
reference semantics: it exposes every structurally enabled leaf and never
chooses among alternatives. This module adds the missing *runner* above that
semantics without weakening the fence:

* every legally concurrent activity is dispatched concurrently;
* choice remains an explicit SELECT seam supplied by ``ChoicePolicy``;
* an ``Atom.action`` payload is never invoked directly;
* world authority remains outside this package behind ``ActivityDriver``;
* successful structural commits are recorded as replayable ``ChoiceRecord``s;
* the default pool eagerly starts eight worker threads.

"100% concurrent" here has a precise meaning: the scheduler is work-conserving
up to ``max_workers`` and never serializes two enabled activities merely to
obtain a deterministic trace. Physical completion order is evidence, not
semantic authority; POWL precedence and explicit choices remain the only
ordering constraints.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from enum import StrEnum
from threading import Barrier, Event, Lock, current_thread
from time import monotonic_ns
from typing import Any, Mapping, Protocol, runtime_checkable
from uuid import uuid4

from autofde_lab.powl.algebra import Atom, ChoiceGraph, End, PowlNode, Silent, Start
from autofde_lab.powl.bounds import DEFAULT_BOUND, ExecutionBound
from autofde_lab.powl.executor import (
    INITIAL_MARKING,
    ChoiceRecord,
    Marking,
    NodePath,
    classify_stall,
    enabled,
    fire,
    is_final,
    node_at,
    replay,
)
from autofde_lab.powl.normalize import model_digest
from autofde_lab.powl.validate import validate_model

__all__ = [
    "DEFAULT_WORKERS",
    "ActivityDriver",
    "ActivityIntent",
    "ActivityOutcome",
    "ActivityRecord",
    "ChoiceDecision",
    "ChoicePolicy",
    "PolicyRecord",
    "RunnerConfig",
    "RunnerRefusal",
    "RunnerRefused",
    "RunEvidence",
    "RunStatus",
    "PowlV2Runner",
]

DEFAULT_WORKERS = 8


class RunnerRefusal(StrEnum):
    """Typed runner-level refusals; structural refusals remain ``PowlError``."""

    ACTIVITY_DRIVER_REQUIRED = "ACTIVITY_DRIVER_REQUIRED"
    CHOICE_POLICY_REQUIRED = "CHOICE_POLICY_REQUIRED"
    INVALID_CHOICE = "INVALID_CHOICE"
    RUNNER_CLOSED = "RUNNER_CLOSED"
    REPLAY_DIVERGED = "REPLAY_DIVERGED"


class RunnerRefused(RuntimeError):
    def __init__(self, refusal: RunnerRefusal, detail: str = "") -> None:
        self.refusal = refusal
        self.detail = detail
        super().__init__(
            f"POWL runner refused: {refusal.value}" + (f" ({detail})" if detail else "")
        )


class RunStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUSED = "REFUSED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    """Bounded scheduler configuration.

    ``max_workers`` is also the maximum number of simultaneously in-flight
    activities. The default is exactly eight and the pool is eagerly warmed,
    so a newly-created runner starts with eight live worker threads rather than
    waiting for the first burst to lazily create them.

    ``activity_timeout_seconds`` is handed to the external driver as a bounded
    execution contract. CPython threads cannot be killed safely; the runner
    therefore never pretends this field is a hard in-process kill switch.
    """

    max_workers: int = DEFAULT_WORKERS
    max_attempts: int = 1
    fail_fast: bool = True
    activity_timeout_seconds: float | None = None
    bound: ExecutionBound = DEFAULT_BOUND
    verify_replay: bool = True
    eager_start: bool = True
    thread_name_prefix: str = "powl-v2"

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.activity_timeout_seconds is not None and self.activity_timeout_seconds <= 0:
            raise ValueError("activity_timeout_seconds must be > 0 when supplied")


@dataclass(frozen=True, slots=True)
class ActivityIntent:
    """Authority-neutral intent handed to the external activity driver.

    The runner never invokes ``action``. A driver may interpret it only under
    whatever admission/authorization boundary that driver owns.
    """

    run_id: str
    model_sha256: str
    path: NodePath
    occurrence: int
    attempt: int
    label: str
    action: Any
    bindings: Mapping[str, Any]
    timeout_seconds: float | None
    cancellation: Event = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class ActivityOutcome:
    success: bool = True
    value: Any = None
    authority_receipt: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class ActivityDriver(Protocol):
    def execute(self, intent: ActivityIntent) -> ActivityOutcome: ...


@dataclass(frozen=True, slots=True)
class ChoiceDecision:
    run_id: str
    choice_path: NodePath
    candidates: tuple[int, ...]
    enabled_paths: Mapping[int, tuple[NodePath, ...]]
    marking: Marking = field(compare=False, repr=False)


@runtime_checkable
class ChoicePolicy(Protocol):
    def choose(self, decision: ChoiceDecision) -> int: ...


@dataclass(frozen=True, slots=True)
class PolicyRecord:
    choice_path: NodePath
    candidates: tuple[int, ...]
    chosen: int
    decided_by: str


@dataclass(frozen=True, slots=True)
class ActivityRecord:
    path: NodePath
    occurrence: int
    attempt: int
    label: str
    success: bool
    worker_thread: str
    started_ns: int
    finished_ns: int
    authority_receipt: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    @property
    def duration_ns(self) -> int:
        return self.finished_ns - self.started_ns


@dataclass(frozen=True, slots=True)
class RunEvidence:
    """Observed runner evidence; deliberately not an authority receipt."""

    run_id: str
    status: RunStatus
    model_sha256: str
    initial_marking: Marking
    final_marking: Marking
    structural_records: tuple[ChoiceRecord, ...]
    policy_records: tuple[PolicyRecord, ...]
    activity_records: tuple[ActivityRecord, ...]
    peak_concurrency: int
    worker_threads: tuple[str, ...]
    refusal: RunnerRefusal | None = None
    detail: str = ""

    @property
    def successful_activities(self) -> int:
        return sum(record.success for record in self.activity_records)

    @property
    def failed_activities(self) -> int:
        return sum(not record.success for record in self.activity_records)


@dataclass(slots=True)
class _Task:
    path: NodePath
    occurrence: int
    attempt: int
    node: Atom


@dataclass(slots=True)
class _TaskResult:
    task: _Task
    outcome: ActivityOutcome | None
    worker_thread: str
    started_ns: int
    finished_ns: int
    error: BaseException | None = None


class PowlV2Runner:
    """Eager eight-thread, work-conserving runner for POWL 2.0 models."""

    def __init__(self, config: RunnerConfig | None = None) -> None:
        self.config = config or RunnerConfig()
        self._pool = ThreadPoolExecutor(
            max_workers=self.config.max_workers,
            thread_name_prefix=self.config.thread_name_prefix,
        )
        self._closed = False
        self._worker_names: set[str] = set()
        self._worker_names_lock = Lock()
        self._activity_lock = Lock()
        self._active = 0
        self._peak = 0
        if self.config.eager_start:
            self._prestart_workers()

    @property
    def worker_threads(self) -> tuple[str, ...]:
        with self._worker_names_lock:
            return tuple(sorted(self._worker_names))

    def _prestart_workers(self) -> None:
        """Force ``ThreadPoolExecutor`` to create every configured worker now."""
        barrier = Barrier(self.config.max_workers + 1)

        def warm() -> str:
            name = current_thread().name
            with self._worker_names_lock:
                self._worker_names.add(name)
            barrier.wait()
            return name

        futures = [self._pool.submit(warm) for _ in range(self.config.max_workers)]
        barrier.wait()
        for future in futures:
            future.result()
        if len(self.worker_threads) != self.config.max_workers:
            raise RuntimeError(
                "worker prestart invariant failed: "
                f"expected={self.config.max_workers} observed={len(self.worker_threads)}"
            )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._pool.shutdown(wait=True, cancel_futures=True)

    def __enter__(self) -> "PowlV2Runner":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _execute(
        self, driver: ActivityDriver, intent: ActivityIntent, task: _Task
    ) -> _TaskResult:
        name = current_thread().name
        with self._worker_names_lock:
            self._worker_names.add(name)
        with self._activity_lock:
            self._active += 1
            self._peak = max(self._peak, self._active)
        started = monotonic_ns()
        try:
            outcome = driver.execute(intent)
            if not isinstance(outcome, ActivityOutcome):
                raise TypeError(
                    "ActivityDriver.execute() must return ActivityOutcome, got "
                    f"{type(outcome).__name__}"
                )
            return _TaskResult(task, outcome, name, started, monotonic_ns())
        except BaseException as exc:
            return _TaskResult(task, None, name, started, monotonic_ns(), exc)
        finally:
            with self._activity_lock:
                self._active -= 1

    @staticmethod
    def _under(path: NodePath, prefix: NodePath) -> bool:
        return len(path) > len(prefix) and path[: len(prefix)] == prefix

    @classmethod
    def _apply_reservations(
        cls, live: set[NodePath], reservations: Mapping[NodePath, int]
    ) -> set[NodePath]:
        out = set(live)
        for prefix, selected in reservations.items():
            out = {
                path
                for path in out
                if not cls._under(path, prefix) or path[len(prefix)] == selected
            }
        return out

    @staticmethod
    def _choice_groups(
        model: PowlNode, live: set[NodePath]
    ) -> dict[NodePath, dict[int, list[NodePath]]]:
        groups: dict[NodePath, dict[int, list[NodePath]]] = {}
        for leaf in sorted(live):
            for depth in range(len(leaf)):
                prefix = leaf[:depth]
                if not isinstance(node_at(model, prefix), ChoiceGraph):
                    continue
                candidate = leaf[depth]
                groups.setdefault(prefix, {}).setdefault(candidate, []).append(leaf)
        return groups

    def _resolve_choices(
        self,
        *,
        model: PowlNode,
        marking: Marking,
        live: set[NodePath],
        reservations: dict[NodePath, int],
        policy: ChoicePolicy | None,
        policy_records: list[PolicyRecord],
        run_id: str,
    ) -> set[NodePath]:
        live = self._apply_reservations(live, reservations)
        while True:
            groups = self._choice_groups(model, live)
            ambiguous = [
                (prefix, by_candidate)
                for prefix, by_candidate in groups.items()
                if len(by_candidate) > 1 and prefix not in reservations
            ]
            if not ambiguous:
                return live
            prefix, by_candidate = min(
                ambiguous, key=lambda item: (len(item[0]), item[0])
            )
            candidates = tuple(sorted(by_candidate))
            if policy is None:
                raise RunnerRefused(
                    RunnerRefusal.CHOICE_POLICY_REQUIRED,
                    f"choice_path={prefix} candidates={candidates}",
                )
            decision = ChoiceDecision(
                run_id=run_id,
                choice_path=prefix,
                candidates=candidates,
                enabled_paths={
                    idx: tuple(sorted(paths))
                    for idx, paths in sorted(by_candidate.items())
                },
                marking=marking,
            )
            chosen = policy.choose(decision)
            if chosen not in by_candidate:
                raise RunnerRefused(
                    RunnerRefusal.INVALID_CHOICE,
                    f"choice_path={prefix} candidates={candidates} chosen={chosen!r}",
                )
            reservations[prefix] = chosen
            policy_records.append(
                PolicyRecord(
                    choice_path=prefix,
                    candidates=candidates,
                    chosen=chosen,
                    decided_by=f"{type(policy).__module__}.{type(policy).__qualname__}",
                )
            )
            live = self._apply_reservations(live, reservations)

    @staticmethod
    def _consume_reservations(
        path: NodePath, reservations: dict[NodePath, int]
    ) -> None:
        for prefix, selected in list(reservations.items()):
            if (
                len(path) > len(prefix)
                and path[: len(prefix)] == prefix
                and path[len(prefix)] == selected
            ):
                reservations.pop(prefix, None)

    @staticmethod
    def _structural_leaf(model: PowlNode, path: NodePath) -> bool:
        return isinstance(node_at(model, path), (Start, End, Silent))

    def run(
        self,
        model: PowlNode,
        driver: ActivityDriver | None,
        *,
        choice_policy: ChoicePolicy | None = None,
        initial: Marking = INITIAL_MARKING,
        context_sha256: str = "",
        cancellation: Event | None = None,
        run_id: str | None = None,
    ) -> RunEvidence:
        """Run ``model`` to terminal standing or a typed boundary.

        The activity pool is dynamic rather than wave/barrier based: whenever a
        worker finishes, its successful leaf is committed immediately and any
        newly-enabled successor may occupy the freed slot while unrelated work
        is still running. That avoids head-of-line blocking across independent
        POWL branches.
        """
        if self._closed:
            raise RunnerRefused(RunnerRefusal.RUNNER_CLOSED)
        validate_model(model)
        run_id = run_id or uuid4().hex
        cancel = cancellation or Event()
        digest = model_digest(model)
        marking = initial
        records: list[ChoiceRecord] = []
        policy_records: list[PolicyRecord] = []
        activity_records: list[ActivityRecord] = []
        reservations: dict[NodePath, int] = {}
        attempts: dict[NodePath, int] = {}
        occurrences: dict[NodePath, int] = {}
        failed_paths: set[NodePath] = set()
        in_flight: dict[Future[_TaskResult], _Task] = {}
        self._peak = 0

        refusal: RunnerRefusal | None = None
        detail = ""
        status = RunStatus.BLOCKED

        def commit(path: NodePath) -> None:
            nonlocal marking
            live_now = enabled(model, marking, self.config.bound)
            if path not in live_now:
                raise RunnerRefused(
                    RunnerRefusal.REPLAY_DIVERGED,
                    f"completed path {path} no longer enabled; enabled={sorted(live_now)}",
                )
            records.append(
                ChoiceRecord(
                    step=len(records),
                    path=path,
                    enabled=tuple(sorted(live_now)),
                    chosen=path,
                    decided_by="powl-v2-concurrent-runner",
                    context_sha256=context_sha256,
                )
            )
            marking = fire(
                model,
                marking,
                path,
                context_sha256=context_sha256,
                bound=self.config.bound,
            )
            self._consume_reservations(path, reservations)

        try:
            while True:
                if cancel.is_set():
                    status = RunStatus.CANCELLED
                    detail = "cancellation requested"
                    break

                if is_final(model, marking):
                    status = (
                        RunStatus.COMPLETED if not failed_paths else RunStatus.FAILED
                    )
                    break

                full_live = set(enabled(model, marking, self.config.bound))
                live = self._resolve_choices(
                    model=model,
                    marking=marking,
                    live=full_live,
                    reservations=reservations,
                    policy=choice_policy,
                    policy_records=policy_records,
                    run_id=run_id,
                )

                active_paths = {task.path for task in in_flight.values()}
                progressed = False
                for path in sorted(live):
                    if path in failed_paths or path in active_paths:
                        continue
                    if self._structural_leaf(model, path):
                        commit(path)
                        progressed = True
                if progressed:
                    continue

                active_paths = {task.path for task in in_flight.values()}
                ready = [
                    path
                    for path in sorted(live)
                    if path not in active_paths and path not in failed_paths
                ]
                slots = self.config.max_workers - len(in_flight)
                for path in ready[: max(0, slots)]:
                    node = node_at(model, path)
                    if not isinstance(node, Atom):
                        continue
                    if driver is None:
                        raise RunnerRefused(
                            RunnerRefusal.ACTIVITY_DRIVER_REQUIRED,
                            f"enabled activity {node.label!r} at path={path}",
                        )
                    attempt = attempts.get(path, 0) + 1
                    attempts[path] = attempt
                    occurrence = occurrences.get(path, 0)
                    task = _Task(
                        path=path,
                        occurrence=occurrence,
                        attempt=attempt,
                        node=node,
                    )
                    intent = ActivityIntent(
                        run_id=run_id,
                        model_sha256=digest,
                        path=path,
                        occurrence=occurrence,
                        attempt=attempt,
                        label=node.label,
                        action=node.action,
                        bindings=node.bindings,
                        timeout_seconds=self.config.activity_timeout_seconds,
                        cancellation=cancel,
                    )
                    future = self._pool.submit(self._execute, driver, intent, task)
                    in_flight[future] = task

                if not in_flight:
                    if failed_paths:
                        status = RunStatus.FAILED
                        detail = f"activity failures at paths={sorted(failed_paths)}"
                        break
                    if not full_live:
                        status = RunStatus.BLOCKED
                        detail = classify_stall(
                            model, marking, self.config.bound
                        ).value
                        break
                    status = RunStatus.BLOCKED
                    detail = (
                        "no dispatchable activity after policy/reservation filtering"
                    )
                    break

                done, _ = wait(tuple(in_flight), return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda item: in_flight[item].path):
                    task = in_flight.pop(future)
                    result = future.result()
                    failure = result.error
                    if (
                        result.outcome is not None
                        and not result.outcome.success
                        and failure is None
                    ):
                        failure = RuntimeError(
                            "activity driver returned success=False"
                        )
                    success = failure is None
                    activity_records.append(
                        ActivityRecord(
                            path=task.path,
                            occurrence=task.occurrence,
                            attempt=task.attempt,
                            label=task.node.label,
                            success=success,
                            worker_thread=result.worker_thread,
                            started_ns=result.started_ns,
                            finished_ns=result.finished_ns,
                            authority_receipt=(
                                result.outcome.authority_receipt
                                if result.outcome is not None
                                else None
                            ),
                            error_type=(
                                type(failure).__name__
                                if failure is not None
                                else None
                            ),
                            error_message=(
                                str(failure) if failure is not None else None
                            ),
                        )
                    )
                    if success:
                        occurrences[task.path] = task.occurrence + 1
                        attempts.pop(task.path, None)
                        commit(task.path)
                        continue

                    if (
                        task.attempt < self.config.max_attempts
                        and not cancel.is_set()
                    ):
                        continue
                    failed_paths.add(task.path)
                    if self.config.fail_fast:
                        cancel.set()
                        for pending in in_flight:
                            pending.cancel()
                        status = RunStatus.FAILED
                        detail = (
                            f"activity {task.node.label!r} failed after "
                            f"{task.attempt} attempt(s): {failure}"
                        )
                        break
                if status is RunStatus.FAILED and self.config.fail_fast:
                    break
        except RunnerRefused as exc:
            refusal = exc.refusal
            detail = exc.detail
            status = RunStatus.REFUSED
        finally:
            if status in {
                RunStatus.FAILED,
                RunStatus.REFUSED,
                RunStatus.CANCELLED,
            }:
                cancel.set()
            if in_flight:
                wait(tuple(in_flight))

        if self.config.verify_replay and records:
            try:
                replayed = replay(
                    model,
                    records,
                    bound=self.config.bound,
                    initial=initial,
                )
            except Exception as exc:
                refusal = RunnerRefusal.REPLAY_DIVERGED
                status = RunStatus.REFUSED
                detail = f"replay failed: {type(exc).__name__}: {exc}"
            else:
                if replayed != marking:
                    refusal = RunnerRefusal.REPLAY_DIVERGED
                    status = RunStatus.REFUSED
                    detail = (
                        "replayed final marking differs from observed final marking"
                    )

        return RunEvidence(
            run_id=run_id,
            status=status,
            model_sha256=digest,
            initial_marking=initial,
            final_marking=marking,
            structural_records=tuple(records),
            policy_records=tuple(policy_records),
            activity_records=tuple(activity_records),
            peak_concurrency=self._peak,
            worker_threads=self.worker_threads,
            refusal=refusal,
            detail=detail,
        )
