"""Hash-chain sealing for the ledger (stdlib only).

Detects edits, reorderings and deletions in the middle of a ledger, and tail
truncation when the head digest is kept apart from the rows. It does NOT stop a
party who can rewrite both rows and head from forging a consistent ledger;
forgery resistance comes from replaying the world in verify.py.
"""

from __future__ import annotations

import hashlib
import json

GENESIS = "0" * 64


def _canon(row: dict) -> bytes:
    body = {k: v for k, v in row.items() if k != "digest"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()


def seal(rows: list[dict], prev: str = GENESIS) -> list[dict]:
    """Return rows with ``prev``/``digest`` recomputed, in order."""
    out = []
    for row in rows:
        row = {k: v for k, v in row.items() if k != "digest"}
        row["prev"] = prev
        row["digest"] = hashlib.sha256(_canon(row)).hexdigest()
        prev = row["digest"]
        out.append(row)
    return out


def chain_findings(rows: list[dict]) -> list[str]:
    findings = []
    prev = GENESIS
    for i, row in enumerate(rows):
        if row.get("prev") != prev:
            findings.append(f"CHAIN_BROKEN:{i}")
        elif hashlib.sha256(_canon(row)).hexdigest() != row.get("digest"):
            findings.append(f"CHAIN_DIGEST:{i}")
        prev = row.get("digest", "")
    return findings
