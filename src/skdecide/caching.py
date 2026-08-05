# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Capability-aware caching for scikit-decide domains.

The cache is deliberately applied as a domain proxy instead of being embedded in
individual solvers. This lets multiple solvers reuse the same admitted model
queries while keeping stateful and stochastic operations outside the cache.
"""

from __future__ import annotations

import dataclasses
import functools
import inspect
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

__all__ = [
    "CONSTANT_CAPABILITY_METHODS",
    "MODEL_CAPABILITY_METHODS",
    "SCHEDULING_CAPABILITY_METHODS",
    "UNSAFE_CAPABILITY_METHODS",
    "CacheInfo",
    "CachePolicy",
    "CachedDomain",
    "MemoryCacheStore",
    "UnhashableCacheKeyError",
    "UnsafeCacheMethodError",
    "cache_domain",
]

_T = TypeVar("_T")
_MISSING = object()

# Constant capability descriptions already have small local caches in several
# builders. Keeping them in the shared policy lets equivalent domain wrappers
# and multiple solvers reuse one admitted result instead of rebuilding it.
CONSTANT_CAPABILITY_METHODS = frozenset(
    {
        "get_action_space",
        "get_constraints",
        "get_goals",
        "get_initial_state",
        "get_initial_state_distribution",
        "get_memory_maxlen",
        "get_observation_space",
        "is_transition_value_dependent_on_next_state",
    }
)

# Read-only white-box model queries. The model policy is explicit opt-in because
# domains can represent non-stationary systems even when the method name looks
# pure. Sampling remains outside this set: distributions may be cached, draws
# from those distributions may not.
MODEL_CAPABILITY_METHODS = CONSTANT_CAPABILITY_METHODS | frozenset(
    {
        "get_action_mask",
        "get_applicable_actions",
        "get_enabled_events",
        "get_next_state",
        "get_next_state_distribution",
        "get_observation",
        "get_observation_distribution",
        "get_transition_value",
        "is_action",
        "is_applicable_action",
        "is_enabled_event",
        "is_goal",
        "is_observation",
        "is_terminal",
    }
)


# High-value read-only scheduling descriptions and predicates. These methods
# cover the static model surfaces repeatedly traversed by scheduling solvers;
# stochastic duration/resource draws remain explicitly refused.
SCHEDULING_CAPABILITY_METHODS = frozenset(
    {
        "all_tasks_possible",
        "check_if_skills_are_fulfilled",
        "check_unique_resource_names",
        "find_one_ressource_to_do_one_task",
        "get_all_resources_skills",
        "get_all_tasks_skills",
        "get_mode_costs",
        "get_non_zero_ressource_need_names",
        "get_original_quantity_resource",
        "get_preallocations",
        "get_predecessors",
        "get_predecessors_task",
        "get_quantity_resource",
        "get_resource_cost_per_time_unit",
        "get_resource_need",
        "get_resource_need_at_time",
        "get_resource_renewability",
        "get_resource_type_for_unit",
        "get_resource_types_names",
        "get_resource_units_names",
        "get_ressource_names",
        "get_ressource_names_for_task_mode",
        "get_skills_names",
        "get_skills_of_resource",
        "get_skills_of_task",
        "get_successors",
        "get_successors_task",
        "get_task_consumption",
        "get_task_duration",
        "get_task_duration_distribution",
        "get_task_duration_lower_bound",
        "get_task_duration_upper_bound",
        "get_task_modes",
        "get_task_paused_non_renewable_resource_returned",
        "get_task_preemptivity",
        "get_task_resuming_type",
        "get_tasks_ids",
        "get_tasks_mode",
        "get_tasks_modes",
        "get_time_lags",
        "get_time_window",
        "is_renewable",
        "task_modes_possible_to_launch",
        "task_possible_to_launch_precedence",
    }
)

# These operations either mutate a domain, consume external state, draw random
# values, or perform side effects. They are refused even when a caller includes
# them in a custom policy.
UNSAFE_CAPABILITY_METHODS = frozenset(
    {
        "close",
        "compute_graph",
        "get_latest_sampled_duration",
        "render",
        "reset",
        "sample",
        "sample_quantity_resource",
        "sample_task_duration",
        "set_memory",
        "step",
    }
)

# These methods silently use domain._memory when memory is omitted. Caching that
# implicit call would return stale answers after reset()/step()/set_memory().
_EXPLICIT_MEMORY_METHODS = frozenset(
    {
        "get_action_mask",
        "get_applicable_actions",
        "get_enabled_events",
        "is_applicable_action",
        "is_enabled_event",
    }
)


class UnsafeCacheMethodError(ValueError):
    """Raised when a cache policy tries to admit a stateful or stochastic call."""


class UnhashableCacheKeyError(TypeError):
    """Raised when a call cannot be converted into a deterministic cache key."""


@dataclass(frozen=True)
class CacheInfo:
    """Observable cache counters for a store, namespace, or method."""

    hits: int
    misses: int
    waits: int
    stores: int
    evictions: int
    expirations: int
    bypasses: int
    errors: int
    invalidations: int
    currsize: int
    maxsize: int

    @property
    def hit_rate(self) -> float:
        """Return hits divided by cacheable completed lookups."""

        denominator = self.hits + self.misses + self.waits
        return self.hits / denominator if denominator else 0.0


@dataclass(frozen=True)
class CachePolicy:
    """Admission and resource policy for a :class:`CachedDomain`.

    Parameters
    ----------
    methods:
        Public domain methods admitted to the cache.
    max_entries:
        Capacity used when the wrapper creates its own in-memory store.
    ttl_seconds:
        Optional strict time-to-live. Expired values are never served.
    single_flight:
        Coalesce concurrent misses for the same key into one computation.
    cache_none:
        Whether ``None`` is a valid cached result.
    on_unhashable:
        ``"bypass"`` preserves domain behavior for unsupported state objects;
        ``"raise"`` makes missing key support an explicit error.
    """

    methods: frozenset[str]
    max_entries: int = 4096
    ttl_seconds: float | None = None
    single_flight: bool = True
    cache_none: bool = True
    on_unhashable: Literal["bypass", "raise"] = "bypass"

    def __post_init__(self) -> None:
        methods = frozenset(self.methods)
        object.__setattr__(self, "methods", methods)
        if self.max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        if self.ttl_seconds is not None and self.ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive or None")
        if self.on_unhashable not in {"bypass", "raise"}:
            raise ValueError("on_unhashable must be 'bypass' or 'raise'")
        malformed = {m for m in methods if not isinstance(m, str) or not m}
        if malformed:
            raise ValueError(
                "cache method names must be non-empty strings: "
                f"{malformed!r}"
            )
        private = {
            m for m in methods if isinstance(m, str) and m.startswith("_")
        }
        sampling = {
            m for m in methods if isinstance(m, str) and m.startswith("sample")
        }
        refused = (methods & UNSAFE_CAPABILITY_METHODS) | sampling
        if private or refused:
            names = sorted(private | refused)
            raise UnsafeCacheMethodError(
                "stateful, stochastic, side-effecting, and private methods cannot be "
                f"cached: {', '.join(names)}"
            )

    @classmethod
    def constants(cls, **kwargs: Any) -> CachePolicy:
        """Create a policy for constant domain capability descriptions."""

        return cls(methods=CONSTANT_CAPABILITY_METHODS, **kwargs)

    @classmethod
    def model(cls, **kwargs: Any) -> CachePolicy:
        """Create the 80/20 policy for stationary white-box model queries."""

        return cls(methods=MODEL_CAPABILITY_METHODS, **kwargs)

    @classmethod
    def scheduling(cls, **kwargs: Any) -> CachePolicy:
        """Create a policy spanning generic and scheduling model queries."""

        return cls(
            methods=MODEL_CAPABILITY_METHODS | SCHEDULING_CAPABILITY_METHODS,
            **kwargs,
        )

    @classmethod
    def custom(cls, *methods: str, **kwargs: Any) -> CachePolicy:
        """Create a policy with an explicit method allow-list."""

        return cls(methods=frozenset(methods), **kwargs)

    def with_methods(self, *methods: str) -> CachePolicy:
        """Return a policy admitting additional read-only methods."""

        return dataclasses.replace(self, methods=self.methods | frozenset(methods))

    def without_methods(self, *methods: str) -> CachePolicy:
        """Return a policy excluding methods from this policy."""

        return dataclasses.replace(self, methods=self.methods - frozenset(methods))


@dataclass
class _Counters:
    hits: int = 0
    misses: int = 0
    waits: int = 0
    stores: int = 0
    evictions: int = 0
    expirations: int = 0
    bypasses: int = 0
    errors: int = 0
    invalidations: int = 0


@dataclass
class _Entry:
    value: Any
    expires_at: float | None


@dataclass
class _Flight:
    event: threading.Event
    value: Any = _MISSING
    error: BaseException | None = None


class MemoryCacheStore:
    """Thread-safe bounded LRU store with TTL, invalidation, and single-flight.

    A store can be shared by multiple :class:`CachedDomain` instances. Shared
    reuse only occurs when wrappers also use the same explicit namespace.
    """

    def __init__(
        self,
        max_entries: int = 4096,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[tuple[Any, ...], _Entry] = OrderedDict()
        self._flights: dict[tuple[Any, ...], _Flight] = {}
        self._counters: dict[tuple[Hashable, str], _Counters] = {}
        self._global_generation = 0
        self._namespace_generations: dict[Hashable, int] = {}
        self._method_generations: dict[tuple[Hashable, str], int] = {}
        self._lock = threading.RLock()

    @property
    def max_entries(self) -> int:
        return self._max_entries

    def _counter(self, namespace: Hashable, method: str) -> _Counters:
        return self._counters.setdefault((namespace, method), _Counters())

    def record_bypass(self, namespace: Hashable, method: str) -> None:
        with self._lock:
            self._counter(namespace, method).bypasses += 1

    def _token(self, namespace: Hashable, method: str) -> tuple[int, int, int]:
        return (
            self._global_generation,
            self._namespace_generations.get(namespace, 0),
            self._method_generations.get((namespace, method), 0),
        )

    def get_or_compute(
        self,
        *,
        namespace: Hashable,
        method: str,
        call_key: Hashable,
        compute: Callable[[], _T],
        ttl_seconds: float | None,
        single_flight: bool,
        cache_none: bool,
    ) -> _T:
        """Return a cached value or compute it exactly once per concurrent key."""

        with self._lock:
            token = self._token(namespace, method)
            key = (namespace, method, token, call_key)
            now = self._clock()
            entry = self._entries.get(key)
            if entry is not None:
                if entry.expires_at is None or entry.expires_at > now:
                    self._entries.move_to_end(key)
                    self._counter(namespace, method).hits += 1
                    return entry.value
                del self._entries[key]
                self._counter(namespace, method).expirations += 1

            if single_flight:
                flight = self._flights.get(key)
                if flight is not None:
                    self._counter(namespace, method).waits += 1
                    leader = False
                else:
                    flight = _Flight(threading.Event())
                    self._flights[key] = flight
                    self._counter(namespace, method).misses += 1
                    leader = True
            else:
                flight = None
                self._counter(namespace, method).misses += 1
                leader = True

        if not leader:
            assert flight is not None
            flight.event.wait()
            if flight.error is not None:
                raise flight.error
            return flight.value

        try:
            value = compute()
        except BaseException as error:
            with self._lock:
                self._counter(namespace, method).errors += 1
                if flight is not None:
                    flight.error = error
                    flight.event.set()
                    self._flights.pop(key, None)
            raise

        with self._lock:
            # Invalidation changes the token. A computation started before an
            # invalidation may finish, but its old-token value can never be hit.
            if cache_none or value is not None:
                expires_at = (
                    None if ttl_seconds is None else self._clock() + ttl_seconds
                )
                self._entries[key] = _Entry(value=value, expires_at=expires_at)
                self._entries.move_to_end(key)
                counters = self._counter(namespace, method)
                counters.stores += 1
                while len(self._entries) > self._max_entries:
                    evicted_key, _ = self._entries.popitem(last=False)
                    evicted_namespace, evicted_method = evicted_key[:2]
                    self._counter(evicted_namespace, evicted_method).evictions += 1

            if flight is not None:
                flight.value = value
                flight.event.set()
                self._flights.pop(key, None)

        return value

    def invalidate(self, namespace: Hashable, method: str | None = None) -> int:
        """Invalidate one namespace or one method and return removed entries."""

        with self._lock:
            if method is None:
                self._namespace_generations[namespace] = (
                    self._namespace_generations.get(namespace, 0) + 1
                )
            else:
                generation_key = (namespace, method)
                self._method_generations[generation_key] = (
                    self._method_generations.get(generation_key, 0) + 1
                )

            keys = [
                key
                for key in self._entries
                if key[0] == namespace and (method is None or key[1] == method)
            ]
            for key in keys:
                del self._entries[key]

            affected = [
                counter
                for (counter_namespace, counter_method), counter
                in self._counters.items()
                if counter_namespace == namespace
                and (method is None or counter_method == method)
            ]
            if affected:
                for counter in affected:
                    counter.invalidations += 1
            elif method is not None:
                self._counter(namespace, method).invalidations += 1
            return len(keys)

    def clear(self, *, reset_stats: bool = False) -> int:
        """Invalidate the complete store and return the number of removed entries."""

        with self._lock:
            size = len(self._entries)
            self._entries.clear()
            self._global_generation += 1
            for counter in self._counters.values():
                counter.invalidations += 1
            if reset_stats:
                self._counters.clear()
            return size

    def info(
        self, namespace: Hashable | None = None, method: str | None = None
    ) -> CacheInfo:
        """Return aggregate counters, optionally scoped by namespace and method."""

        with self._lock:
            counters = [
                counter
                for (counter_namespace, counter_method), counter
                in self._counters.items()
                if (namespace is None or counter_namespace == namespace)
                and (method is None or counter_method == method)
            ]
            size = sum(
                1
                for key in self._entries
                if (namespace is None or key[0] == namespace)
                and (method is None or key[1] == method)
            )
            return CacheInfo(
                hits=sum(c.hits for c in counters),
                misses=sum(c.misses for c in counters),
                waits=sum(c.waits for c in counters),
                stores=sum(c.stores for c in counters),
                evictions=sum(c.evictions for c in counters),
                expirations=sum(c.expirations for c in counters),
                bypasses=sum(c.bypasses for c in counters),
                errors=sum(c.errors for c in counters),
                invalidations=sum(c.invalidations for c in counters),
                currsize=size,
                maxsize=self._max_entries,
            )


def _freeze(value: Any, active: set[int] | None = None) -> Hashable:
    """Convert common nested values into typed, deterministic hashable keys."""

    if active is None:
        active = set()

    if hasattr(value, "__cache_key__"):
        return (type(value), _freeze(value.__cache_key__(), active))

    if isinstance(value, (str, bytes, int, float, complex, bool, type(None))):
        return (type(value), value)
    if isinstance(value, (bytearray, memoryview)):
        return (bytes, bytes(value))

    is_recursive = dataclasses.is_dataclass(value) or isinstance(
        value, (Mapping, tuple, list, set, frozenset)
    )
    marker = id(value)
    if is_recursive:
        if marker in active:
            raise UnhashableCacheKeyError("recursive values require a custom cache key")
        active.add(marker)

    try:
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            fields = tuple(
                (field.name, _freeze(getattr(value, field.name), active))
                for field in dataclasses.fields(value)
            )
            return (type(value), fields)
        if isinstance(value, Mapping):
            return (
                type(value),
                frozenset(
                    (_freeze(key, active), _freeze(item, active))
                    for key, item in value.items()
                ),
            )
        if isinstance(value, tuple):
            return (type(value), tuple(_freeze(item, active) for item in value))
        if isinstance(value, list):
            return (list, tuple(_freeze(item, active) for item in value))
        if isinstance(value, (set, frozenset)):
            return (type(value), frozenset(_freeze(item, active) for item in value))
        if isinstance(value, Hashable):
            return (type(value), value)
    finally:
        if is_recursive:
            active.remove(marker)

    raise UnhashableCacheKeyError(
        f"{type(value).__qualname__} is not safely hashable; define __cache_key__ "
        "or pass a method key function"
    )


def _restore_cached_domain(
    domain: Any,
    policy: CachePolicy,
    namespace: Hashable,
    key_functions: Mapping[str, Callable[..., Any]],
) -> "CachedDomain":
    return CachedDomain(
        domain, policy, namespace=namespace, key_functions=key_functions
    )


class CachedDomain:
    """Transparent domain proxy applying an explicit :class:`CachePolicy`.

    Non-admitted attributes and methods are delegated unchanged. The default
    namespace is unique to this wrapper; pass a stable hashable namespace and a
    shared store to reuse values across equivalent domain instances.
    """

    def __init__(
        self,
        domain: Any,
        policy: CachePolicy | None = None,
        *,
        store: MemoryCacheStore | None = None,
        namespace: Hashable | None = None,
        key_functions: Mapping[str, Callable[..., Any]] | None = None,
    ) -> None:
        policy = policy or CachePolicy.model()
        namespace = object() if namespace is None else namespace
        try:
            hash(namespace)
        except TypeError as error:
            raise TypeError("cache namespace must be hashable") from error

        object.__setattr__(self, "_cached_domain", domain)
        object.__setattr__(self, "_cache_policy", policy)
        object.__setattr__(
            self,
            "_cache_store",
            store or MemoryCacheStore(max_entries=policy.max_entries),
        )
        object.__setattr__(self, "_cache_namespace", namespace)
        object.__setattr__(self, "_cache_key_functions", dict(key_functions or {}))
        object.__setattr__(self, "_cache_wrappers", {})

    @property
    def __class__(self):  # type: ignore[override]
        # CPython's isinstance() honors a proxy's __class__ attribute.
        return self._cached_domain.__class__

    @property
    def domain(self) -> Any:
        """Return the unwrapped domain."""

        return self._cached_domain

    @property
    def policy(self) -> CachePolicy:
        return self._cache_policy

    @property
    def store(self) -> MemoryCacheStore:
        return self._cache_store

    @property
    def namespace(self) -> Hashable:
        return self._cache_namespace

    def cache_info(self, method: str | None = None) -> CacheInfo:
        return self._cache_store.info(self._cache_namespace, method)

    def invalidate_cache(self, method: str | None = None) -> int:
        """Invalidate this domain namespace or one admitted method."""

        return self._cache_store.invalidate(self._cache_namespace, method)

    def _bind_call(
        self,
        target: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> inspect.BoundArguments | None:
        try:
            bound = inspect.signature(target).bind(*args, **kwargs)
        except (TypeError, ValueError):
            return None
        bound.apply_defaults()
        return bound

    def _call_key(
        self,
        method: str,
        target: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Hashable | object:
        bound = self._bind_call(target, args, kwargs)
        if method in _EXPLICIT_MEMORY_METHODS:
            if bound is None or bound.arguments.get("memory") is None:
                return _MISSING

        key_function = self._cache_key_functions.get(method)
        if key_function is not None:
            return _freeze(key_function(*args, **kwargs))
        if bound is not None:
            return _freeze(tuple(bound.arguments.items()))
        return _freeze((args, kwargs))

    def _cached_method(
        self, method: str, target: Callable[..., _T]
    ) -> Callable[..., _T]:
        @functools.wraps(target)
        def call(*args: Any, **kwargs: Any) -> _T:
            try:
                call_key = self._call_key(method, target, args, kwargs)
            except UnhashableCacheKeyError:
                if self._cache_policy.on_unhashable == "raise":
                    raise
                self._cache_store.record_bypass(self._cache_namespace, method)
                return target(*args, **kwargs)

            if call_key is _MISSING:
                self._cache_store.record_bypass(self._cache_namespace, method)
                return target(*args, **kwargs)

            return self._cache_store.get_or_compute(
                namespace=self._cache_namespace,
                method=method,
                call_key=call_key,
                compute=lambda: target(*args, **kwargs),
                ttl_seconds=self._cache_policy.ttl_seconds,
                single_flight=self._cache_policy.single_flight,
                cache_none=self._cache_policy.cache_none,
            )

        call.cache_info = lambda: self.cache_info(method)  # type: ignore[attr-defined]
        call.cache_clear = (  # type: ignore[attr-defined]
            lambda: self.invalidate_cache(method)
        )
        return call

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._cached_domain, name)
        if name not in self._cache_policy.methods or not callable(target):
            return target
        wrappers = self._cache_wrappers
        wrapper = wrappers.get(name)
        if wrapper is None:
            wrapper = self._cached_method(name, target)
            wrappers[name] = wrapper
        return wrapper

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_cache") or name == "_cached_domain":
            object.__setattr__(self, name, value)
        else:
            setattr(self._cached_domain, name, value)

    def __dir__(self) -> list[str]:
        return sorted(set(object.__dir__(self)) | set(dir(self._cached_domain)))

    def __repr__(self) -> str:
        return f"CachedDomain({self._cached_domain!r}, policy={self._cache_policy!r})"

    def __reduce_ex__(self, protocol: int):
        return (
            _restore_cached_domain,
            (
                self._cached_domain,
                self._cache_policy,
                self._cache_namespace,
                self._cache_key_functions,
            ),
        )

    def __getstate__(self) -> dict[str, Any]:
        # Locks, in-flight calls, and cached values are process-local. A fresh
        # store after unpickling avoids the wrapt-style unpicklable cache issue.
        return {
            "domain": self._cached_domain,
            "policy": self._cache_policy,
            "namespace": self._cache_namespace,
            "key_functions": self._cache_key_functions,
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__init__(
            state["domain"],
            state["policy"],
            namespace=state["namespace"],
            key_functions=state["key_functions"],
        )


def cache_domain(
    domain: Any,
    policy: CachePolicy | None = None,
    *,
    store: MemoryCacheStore | None = None,
    namespace: Hashable | None = None,
    key_functions: Mapping[str, Callable[..., Any]] | None = None,
) -> CachedDomain:
    """Wrap a domain in a capability-aware cache.

    Calling this function on an existing :class:`CachedDomain` returns it
    unchanged when no replacement configuration is supplied.
    """

    if (
        isinstance(domain, CachedDomain)
        and policy is None
        and store is None
        and namespace is None
        and key_functions is None
    ):
        return domain
    return CachedDomain(
        domain,
        policy,
        store=store,
        namespace=namespace,
        key_functions=key_functions,
    )
