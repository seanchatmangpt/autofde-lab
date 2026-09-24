"""Deterministic passive repository inventory with bounded traversal."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_DEFAULT_EXCLUDES = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "target",
        "_build",
        ".mypy_cache",
        ".pytest_cache",
    }
)


@dataclass(frozen=True, slots=True)
class InventoryPolicy:
    excluded_directories: frozenset[str] = _DEFAULT_EXCLUDES
    max_files: int = 20_000
    max_total_bytes: int = 512_000_000
    sample_bytes: int = 8192

    def __post_init__(self) -> None:
        if self.max_files <= 0 or self.max_total_bytes <= 0:
            raise ValueError("inventory limits must be positive")


@dataclass(frozen=True, slots=True)
class InventoryEntry:
    path: str
    size: int
    executable: bool
    binary: bool
    symlink: bool


@dataclass(frozen=True, slots=True)
class RepositoryInventory:
    root: str
    entries: tuple[InventoryEntry, ...]
    skipped: tuple[tuple[str, str], ...]
    total_bytes: int

    @property
    def text_paths(self) -> tuple[str, ...]:
        return tuple(
            entry.path
            for entry in self.entries
            if not entry.binary and not entry.symlink
        )


class RepositoryInventoryScanner:
    """Walk a local checkout without executing files or following symlinks."""

    def __init__(
        self,
        root: str | Path,
        *,
        policy: InventoryPolicy | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.policy = policy or InventoryPolicy()
        if not self.root.is_dir():
            raise FileNotFoundError(self.root)

    def scan(self) -> RepositoryInventory:
        entries: list[InventoryEntry] = []
        skipped: list[tuple[str, str]] = []
        total_bytes = 0

        for current_root, dirs, files in os.walk(
            self.root,
            topdown=True,
            followlinks=False,
        ):
            current = Path(current_root)
            dirs[:] = sorted(
                directory
                for directory in dirs
                if directory not in self.policy.excluded_directories
            )
            for filename in sorted(files):
                path = current / filename
                relative = path.relative_to(self.root).as_posix()

                if path.is_symlink():
                    skipped.append((relative, "REFUSED_SYMLINK"))
                    entries.append(
                        InventoryEntry(
                            path=relative,
                            size=0,
                            executable=False,
                            binary=False,
                            symlink=True,
                        )
                    )
                    continue

                stat = path.stat()
                total_bytes += stat.st_size
                if len(entries) >= self.policy.max_files:
                    raise ValueError(
                        f"BLOCKED_INVENTORY_FILE_LIMIT:{self.policy.max_files}"
                    )
                if total_bytes > self.policy.max_total_bytes:
                    raise ValueError(
                        "BLOCKED_INVENTORY_BYTE_LIMIT:"
                        f"{self.policy.max_total_bytes}"
                    )

                with path.open("rb") as handle:
                    sample = handle.read(self.policy.sample_bytes)
                binary = b"\x00" in sample
                entries.append(
                    InventoryEntry(
                        path=relative,
                        size=stat.st_size,
                        executable=bool(stat.st_mode & 0o111),
                        binary=binary,
                        symlink=False,
                    )
                )

        return RepositoryInventory(
            root=str(self.root),
            entries=tuple(entries),
            skipped=tuple(sorted(skipped)),
            total_bytes=total_bytes,
        )
