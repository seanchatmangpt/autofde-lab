# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Three real timeout mechanisms, for three shapes of "run this without a bound."

No timeout mechanism existed anywhere in this repo for either of the first two
shapes before this module: confirmed this session against
``fabric/coverage.py::_run_solver`` (the only prior "run every solver"
precedent) and against a hand-rolled ``subprocess.run()`` call built for a new
MCP-driven catalog sweep (``notebooks/18_mcp_user_simulation_ocel.ipynb``).
Several real registered solvers are RL-training methods (``RayRLlib``,
``StableBaseline``, ``AugmentedRandomSearch``, ``MaxentIRL``) with no bound on
training time, so this is not a hypothetical gap -- the sweep genuinely needed
both mechanisms to avoid hanging, in two different situations that call for
different fixes:

``run_subprocess_bounded``
    For a call that is *already* a subprocess invocation (a fresh Python
    process, argv-addressable). Uses ``asyncio.create_subprocess_exec`` +
    ``asyncio.wait_for`` -- not blocking ``subprocess.run()``, which was found
    this session to race an already-running asyncio event loop's own
    child-process reaping (SIGCHLD/``waitpid``) when called from a coroutine,
    silently returning bogus near-instant nonzero exit codes instead of real
    results. Kills the child on timeout.

``run_callable_bounded``
    For an arbitrary in-process Python callable that cannot be reduced to a
    subprocess argv -- ``fabric/coverage.py``'s ``domain_factory`` is a
    caller-supplied closure (e.g. ``lambda: CareerAdmission()``), not a
    registry name a fresh process could reconstruct on its own. Uses
    ``signal.alarm`` (POSIX, main-thread only) to raise a real
    :class:`TimeoutError` inside the callable rather than letting it block
    forever. **Correction, this session:** an earlier version of this
    docstring claimed this "covers every registered solver's ``solve()`` +
    rollout loop in this repo today" -- that was false, and was disproven by
    running the real registered ``AOstar`` solver (a pybind11 C++ binding,
    ``autofde_lab.hub.__autofde_lab_hub_cpp._AOStarSolver_``) against the
    real ``Maze`` domain: it ran for 24+ real wall-clock minutes past its
    60s ``run_callable_bounded`` bound, still holding the GIL inside the
    compiled extension. ``signal.alarm`` only fires when execution returns to
    the Python bytecode interpreter or blocks in an interruptible syscall
    (e.g. ``time.sleep``) -- a tight C-extension loop that never yields the
    GIL back to Python never processes the pending signal, so the alarm is
    queued but not delivered until the C call itself returns, which may be
    never in practice. This function remains correct and sufficient for a
    callable that *is* pure-Python or that blocks in an interruptible
    syscall; it is not sufficient, alone, for one that spends its bounded
    time inside non-GIL-releasing native code.

``run_process_bounded``
    The fix for exactly that gap: runs ``fn`` in a real forked child OS
    process and force-kills that process if it outlives ``timeout_s`` --
    ``SIGKILL`` at the OS level does not require the target's cooperation the
    way a Python-level signal handler does, so it bounds CPU-bound native
    code exactly as reliably as Python code. Uses the POSIX ``fork`` start
    method (not the platform-default ``spawn``) specifically so ``fn`` may be
    an arbitrary non-picklable in-process closure (e.g. ``domain_factory``
    itself) -- ``fork`` duplicates the parent's memory via copy-on-write
    instead of pickling the target across a pipe, which ``spawn`` requires
    and a bare ``lambda`` cannot satisfy.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import signal
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class SubprocessOutcome:
    """Result of :func:`run_subprocess_bounded`."""

    standing: str  # "SOLVED" | "TIMEOUT" | "ERROR"
    elapsed_s: float
    stdout: str = ""
    stderr: str = ""
    returncode: Optional[int] = None


