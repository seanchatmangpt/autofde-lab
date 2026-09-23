"""Content-addressed observation cache identities and dependency invalidation."""

from __future__ import annotations

from dataclasses import dataclass

from .model import digest


@dataclass(frozen=True, slots=True)
class CacheKey:
    subject_id: str
    extractor_id: str
    extractor_version: str
    input_digest: str
    config_digest: str = "none"
    dependency_digest: str = "none"

    @property
    def key(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class CacheEntry:
    key: CacheKey
    output_digest: str
    dependency_keys: tuple[str, ...] = ()


class ObservationCache:
    """In-memory reference implementation of identity-safe reuse semantics."""

    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._dependents: dict[str, set[str]] = {}

    def put(self, entry: CacheEntry) -> None:
        key = entry.key.key
        self._entries[key] = entry
        for dependency in entry.dependency_keys:
            self._dependents.setdefault(dependency, set()).add(key)

    def get(self, key: CacheKey) -> CacheEntry | None:
        return self._entries.get(key.key)

    def invalidate(self, key: CacheKey) -> tuple[str, ...]:
        """Invalidate one identity and all transitively dependent evidence."""

        root = key.key
        stack = [root]
        invalidated: set[str] = set()
        while stack:
            current = stack.pop()
            if current in invalidated:
                continue
            invalidated.add(current)
            stack.extend(sorted(self._dependents.get(current, ())))
        for identity in invalidated:
            self._entries.pop(identity, None)
            self._dependents.pop(identity, None)
        for dependents in self._dependents.values():
            dependents.difference_update(invalidated)
        return tuple(sorted(invalidated))

    def identities(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))
