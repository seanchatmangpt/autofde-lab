# Capability-aware domain caching

`skdecide.caching` provides a shared cache at the domain capability boundary. It is designed for repeated white-box model queries made by planning, reinforcement-learning, and scheduling solvers without caching state transitions, random draws, or side effects.

## 80/20 ERRC design

| Move | Result |
|---|---|
| **Eliminate** | Solver-specific memoization and duplicate model evaluation. |
| **Reduce** | One bounded LRU store, strict TTL, normalized call keys, and namespace/method invalidation. |
| **Raise** | Explicit admission, single-flight miss coalescing, hit/miss/bypass/error evidence, and safe handling of unhashable states. |
| **Create** | A composable `CachedDomain` proxy and shareable `MemoryCacheStore` spanning equivalent domain wrappers and multiple solvers. |

The model policy caches read-only model descriptions and predicates. `CachePolicy.scheduling()` extends it with deterministic task-duration, resource, mode, precedence, skill, cost, and time-window queries. It always refuses `reset`, `step`, `sample`, `set_memory`, `render`, and `close`. Calls such as `get_applicable_actions()` that omit their `memory` argument bypass the cache because they depend on mutable internal domain memory; pass memory explicitly to admit reuse.

## Basic use

```python
from skdecide.caching import CachePolicy, cache_domain

cached_domain = cache_domain(
    domain,
    CachePolicy.scheduling(max_entries=16_384, ttl_seconds=None),
)

# Repeated solver/model calls now reuse admitted results.
next_state = cached_domain.get_next_state(state, action)
print(cached_domain.cache_info("get_next_state"))
```

## Reuse across equivalent domain instances

Reuse requires both a shared store and an explicit namespace. The namespace is the caller's assertion that the wrapped domains have equivalent model semantics and configuration.

```python
from skdecide.caching import CachePolicy, MemoryCacheStore, cache_domain

store = MemoryCacheStore(max_entries=100_000)
policy = CachePolicy.model()

training = cache_domain(training_domain, policy, store=store, namespace=("warehouse", "v3"))
evaluation = cache_domain(evaluation_domain, policy, store=store, namespace=("warehouse", "v3"))
```

Invalidate after any external model/configuration change:

```python
training.invalidate_cache()                    # all methods in this namespace
training.invalidate_cache("get_transition_value")  # one capability
```

## Custom state keys

Nested built-in containers and dataclasses are normalized automatically. An unsupported state bypasses caching by default. Add a deterministic `__cache_key__()` method or provide a per-method key function to admit it. Set `on_unhashable="raise"` when unsupported keys must fail closed.

The in-memory store is process-local. Pickling a `CachedDomain` preserves the wrapped domain, policy, namespace, and key functions but intentionally starts with an empty cache in the receiving process. Custom key functions must themselves be pickleable when the wrapper crosses a process boundary. Cached return values should be treated as immutable, as with the framework's existing cached spaces and distributions.
