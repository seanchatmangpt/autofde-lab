"""Exact-subject and epoch identity; digests use the repo-wide canonical serializer."""
from autofde_lab.fabric.canonical import sha256 as canonical_digest

__all__ = ["canonical_digest", "require_distinct_epochs", "require_same_subject"]


def require_same_subject(a, b):
    if not a or a != b:
        raise ValueError("PTD exact-subject mismatch")


def require_distinct_epochs(a, b):
    if not a or not b or a == b:
        raise ValueError("PTD requires distinct epochs")
