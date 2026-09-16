"""Exact-head receipt qualification guard (AFDE-2603, hardened).

Machine rule encoding the stale-SHA episode of 2026-09-15: **a receipt's
qualification expires whenever the subject head moves.** A receipt document
may record standing *bound to the head it qualified at* (point-in-time
history), but it must not express an unbound *current* standing claim --
"the branch is green/ALIVE" without naming the head -- because such a claim
silently outlives the commit it was earned on.

Hardened semantics (second pass, after the gap audit showed the first
version was fail-open):

- A document with a current-standing claim and **no** qualified-head anchor
  is refused (``REFUSED_UNANCHORED_STANDING``): omitting the anchor must
  not be an escape hatch.
- Claim detection covers the phrasings actually seen in this repo
  (``**Standing:** `ALIVE````, ``**Final Standing**: `ALIVE````,
  "pushed, verified, green", "CI green"), with bound forms
  (``Standing at qualified head `sha```) excluded from matching.
- An abbreviated anchor (>= 7 hex chars) counts as matching the current
  head iff it is a prefix of it -- the same abbreviation convention the
  verdict details themselves use.
- The repo-wide scan evaluates **every** Markdown document under ``docs/``
  (content-based). Enforcement (refusal verdicts) applies to
  *receipt-named* documents -- the qualification artifact class AFDE-2603
  governs; standing ledgers and status pages (non-receipt names) receive
  note verdicts only, since re-anchoring living ledgers on every edit is
  their own maintenance discipline, not receipt qualification.

Verdicts:

- ``QUALIFIED`` -- anchored and current, or no anchor and no claim.
- ``REFUSED_STALE_QUALIFICATION`` -- anchored, not current, unbound claim.
- ``REFUSED_UNANCHORED_STANDING`` -- unanchored current-standing claim.
- ``EXPIRED_POINT_IN_TIME`` -- anchored, not current, claim bound to the
  qualified head (or no current claim at all): lawful history.

This module only computes verdicts; it never edits documents or blocks
anything itself. Enforcement is the Chicago suite driving it plus its line
in the PR qualification gate. Standalone use:

    python -m autofde_lab.agent.receipt_qualification [--docs-root DIR]

exits non-zero if any document is refused.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VERDICT_QUALIFIED = "QUALIFIED"
VERDICT_REFUSED_STALE = "REFUSED_STALE_QUALIFICATION"
VERDICT_REFUSED_UNANCHORED = "REFUSED_UNANCHORED_STANDING"
VERDICT_EXPIRED_POINT_IN_TIME = "EXPIRED_POINT_IN_TIME"

# ``**Exact Head Commit**: `sha``` / ``**Exact Head Commit (scope)**: `sha```
# / a bare ``qualified head `sha``` binding phrase.
_QUALIFIED_HEAD_RES = (
    re.compile(
        r"\*{1,2}Exact Head Commit[^*]*\*{1,2}:\s*`([0-9a-f]{7,40})`",
        re.IGNORECASE,
    ),
    re.compile(
        r"[Qq]ualified head\s*`?([0-9a-f]{7,40})`?",
        re.IGNORECASE,
    ),
)

# Bound point-in-time claims -- matched FIRST and removed before unbound
# claim detection so the lawful form can never double as a violation.
_BOUND_CLAIM_RE = re.compile(
    r"[Ss]tanding (?:at|on) (?:the )?(?:qualified )?head `?[0-9a-f]{7,40}`?[^\n]{0,80}",
    re.IGNORECASE,
)

# Unbound *current* standing claims -- the phrasings observed in this repo.
_UNBOUND_CLAIM_RES = (
    re.compile(
        r"\*{0,2}(?:Final )?[Ss]tanding:?\*{0,2}\s*[:=]?\s*`?ALIVE`?", re.IGNORECASE
    ),
    re.compile(r"\bpushed,?\s+verified,?\s+green\b", re.IGNORECASE),
    re.compile(r"\bCI is green\b", re.IGNORECASE),
    re.compile(r"\bbranch is green\b", re.IGNORECASE),
)

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ABBREV_SHA_RE = re.compile(r"^[0-9a-f]{7,39}$")


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


def _anchor_matches_current(qualified_head: str, current_head: str) -> bool:
    """Exact match, or an abbreviated anchor that is a prefix of HEAD.

    Abbreviations of >= 7 hex chars are the convention this module's own
    details use; a 7-char prefix that IS the head must not be refused as
    stale.
    """
    q = qualified_head.lower()
    c = current_head.lower()
    if q == c:
        return True
    return bool(_ABBREV_SHA_RE.match(q)) and c.startswith(q)


def _has_unbound_current_claim(text: str) -> bool:
    """True if the text claims current standing outside a bound form."""
    residual = _BOUND_CLAIM_RE.sub("", text)
    return any(r.search(residual) for r in _UNBOUND_CLAIM_RES)


def evaluate_receipt_document(
    document: Path,
    current_head: str,
) -> ReceiptQualification:
    """Evaluate one document against the exact current head."""
    if not _FULL_SHA_RE.match(current_head):
        raise ValueError(
            f"current_head must be a full 40-char SHA, got {current_head!r}"
        )
    text = document.read_text(encoding="utf-8", errors="replace")

    qualified_head: str | None = None
    for pattern in _QUALIFIED_HEAD_RES:
        match = pattern.search(text)
        if match:
            qualified_head = match.group(1).lower()
            break

    unbound_claim = _has_unbound_current_claim(text)
    # Refusal verdicts are reserved for the receipt artifact class; standing
    # ledgers and narrative logs are noted, not gated.
    is_receipt = "receipt" in document.name.lower()

    if qualified_head is None:
        if unbound_claim and is_receipt:
            verdict = VERDICT_REFUSED_UNANCHORED
            detail = (
                "receipt claims current standing with no qualified-head "
                "anchor; omitting the anchor is not an escape hatch -- bind "
                "the claim to the head it was earned on"
            )
        elif unbound_claim:
            verdict = VERDICT_QUALIFIED
            detail = (
                "unanchored current-standing claim in a non-receipt "
                "document (ledger/log class); outside the receipt "
                "guard's enforcement jurisdiction"
            )
        else:
            verdict = VERDICT_QUALIFIED
            detail = "no qualified-head anchor and no current-standing claim"
    elif _anchor_matches_current(qualified_head, current_head):
        verdict = VERDICT_QUALIFIED
        detail = f"qualified head {qualified_head[:12]} is the current head"
    elif unbound_claim and is_receipt:
        verdict = VERDICT_REFUSED_STALE
        detail = (
            f"receipt claims current standing but its qualified head "
            f"{qualified_head[:12]} is not the current head "
            f"{current_head[:12]} -- the claim is expired; re-qualify at "
            "the current head or bind the standing claim to the qualified head"
        )
    else:
        verdict = VERDICT_EXPIRED_POINT_IN_TIME
        detail = f"qualified head {qualified_head[:12]} is historical " + (
            "(lawful point-in-time record)"
            if not unbound_claim
            else "with standing claims present (non-receipt document; "
            "noted, not enforced)"
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
    """Evaluate every Markdown document under ``docs_root``.

    Content-based: any document making a current-standing claim is in
    scope, whatever its filename. Any refusal verdict is a gate failure for
    the caller to surface; this function reports, it does not raise.
    """
    documents = sorted(docs_root.rglob("*.md"))
    return tuple(evaluate_receipt_document(doc, current_head) for doc in documents)


def main(argv: list[str] | None = None) -> int:
    """CLI: evaluate every document under --docs-root (default docs/)."""
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(
        description="Refuse stale or unanchored current-standing claims in docs."
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=repo_root / "docs",
        help="root to scan for Markdown documents (default: <repo>/docs)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=repo_root,
        help="repository root used to resolve the current HEAD",
    )
    args = parser.parse_args(argv)

    current = resolve_current_head(args.repo_root)
    verdicts = verify_repo_receipts(args.docs_root, current)
    refused = 0
    for v in verdicts:
        if v.verdict == VERDICT_QUALIFIED:
            continue
        if v.verdict.startswith("REFUSED"):
            refused += 1
            print(f"REFUSED: {v.document}: {v.verdict}: {v.detail}")
        else:
            print(f"note: {v.document}: {v.verdict}: {v.detail}")
    print(
        f"{len(verdicts)} documents scanned at HEAD {current[:12]}; {refused} refused"
    )
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
