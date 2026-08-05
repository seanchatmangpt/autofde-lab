# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""80/20 ERRC cache fabric for planning, RL, and scheduling.

The public module intentionally remains small. The implementation lives in
``skdecide._cache`` and provides:

* deterministic, typed, content-addressed keys;
* mutation-isolated values with digest verification and compression;
* byte-bounded TinyLFU/segmented-LRU memory caching;
* persistent SQLite/WAL storage with content deduplication;
* thread and process single-flight construction leases;
* dependency tags, explicit invalidation, receipts, and replay;
* transparent domain proxies and pickle-safe solver domain factories.

Only explicitly admitted deterministic operations are cacheable. State
actuation, random sampling, rendering, external I/O, and implicit mutable-memory
queries remain outside the cache.
"""

from skdecide import _cache as _implementation
from skdecide._cache import *

__all__ = _implementation.__all__
