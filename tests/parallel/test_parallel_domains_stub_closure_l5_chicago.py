"""L5 Chicago tests: parallel_domains abstract contracts and IPC pickle round-trip.

Real subprocesses, real pipes, real pynng sockets; deadline-bounded, no sleeps.
"""

import os
import time

import pytest
from pynng import Pull0

from autofde_lab.parallel_domains import ParallelDomain, PipeParallelDomain

DEADLINE_S = 60.0


class CounterDomain:
    def __init__(self):
        self.pid = os.getpid()

    def add(self, a, b):
        return a + b

    def whoami(self):
        return self.pid

    def boom(self):
        raise ValueError("kaboom")


def _factory():
    return CounterDomain()


def _roundtrip(pd):
    """Apply the spawn-time state transfer (mp Values are only shareable by
    inheritance, so full pickling is not possible outside a spawn)."""
    new = object.__new__(type(pd))
    state = pd.__getstate__()
    # pickling copies the bookkeeping lists; emulate that (sync objects stay shared)
    state["_ipc_connections"] = list(state["_ipc_connections"])
    new.__setstate__(state)
    return new


def _poll(pred):
    deadline = time.monotonic() + DEADLINE_S
    while time.monotonic() < deadline:
        if pred():
            return True
    return False


def test_base_contract_is_abstract():
    with pytest.raises(TypeError):
        ParallelDomain(_factory, nb_domains=1)
    assert ParallelDomain.__abstractmethods__ == frozenset(
        {"_launch_processes", "close", "launch", "get_proc_connections"}
    )


def test_pipe_domains_run_in_real_subprocesses():
    with PipeParallelDomain(_factory, nb_domains=2) as pd:
        i = pd.add(2, 3)
        assert pd.get_result(i) == 5
        j = pd.whoami(i=0)
        assert pd.get_result(j) != os.getpid()
        assert all(p.is_alive() for p in pd._processes)
    assert pd._processes == [None, None]


def test_unpickled_copy_reopens_ipc_handles_and_closes_cleanly():
    with PipeParallelDomain(_factory, nb_domains=2, ipc_notify=False) as pd:
        copy = _roundtrip(pd)
        assert copy._ipc_connections == pd._ipc_connections
        for i, conn in enumerate(copy._ipc_connections):
            path = conn[len("ipc://") : -len(".ipc")]
            assert os.path.exists(path)
            assert copy._temp_connections[i] is not None
            assert not copy._temp_connections[i].closed
        for i in range(2):
            copy.close_ipc_connection(i)
        assert copy._ipc_connections == [None, None]
        # the original still owns its files and is unaffected
        assert all(c is not None for c in pd._ipc_connections)
        assert pd.get_result(pd.add(1, 1)) == 2


def test_unpickled_copy_with_closed_original_closes_without_error():
    pd = PipeParallelDomain(_factory, nb_domains=1)
    with pd:
        pass
    copy = _roundtrip(pd)
    assert copy._temp_connections == [None]
    copy.close_ipc_connection(0)


def test_ipc_notify_delivers_success_and_error_over_real_socket():
    with PipeParallelDomain(_factory, nb_domains=1, ipc_notify=True) as pd:
        with Pull0(recv_timeout=int(DEADLINE_S * 1000)) as pull:
            pull.listen(pd.get_ipc_connections()[0])
            i = pd.add(4, 5)
            assert pull.recv() == b"0"
            assert pd.get_result(i) == 9
            pd.boom(i=0)
            assert b"kaboom" in pull.recv()
