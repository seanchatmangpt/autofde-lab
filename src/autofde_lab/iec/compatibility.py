"""Public-interface compatibility deltas for translation validation."""

from __future__ import annotations

from dataclasses import dataclass

from .model import digest
from .python_api import PublicSymbol, PythonApiSurface


@dataclass(frozen=True, slots=True)
class CompatibilityDelta:
    original_surface_id: str
    candidate_surface_id: str
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]

    @property
    def breaking_candidate(self) -> bool:
        return bool(self.removed or self.changed)

    @property
    def delta_id(self) -> str:
        return digest(self)


def compare_python_api(
    original: PythonApiSurface,
    candidate: PythonApiSurface,
) -> CompatibilityDelta:
    left = {(symbol.kind, symbol.name): symbol for symbol in original.symbols}
    right = {(symbol.kind, symbol.name): symbol for symbol in candidate.symbols}
    left_keys = set(left)
    right_keys = set(right)

    added = tuple(
        sorted(f"{kind}:{name}" for kind, name in right_keys - left_keys)
    )
    removed = tuple(
        sorted(f"{kind}:{name}" for kind, name in left_keys - right_keys)
    )
    changed = tuple(
        sorted(
            f"{kind}:{name}"
            for kind, name in left_keys & right_keys
            if _symbol_contract(left[(kind, name)])
            != _symbol_contract(right[(kind, name)])
        )
    )
    return CompatibilityDelta(
        original_surface_id=original.surface_id,
        candidate_surface_id=candidate.surface_id,
        added=added,
        removed=removed,
        changed=changed,
    )


def _symbol_contract(symbol: PublicSymbol) -> tuple[str, tuple[str, ...]]:
    return symbol.signature, symbol.decorators
