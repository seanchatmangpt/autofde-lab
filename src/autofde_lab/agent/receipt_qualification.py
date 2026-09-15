"""Exact-head receipt qualification guard (AFDE-2603).

Machine rule encoding the stale-SHA episode of 2026-09-15: **a receipt's
qualification expires whenever the subject head moves.** A receipt document
may record standing *bound to the head it qualified at* (point-in-time
history), but it must not express an unbound *current* standing claim --
"the branch is green/ALIVE" without naming the head -- because such a claim
silently outlives the commit it was earned on.

The guard scans receipt documents for:

- a qualified head anchor, e.g. ``**Exact Head Commit**: `1605cfc9...````
  (the ``(capstone scope)`` qualifier is tolerated);
- a current-standing claim, e.g. ``**Final Standing**: `ALIVE```` or
  ``PR ... is pushed, verified, green``.

Verdicts:

- ``QUALIFIED`` -- anchored, and either current or making no current-standing
  claim;
- ``REFUSED_STALE_QUALIFICATION`` -- the anchor is not the current head
  *and* the document claims current standing: the claim is refused and the
  head mismatch surfaced, never silently retained;
- ``EXPIRED_POINT_IN_TIME`` -- the anchor is not the current head and the
  document's standing claim is explicitly bound to its qualified head
  (lawful historical record).

This module only computes verdicts; it never edits documents or blocks
anything itself. Enforcement is the Chicago suite driving it plus its line
in the PR qualification gate.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

VERDICT_QUALIFIED = "QUALIFIED"
VERDICT_REFUSED_STALE = "REFUSED_STALE_QUALIFICATION"
VERDICT_EXPIRED_POINT_IN_TIME = "EXPIRED_POINT_IN_TIME"

# ``**Exact Head Commit**: `sha``` / ``**Exact Head Commit (scope)**: `sha````
_QUALIFIED_HEAD_RE = re.compile(
    r"\*{1,2}Exact Head Commit[^*]*\*{1,2}:\s*`([0-9a-f]{7,40})`",
    re.IGNORECASE,
)

# Unbound *current* standing claims -- the phrasings the stale episode used.
_CURRENT_STANDING_RES = (
    re.compile(r"\*{1,2}Final Standing\*{1,2}:\s*`?ALIVE`?", re.IGNORECASE),
    re.compile(r"\bpushed, verified, green\b", re.IGNORECASE),
)

# Standing explicitly bound to the qualified head (lawful point-in-time form).
_BOUND_STANDING_RE = re.compile(
    r"Standing (?:at|on) (?:qualified )?head `?[0-9a-f]{7,40}`?", re.IGNORECASE
)

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class ReceiptQualification:
    """One receipt document's qualification verdict."""

    document: Path
    qualified_head: str | None
    current_head: str
    verdict: str
    detail: str


def resolve_current_head(repo_root: Path | None = None) -> str:
    """Resolve the repository's exact current HEAD SHA."""
    root = repo_root or Path(__file__).resolve().parents[3]
    proc = subprocess.run(  # noqa: S603 -- fixed argv, repo-scoped
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"failed to resolve HEAD: {proc.stderr.strip()}")
    return proc.stdout.strip()


def evaluate_receipt_document(
    document: Path,
    current_head: str,
) -> ReceiptQualification:
    """Evaluate one receipt document against the exact current head."""
    if not _FULL_SHA_RE.match(current_head):
        raise ValueError(
            f"current_head must be a full 40-char SHA, got {current_head!r}"
        )
    text = document.read_text(encoding="utf-8")

    match = _QUALIFIED_HEAD_RE.search(text)
    qualified_head = match.group(1) if match else None
    if qualified_head is not None:
        qualified_head = qualified_head.lower()

    unbound_claim = any(r.search(text) for r in _CURRENT_STANDING_RES)
    bound_claim = bool(_BOUND_STANDING_RE.search(text))

    if qualified_head is None:
        verdict = VERDICT_QUALIFIED
        detail = "no qualified-head anchor; nothing to invalidate"
    elif qualified_head == current_head.lower():
        verdict = VERDICT_QUALIFIED
        detail = f"qualified head {qualified_head[:12]} is the current head"
    elif unbound_claim:
        verdict = VERDICT_REFUSED_STALE
        detail = (
            f"receipt claims current standing but its qualified head "
            f"{qualified_head[:12]} is not the current head "
            f"{current_head[:12]} -- the claim is expired; re-qualify at "
            "the current head or bind the standing claim to the qualified head"
        )
    elif bound_claim:
        verdict = VERDICT_EXPIRED_POINT_IN_TIME
        detail = (
            f"standing claim is bound to qualified head {qualified_head[:12]}; "
            "expired as a current claim (lawful historical record)"
        )
    else:
        verdict = VERDICT_EXPIRED_POINT_IN_TIME
        detail = (
            f"qualified head {qualified_head[:12]} is historical; document "
            "makes no current-standing claim"
        )

    return ReceiptQualification(
        document=document,
        qualified_head=qualified_head,
        current_head=current_head,
        verdict=verdict,
        detail=detail,
    )


def verify_repo_receipts(
    docs_root: Path,
    current_head: str,
) -> tuple[ReceiptQualification, ...]:
    """Evaluate every receipt-named document under ``docs_root``.

    Any ``REFUSED_STALE_QUALIFICATION`` verdict is a gate failure for the
    caller to surface; this function reports, it does not raise.
    """
    receipts = sorted(p for p in docs_root.rglob("*.md") if "receipt" in p.name.lower())
    return tuple(evaluate_receipt_document(doc, current_head) for doc in receipts)
