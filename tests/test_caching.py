from __future__ import annotations

import importlib.util
import pickle
import sys
import threading
import types
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

PACKAGE_PATH = Path(__file__).parents[1] / "src" / "skdecide"
package = types.ModuleType("skdecide")
package.__path__ = [str(PACKAGE_PATH)]
sys.modules.setdefault("skdecide", package)
MODULE_PATH = PACKAGE_PATH / "caching.py"
SPEC = importlib.util.spec_from_file_location("skdecide.caching", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
caching = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = caching
SPEC.loader.exec_module(caching)

CachePolicy = caching.CachePolicy
CachedDomain = caching.CachedDomain
MemoryCacheStore = caching.MemoryCacheStore
UnhashableCacheKeyError = caching.UnhashableCacheKeyError
UnsafeCacheMethodError = caching.UnsafeCacheMethodError
cache_domain = caching.cache_domain


class CountingDomain:
    def __init__(self) -> None:
        self.calls: dict[str, int] = {}
        self._memory = 1

    def _count(self, method: str) -> None:
        self.calls[method] = self.calls.get(method, 0) + 1

    def get_next_state(self, memory, action):
        self._count("get_next_state")
        return memory + action

    def get_transition_value(self, memory, action, next_state=None):
        self._count("get_transition_value")
        return (memory, action, next_state)

    def get_applicable_actions(self, memory=None):
        self._count("get_applicable_actions")
        memory = self._memory if memory is None else memory
        return tuple(range(memory))

    def step(self, action):
        self._count("step")
        self._memory += action
        return self._memory

    def unstable(self, value):
        self._count("unstable")
        raise RuntimeError(value)

    def identity(self, value):
        self._count("identity")
        return value


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class OpaqueState:
    __hash__ = None

    def __init__(self, values: list[int]) -> None:
        self.values = values


@dataclass
class StructuredState:
    values: list[int]


class CustomState:
    __hash__ = None

    def __init__(self, value: int) -> None:
        self.value = value

    def __cache_key__(self):
        return self.value


def test_model_policy_refuses_actuation_and_random_draws() -> None:
    for method in (
        "step",
        "sample",
        "sample_task_duration",
        "sample_any_domain_value",
        "compute_graph",
        "get_latest_sampled_duration",
        "reset",
        "render",
        "_state_sample",
    ):
        with pytest.raises(UnsafeCacheMethodError):
            CachePolicy.custom(method)


def test_scheduling_policy_covers_static_scheduling_capabilities() -> None:
    policy = CachePolicy.scheduling()

    assert "get_task_duration" in policy.methods
    assert "get_quantity_resource" in policy.methods
    assert "get_successors" in policy.methods
    assert "get_constraints" in policy.methods
    assert "sample_task_duration" not in policy.methods


def test_repeated_model_query_is_cached_and_observable() -> None:
    domain = CountingDomain()
    cached = cache_domain(domain, CachePolicy.custom("get_next_state"))

    assert cached.get_next_state(2, 3) == 5
    assert cached.get_next_state(memory=2, action=3) == 5
    assert domain.calls == {"get_next_state": 1}
    assert cached.cache_info("get_next_state").hits == 1
    assert cached.cache_info("get_next_state").misses == 1
    assert cached.get_next_state.cache_info().currsize == 1


def test_lru_is_bounded_and_evicts_oldest_entry() -> None:
    domain = CountingDomain()
    cached = cache_domain(
        domain, CachePolicy.custom("get_next_state", max_entries=2)
    )

    cached.get_next_state(0, 1)
    cached.get_next_state(1, 1)
    cached.get_next_state(2, 1)
    cached.get_next_state(0, 1)

    info = cached.cache_info()
    assert domain.calls["get_next_state"] == 4
    assert info.currsize == 2
    assert info.evictions == 2


def test_ttl_never_serves_expired_values() -> None:
    clock = FakeClock()
    store = MemoryCacheStore(max_entries=8, clock=clock)
    domain = CountingDomain()
    cached = cache_domain(
        domain,
        CachePolicy.custom("get_next_state", ttl_seconds=5),
        store=store,
    )

    assert cached.get_next_state(1, 1) == 2
    clock.now = 4.9
    assert cached.get_next_state(1, 1) == 2
    clock.now = 5.0
    assert cached.get_next_state(1, 1) == 2

    info = cached.cache_info()
    assert domain.calls["get_next_state"] == 2
    assert info.hits == 1
    assert info.expirations == 1


def test_unhashable_values_bypass_without_changing_domain_behavior() -> None:
    domain = CountingDomain()
    cached = cache_domain(domain, CachePolicy.custom("identity"))
    value = OpaqueState([1, 2])

    assert cached.identity(value) is value
    assert cached.identity(value) is value
    assert domain.calls["identity"] == 2
    assert cached.cache_info("identity").bypasses == 2


def test_unhashable_policy_can_require_explicit_key_support() -> None:
    domain = CountingDomain()
    cached = cache_domain(
        domain, CachePolicy.custom("identity", on_unhashable="raise")
    )

    with pytest.raises(UnhashableCacheKeyError):
        cached.identity(OpaqueState([1]))


def test_dataclass_arguments_are_structurally_normalized() -> None:
    domain = CountingDomain()
    cached = cache_domain(domain, CachePolicy.custom("identity"))

    first = cached.identity(StructuredState([1, 2]))
    second = cached.identity(StructuredState([1, 2]))

    assert first is second
    assert domain.calls["identity"] == 1


def test_cache_key_protocol_admits_custom_state() -> None:
    domain = CountingDomain()
    cached = cache_domain(domain, CachePolicy.custom("identity"))

    first = cached.identity(CustomState(7))
    second = cached.identity(CustomState(7))

    assert first is second
    assert domain.calls["identity"] == 1


def test_custom_key_function_admits_external_unhashable_type() -> None:
    domain = CountingDomain()
    cached = cache_domain(
        domain,
        CachePolicy.custom("identity"),
        key_functions={"identity": lambda value: tuple(value.values)},
    )

    first = cached.identity(OpaqueState([1, 2]))
    second = cached.identity(OpaqueState([1, 2]))

    assert first is second
    assert domain.calls["identity"] == 1


def test_implicit_internal_memory_is_bypassed_but_explicit_memory_is_cached() -> None:
    domain = CountingDomain()
    cached = cache_domain(domain, CachePolicy.custom("get_applicable_actions"))

    assert cached.get_applicable_actions() == (0,)
    cached.step(2)
    assert cached.get_applicable_actions() == (0, 1, 2)
    assert cached.get_applicable_actions(3) == (0, 1, 2)
    assert cached.get_applicable_actions(memory=3) == (0, 1, 2)

    assert domain.calls["get_applicable_actions"] == 3
    info = cached.cache_info("get_applicable_actions")
    assert info.bypasses == 2
    assert info.hits == 1


def test_non_admitted_and_stateful_methods_are_transparent() -> None:
    domain = CountingDomain()
    cached = cache_domain(domain, CachePolicy.custom("get_next_state"))

    assert cached.step(1) == 2
    assert cached.step(1) == 3
    cached.extra = "forwarded"

    assert domain.calls["step"] == 2
    assert domain.extra == "forwarded"
    assert cached.domain is domain
    assert isinstance(cached, CountingDomain)


def test_exceptions_are_not_cached() -> None:
    domain = CountingDomain()
    cached = cache_domain(domain, CachePolicy.custom("unstable"))

    for _ in range(2):
        with pytest.raises(RuntimeError, match="boom"):
            cached.unstable("boom")

    info = cached.cache_info("unstable")
    assert domain.calls["unstable"] == 2
    assert info.errors == 2
    assert info.currsize == 0


def test_single_flight_coalesces_concurrent_misses() -> None:
    started = threading.Event()
    release = threading.Event()

    class SlowDomain:
        def __init__(self) -> None:
            self.calls = 0

        def get_next_state(self, memory, action):
            self.calls += 1
            started.set()
            assert release.wait(2)
            return memory + action

    domain = SlowDomain()
    cached = cache_domain(domain, CachePolicy.custom("get_next_state"))
    results: list[int] = []

    threads = [
        threading.Thread(target=lambda: results.append(cached.get_next_state(1, 2)))
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    assert started.wait(1)
    time.sleep(0.05)
    release.set()
    for thread in threads:
        thread.join(2)

    assert results == [3] * 8
    assert domain.calls == 1
    info = cached.cache_info("get_next_state")
    assert info.misses == 1
    assert info.waits == 7


def test_shared_store_and_namespace_reuse_across_domain_wrappers() -> None:
    store = MemoryCacheStore(max_entries=16)
    first_domain = CountingDomain()
    second_domain = CountingDomain()
    policy = CachePolicy.custom("get_next_state")
    first = cache_domain(first_domain, policy, store=store, namespace="grid-v1")
    second = cache_domain(second_domain, policy, store=store, namespace="grid-v1")

    assert first.get_next_state(1, 2) == 3
    assert second.get_next_state(1, 2) == 3
    assert first_domain.calls["get_next_state"] == 1
    assert second_domain.calls == {}

    assert second.invalidate_cache("get_next_state") == 1
    assert second.get_next_state(1, 2) == 3
    assert second_domain.calls["get_next_state"] == 1


def test_method_invalidation_does_not_flush_other_capabilities() -> None:
    domain = CountingDomain()
    cached = cache_domain(
        domain,
        CachePolicy.custom("get_next_state", "get_transition_value"),
    )

    cached.get_next_state(1, 1)
    cached.get_transition_value(1, 1, 2)
    assert cached.get_next_state.cache_clear() == 1
    cached.get_next_state(1, 1)
    cached.get_transition_value(1, 1, 2)

    assert domain.calls["get_next_state"] == 2
    assert domain.calls["get_transition_value"] == 1


def test_cache_none_policy_can_skip_none_results() -> None:
    class NoneDomain:
        def __init__(self) -> None:
            self.calls = 0

        def identity(self, value):
            self.calls += 1
            return None

    domain = NoneDomain()
    cached = cache_domain(
        domain, CachePolicy.custom("identity", cache_none=False)
    )
    cached.identity(1)
    cached.identity(1)

    assert domain.calls == 2
    assert cached.cache_info().currsize == 0


def test_nested_builtin_arguments_have_stable_typed_keys() -> None:
    domain = CountingDomain()
    cached = cache_domain(domain, CachePolicy.custom("identity"))

    first = cached.identity({"a": [1, 2], "b": {3, 4}})
    second = cached.identity({"b": {4, 3}, "a": [1, 2]})
    assert first is second
    assert domain.calls["identity"] == 1

    cached.identity(1)
    cached.identity(1.0)
    assert domain.calls["identity"] == 3


def test_recursive_arguments_bypass_instead_of_recursing_forever() -> None:
    domain = CountingDomain()
    cached = cache_domain(domain, CachePolicy.custom("identity"))
    recursive = []
    recursive.append(recursive)

    assert cached.identity(recursive) is recursive
    assert cached.cache_info("identity").bypasses == 1


def test_pickle_preserves_configuration_but_not_process_local_entries() -> None:
    domain = CountingDomain()
    cached = cache_domain(
        domain,
        CachePolicy.custom("get_next_state"),
        namespace="pickle-domain",
    )
    cached.get_next_state(1, 1)

    restored = pickle.loads(pickle.dumps(cached))
    assert restored.cache_info().currsize == 0
    assert restored.get_next_state(1, 1) == 2
    assert restored.domain.calls["get_next_state"] == 2


def test_cache_domain_is_idempotent_without_reconfiguration() -> None:
    cached = cache_domain(CountingDomain(), CachePolicy.custom("get_next_state"))
    assert cache_domain(cached) is cached
