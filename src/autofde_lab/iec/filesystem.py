"""Root-fenced passive filesystem reader for explicit IEC observations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .observations import PassiveFile


@dataclass(frozen=True, slots=True)
class ReadPolicy:
    max_file_bytes: int = 2_000_000
    allow_binary: bool = False

    def __post_init__(self) -> None:
        if self.max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive")


class PassiveRepositoryReader:
    """Read explicitly named files without executing or following symlinks."""

    def __init__(self, root: str | Path, *, policy: ReadPolicy | None = None) -> None:
        self.root = Path(root).resolve()
        self.policy = policy or ReadPolicy()
        if not self.root.is_dir():
            raise FileNotFoundError(self.root)

    def _resolve(self, relative_path: str) -> Path:
        candidate = self.root / relative_path
        if candidate.is_symlink():
            raise PermissionError(f"REFUSED_SYMLINK:{relative_path}")
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError(f"REFUSED_PATH_ESCAPE:{relative_path}") from exc
        return resolved

    def read(self, relative_path: str) -> PassiveFile:
        path = self._resolve(relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        size = path.stat().st_size
        if size > self.policy.max_file_bytes:
            raise ValueError(
                f"UNSUPPORTED_FILE_SIZE:{relative_path}:{size}:"
                f"{self.policy.max_file_bytes}"
            )
        content = path.read_bytes()
        if not self.policy.allow_binary and b"\x00" in content:
            raise ValueError(f"UNSUPPORTED_BINARY:{relative_path}")
        mode = path.stat().st_mode
        executable = bool(mode & 0o111)
        normalized = path.relative_to(self.root).as_posix()
        return PassiveFile(
            path=normalized,
            content=content,
            executable=executable,
        )

    def read_many(self, relative_paths: Iterable[str]) -> tuple[PassiveFile, ...]:
        paths = tuple(sorted(set(relative_paths)))
        return tuple(self.read(path) for path in paths)
