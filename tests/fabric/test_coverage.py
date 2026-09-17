# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real per-solver wall-clock bound: ``fabric/coverage.py::_run_solver``.

Chicago-style: a real ``Maze`` domain and a real, hand-written solver-like
collaborator (``_SleepingSolver`` below) that genuinely blocks past the
timeout via ``time.sleep`` -- the same technique
``tests/fabric/test_bounded_exec.py`` already uses to trip a real
``signal.alarm``. Per this repo's ``testing-chicago-style.md``, a
hand-written, simple, real implementation of a duck-typed interface
(``__enter__``/``__exit__``/``solve()``/``sample_action()``, the exact shape
``_run_solver`` calls) is a real object with real behaviour, not a mock
standing in for a collaborator this repo owns.

Confirmed this session: before commit ``ac4c25f2`` ``_run_solver`` had no
bound at all -- ``build_report`` against a real ``Maze`` domain hung past 90s
because at least one real registered solver (observed: ``AOstar``) has no
wall-clock limit of its own. That commit added ``run_callable_bounded``
(``signal.alarm``-based); these tests prove the bound is real (a genuinely
slow solver is interrupted within the requested bound, not left to hang) and
that the resulting evidence classifies as ``CAUSE_TIMEOUT``, landing in the
``applicable_failed`` bucket rather than being silently dropped.
"""

from __future__ import annotations

import time

from autofde_lab.fabric.coverage import CAUSE_TIMEOUT, _run_solver, classify_failure
from autofde_lab.hub.domain.maze.maze import Maze


class _SleepingSolver:
    """Real solver-like collaborator whose ``solve()`` blocks past any
    reasonable per-solver timeout -- a genuine, if simple, implementation of
    the interface ``_run_solver`` calls, not a mock of one. See module
    docstring.
    """

    def __init__(self, domain_factory, sleep_s: float = 5.0):
        self._domain_factory = domain_factory
        self._sleep_s = sleep_s

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def solve(self):
        time.sleep(self._sleep_s)  # real block, deliberately past the bound below

    def sample_action(self, observation):  # pragma: no cover - never reached
        raise AssertionError("solve() should have been interrupted by the bound")


def test_run_solver_bounds_a_genuinely_slow_solver_and_never_hangs():
    started = time.monotonic()
    cost, evidence = _run_solver(
        "SleepingTestSolver",
        lambda: Maze(),
        solver_class=_SleepingSolver,
        timeout_s=1,
    )
    elapsed = time.monotonic() - started

    assert cost is None
    assert elapsed < 4.0, (
        f"_run_solver did not honor its bound: took {elapsed:.2f}s against a "
        "1s timeout and a solver that sleeps for 5s real wall-clock seconds "
        "-- this is the exact hang this bound exists to prevent"
    )
    assert evidence.startswith("TimeoutError:")
    assert "wall-clock bound" in evidence


def test_timed_out_evidence_classifies_as_timeout_cause():
    cost, evidence = _run_solver(
        "SleepingTestSolver",
        lambda: Maze(),
        solver_class=_SleepingSolver,
        timeout_s=1,
    )
    assert cost is None
    assert classify_failure(evidence) == CAUSE_TIMEOUT


def test_real_cpp_backed_aostar_solver_is_force_killed_not_left_hanging():
    """The exact real regression this module's fix exists for.

    No injected double here: the real registered ``AOstar`` solver (a
    pybind11 C++ binding, ``autofde_lab.hub.__autofde_lab_hub_cpp._AOStarSolver_``)
    against the real default ``Maze`` domain. Confirmed this session, before
    switching ``_run_solver`` from ``run_callable_bounded`` (``signal.alarm``)
    to ``run_process_bounded`` (a real forked OS process, force-killed on
    timeout): this exact pairing ran 24+ real wall-clock minutes past a 60s
    signal-based bound, because the C++ extension never yields the GIL back
    to Python for the pending ``SIGALRM`` to be processed. A short
    ``timeout_s`` here proves the OS-level kill actually interrupts it --
    the signal-based bound could not.
    """
    started = time.monotonic()
    cost, evidence = _run_solver("AOstar", lambda: Maze(), timeout_s=2)
    elapsed = time.monotonic() - started

    assert cost is None
    assert elapsed < 20.0, (
        f"_run_solver did not bound the real AOstar/Maze pairing: took "
        f"{elapsed:.2f}s against a 2s timeout -- this is the exact real hang "
        "(previously 24+ real minutes) this fix exists to prevent"
    )
    assert classify_failure(evidence) == CAUSE_TIMEOUT