async def run_subprocess_bounded(
    argv: Sequence[str],
    *,
    timeout_s: float,
    env: Optional[dict] = None,
) -> SubprocessOutcome:
    """Run ``argv`` as a subprocess, killed if it exceeds ``timeout_s``.

    Never call this from inside a blocking ``subprocess.run()`` in an
    asyncio-driven caller -- that combination is exactly the bug this
    function exists to avoid (see module docstring).
    """
    import time

    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_s
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return SubprocessOutcome(
            standing="TIMEOUT", elapsed_s=time.monotonic() - started
        )

    elapsed = time.monotonic() - started
    return SubprocessOutcome(
        standing="SOLVED" if proc.returncode == 0 else "ERROR",
        elapsed_s=elapsed,
        stdout=stdout_bytes.decode(errors="replace"),
        stderr=stderr_bytes.decode(errors="replace"),
        returncode=proc.returncode,
    )


class _AlarmTimeout(TimeoutError):
    pass


def run_callable_bounded(fn: Callable[[], T], *, timeout_s: float) -> T:
    """Run ``fn()`` in-process, raising :class:`TimeoutError` past ``timeout_s``.

    POSIX + main-thread only (``signal.alarm``'s own restriction -- raises
    :class:`RuntimeError` outside the main thread, since ``SIGALRM`` cannot be
    delivered to a specific non-main thread). Restores any previously
    installed ``SIGALRM`` handler and cancels the pending alarm in a
    ``finally``, so a caller with its own alarm in flight is not silently
    clobbered by a nested call.
    """
    previous_handler = signal.signal(
        signal.SIGALRM, lambda _signum, _frame: (_ for _ in ()).throw(_AlarmTimeout())
    )
    previous_alarm = signal.alarm(
        0
    )  # cancel any pending alarm, read its remaining time
    try:
        signal.alarm(max(1, int(timeout_s)))
        try:
            return fn()
        except _AlarmTimeout as exc:
            raise TimeoutError(f"exceeded {timeout_s:g}s wall-clock bound") from exc
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_alarm:
            signal.alarm(previous_alarm)


def run_process_bounded(fn: Callable[[], T], *, timeout_s: float) -> T:
    """Run ``fn()`` in a forked child process, force-killed past ``timeout_s``.

    Unlike :func:`run_callable_bounded`, this can forcibly stop CPU-bound
    native/C-extension code that never returns control to the Python
    interpreter and so never processes a pending ``SIGALRM`` -- see the
    module docstring for the real ``AOstar``-vs-``Maze`` reproduction this
    session that motivated it. Prefer this over :func:`run_callable_bounded`
    whenever ``fn`` might call into native code (any registered solver is
    exactly this case, since several hub solvers are pybind11 C++ bindings).

    POSIX ``fork`` only (raises :class:`RuntimeError` if the ``fork`` start
    method is unavailable, e.g. Windows) -- deliberately not the
    platform-default ``spawn``, so ``fn`` may be an arbitrary non-picklable
    closure: ``fork`` duplicates the parent's memory via copy-on-write, so
    the child already has direct access to ``fn`` without pickling it across
    a pipe. Only the *result* (or a formatted exception string) crosses the
    pickling boundary via a real :class:`multiprocessing.Queue`, and both are
    ordinary picklable values (``Tuple[Optional[float], str]`` in this
    module's callers).
    """
    if "fork" not in multiprocessing.get_all_start_methods():
        raise RuntimeError("run_process_bounded requires the POSIX 'fork' start method")
    ctx = multiprocessing.get_context("fork")
    result_queue: "multiprocessing.Queue" = ctx.Queue()

    def _target() -> None:
        try:
            result_queue.put(("ok", fn()))
        except BaseException as exc:  # noqa: BLE001 - propagate as data, not a crash
            result_queue.put(("error", f"{type(exc).__name__}: {exc}"))

    process = ctx.Process(target=_target, daemon=True)
    process.start()
    process.join(timeout_s)
    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join()
        raise TimeoutError(f"exceeded {timeout_s:g}s wall-clock bound (process-killed)")

    if result_queue.empty():
        raise RuntimeError(
            f"child process exited (code {process.exitcode}) without a result"
        )
    status, payload = result_queue.get()
    if status == "error":
        raise RuntimeError(payload)
    return payload
