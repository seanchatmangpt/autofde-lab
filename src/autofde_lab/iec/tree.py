"""Exact tree snapshots and translation-validation diffs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .model import digest


@dataclass(frozen=True, slots=True, order=True)
class TreeEntry:
    path: str
    content_digest: str
    mode: str = "100644"

    def __post_init__(self) -> None:
        if not self.path.strip() or not self.content_digest.strip():
            raise ValueError("tree entry requires path and content digest")


@dataclass(frozen=True, slots=True)
class TreeSnapshot:
    subject_id: str
    entries: tuple[TreeEntry, ...]

    def __post_init__(self) -> None:
        paths = [entry.path for entry in self.entries]
        if len(paths) != len(set(paths)):
            raise ValueError("duplicate path in tree snapshot")

    @classmethod
    def from_entries(
        cls,
        subject_id: str,
        entries: Iterable[TreeEntry],
    ) -> "TreeSnapshot":
        return cls(
            subject_id=subject_id,
            entries=tuple(sorted(entries, key=lambda entry: entry.path)),
        )

    @property
    def tree_digest(self) -> str:
        return digest(self.entries)


@dataclass(frozen=True, slots=True)
class TreeDiff:
    left_subject_id: str
    right_subject_id: str
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]
    unchanged: tuple[str, ...]

    @property
    def equal(self) -> bool:
        return not (self.added or self.removed or self.changed)

    @property
    def diff_id(self) -> str:
        return digest(self)


def compare_trees(left: TreeSnapshot, right: TreeSnapshot) -> TreeDiff:
    left_map = {entry.path: entry for entry in left.entries}
    right_map = {entry.path: entry for entry in right.entries}
    left_paths = set(left_map)
    right_paths = set(right_map)
    common = left_paths & right_paths
    changed = tuple(
        sorted(
            path
            for path in common
            if (
                left_map[path].content_digest != right_map[path].content_digest
                or left_map[path].mode != right_map[path].mode
            )
        )
    )
    unchanged = tuple(sorted(common - set(changed)))
    return TreeDiff(
        left_subject_id=left.subject_id,
        right_subject_id=right.subject_id,
        added=tuple(sorted(right_paths - left_paths)),
        removed=tuple(sorted(left_paths - right_paths)),
        changed=changed,
        unchanged=unchanged,
    )


def tree_equivalence_verifier(
    left: TreeSnapshot,
    right: TreeSnapshot,
) -> tuple[bool, object, object, str]:
    diff = compare_trees(left, right)
    expected = {
        "tree_digest": left.tree_digest,
        "paths": tuple(entry.path for entry in left.entries),
    }
    actual = {
        "tree_digest": right.tree_digest,
        "paths": tuple(entry.path for entry in right.entries),
        "added": diff.added,
        "removed": diff.removed,
        "changed": diff.changed,
    }
    return diff.equal, expected, actual, "byte/mode exact tree equivalence"
