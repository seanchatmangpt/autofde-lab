#!/usr/bin/env python3
"""Independent fresh-consumer verifier for RFC-SA2A-002 Gate11/CHI-FRESH.

Per ``.claude/rules/no-dual-bookkeeping.md``'s "standing external to the
actor": this script is a SECOND, INDEPENDENT consumer of the receipt artifact
produced by ``scripts/run_chicago_qualification.py``. It deliberately does
NOT import ``autofde_lab.sa2a.conformance.runner`` or any court module --
doing so would make this verifier attest to itself (the exact anti-pattern
``no-dual-bookkeeping.md`` names: "the system is attesting to itself, and its
verdict is worth exactly what a self-report is worth").

Instead it treats the previously-emitted receipt JSON file as the sole
durable evidence artifact and, using ONLY the Python standard library
(``json``, ``hashlib``, ``subprocess``, ``sys``, ``pathlib``), independently:

  1. Checks all 12 ``canonical_gates`` keys are present and ``true``.
  2. Checks ``gates_passed`` has exactly 12 entries, all ``true``.
  3. Recomputes ``git rev-parse HEAD`` via a real subprocess call and
     compares it against the receipt's stored ``exact_sha`` -- this is what
     makes the check a FRESH-consumer check rather than a replay of a
     previously-trusted value: it re-derives the current repo identity from
     the one place it can actually come from (git itself), not from any
     value the producer script also wrote down.
  4. Recomputes ``receipt_digest`` using the *exact same* canonicalization
     the producer uses, reproduced here (not imported) from direct source
     reads this session:

       - ``src/autofde_lab/sa2a/conformance/runner.py`` (around lines
         851-889): builds a ``pre_body`` dict, then computes
         ``compute_receipt_digest({"kind": "standing_receipt", "body": pre_body})``.
         ``pre_body`` contains exactly the same fields as
         ``StandingReceipt.to_dict()`` (same file, ``to_dict`` around lines
         243-266) MINUS the three keys that ``to_dict()`` adds beyond
         ``pre_body``: ``gates_passed``, ``canonical_gates``,
         ``receipt_digest`` itself. Every other field
         (``receipt_id``, ``standard``, ``appendix``, ``court``, ``release``,
         ``qualification_kind``, ``subject``, ``exact_sha``, ``tag_sha``,
         ``tag_equality``, ``standing``, ``all_gates_passed``,
         ``issued_at_ms``, ``duration_ms``, ``gates``, ``ocel_conformance``,
         ``cryptographic_binding``) is written into ``pre_body`` verbatim and
         unmodified -- confirmed by a direct side-by-side read of both
         dict-literal blocks in source, not inferred.
       - ``src/autofde_lab/sa2a/brce/receipts.py::compute_receipt_digest()``:
         ``sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
         ensure_ascii=False).encode("utf-8")).hexdigest()``.

     Because ``pre_body`` is reconstructible from the stored receipt dict by
     dropping exactly those three keys, and every nested value inside it
     (``gates``, ``ocel_conformance``, ``cryptographic_binding``) already
     round-trips through the JSON file with no lossy types (no sets, no
     enums, no tuples that serialize differently -- confirmed by reading
     ``GateExecutionRecord.to_dict()``, ``OcelConformanceSummary.to_dict()``,
     and ``CryptographicBinding.to_dict()`` directly), this reconstruction is
     exact, not approximate.

     If a future producer change moves this formula, this check will FAIL
     with a printed mismatch (never silently pass) -- see the "if the exact
     formula cannot be determined with certainty" contingency in the module
     docstring's task description: as of this session the formula WAS
     determined with certainty from source, so no such gap is reported here.

Usage::

    python scripts/verify_rfc_sa2a_002_qualification.py [receipt_path]

Default ``receipt_path``:
    reports/rfc_sa2a_002_chicago_crown_receipt.json

Exit code 0 iff all four checks pass. Non-zero otherwise. If the receipt
file does not exist yet, this prints a named ``BLOCKED:RECEIPT_NOT_YET_PRODUCED``
status and the exact command to run first -- it never waits, polls, or
fabricates a receipt.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECEIPT_PATH = REPO_ROOT / "reports" / "rfc_sa2a_002_chicago_crown_receipt.json"
PRODUCER_COMMAND = ".venv/bin/python scripts/run_chicago_qualification.py"

# The 12 canonical Chicago Crown gate names per RFC-SA2A-002 Appendix D, as
# literally reproduced (not imported) from
# ChicagoCrownQualificationRunner.GATE_SPECS in
# src/autofde_lab/sa2a/conformance/runner.py, read directly this session.
CANONICAL_GATE_NAMES: tuple[str, ...] = (
    "Gate01_ExactIdentityFenced",
    "Gate02_ExecutableWorldAdmitted",
    "Gate03_RealCollaboratorsZeroMocks",
    "Gate04_PlanningCandidateOnly",
    "Gate05_WholeBoundedPlanPreflighted",
    "Gate06_AutonomousExecutionInsideEnvelope",
    "Gate07_SoleDOBoundaryBRCE",
    "Gate08_IndependentPostconditionObservation",
    "Gate09_CompleteReceiptIdentityBinding",
    "Gate10_ReplaySucceedsDeterministically",
    "Gate11_FreshConsumerProofSucceeds",
    "Gate12_ZeroRuntimeInferenceKnown",
)

# Keys StandingReceipt.to_dict() adds on top of the pre_body dict that was
# actually hashed to produce receipt_digest (runner.py to_dict() vs. the
# pre_body literal a few lines above it in run()). Dropping exactly these
# three from the stored receipt reconstructs pre_body exactly.
_DIGEST_EXCLUDED_KEYS = frozenset({"gates_passed", "canonical_gates", "receipt_digest"})


def check_canonical_gates(receipt: dict) -> tuple[bool, str]:
    """Check 1: all 12 canonical_gates keys present and true."""
    canonical_gates = receipt.get("canonical_gates")
    if not isinstance(canonical_gates, dict):
        return False, "receipt has no 'canonical_gates' dict"

    missing = [name for name in CANONICAL_GATE_NAMES if name not in canonical_gates]
    if missing:
        return False, f"missing canonical_gates keys: {missing}"

    not_true = [
        name for name in CANONICAL_GATE_NAMES if canonical_gates.get(name) is not True
    ]
    if not_true:
        return False, f"canonical_gates not True for: {not_true}"

    extra = sorted(k for k in canonical_gates if k not in CANONICAL_GATE_NAMES)
    detail = "all 12 canonical_gates keys present and true"
    if extra:
        detail += f" (NOTE: unexpected extra keys also present: {extra})"
    return True, detail


def check_gates_passed(receipt: dict) -> tuple[bool, str]:
    """Check 2: gates_passed has exactly 12 entries, all true."""
    gates_passed = receipt.get("gates_passed")
    if not isinstance(gates_passed, dict):
        return False, "receipt has no 'gates_passed' dict"

    if len(gates_passed) != 12:
        return False, (
            f"gates_passed has {len(gates_passed)} entries, expected exactly 12: "
            f"{sorted(gates_passed.keys())}"
        )

    not_true = [k for k, v in gates_passed.items() if v is not True]
    if not_true:
        return False, f"gates_passed not True for: {not_true}"

    return (
        True,
        f"gates_passed has exactly 12 entries, all true (keys={sorted(gates_passed.keys())})",
    )


def check_exact_sha(receipt: dict, repo_root: Path) -> tuple[bool, str]:
    """Check 3: receipt's exact_sha matches the real, current 'git rev-parse HEAD'."""
    receipt_sha = receipt.get("exact_sha")
    if not isinstance(receipt_sha, str) or not receipt_sha:
        return False, "receipt has no non-empty 'exact_sha' string"

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        return False, f"git executable not found: {exc}"
    except subprocess.SubprocessError as exc:
        return False, f"'git rev-parse HEAD' subprocess failed: {exc}"

    if result.returncode != 0:
        return (
            False,
            f"'git rev-parse HEAD' exited {result.returncode}: stderr={result.stderr.strip()!r}",
        )

    current_head = result.stdout.strip()
    if receipt_sha == current_head:
        return (
            True,
            f"exact_sha {receipt_sha} == current 'git rev-parse HEAD' {current_head}",
        )

    # No prefix/short-SHA leniency: the receipt's top-level exact_sha field
    # is documented in runner.py as the full 40-char SHA. A lenient partial
    # match would silently paper over a stale receipt -- exactly the
    # confident-wrong-result absence-is-not-evidence.md warns against.
    return (
        False,
        f"exact_sha MISMATCH: receipt={receipt_sha!r} current HEAD={current_head!r}",
    )


def _compute_receipt_digest(data: object) -> str:
    """Stdlib-only reproduction of compute_receipt_digest() in
    src/autofde_lab/sa2a/brce/receipts.py (read directly, not imported)."""
    if isinstance(data, bytes):
        payload = data
    elif isinstance(data, str):
        payload = data.encode("utf-8")
    else:
        payload = json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def check_receipt_digest(receipt: dict) -> tuple[bool, str]:
    """Check 4: recompute receipt_digest using the producer's exact canonicalization.

    See the module docstring for the full derivation. Summary: reconstruct
    pre_body = receipt minus {gates_passed, canonical_gates, receipt_digest},
    then digest = sha256(json.dumps({"kind": "standing_receipt", "body": pre_body},
    sort_keys=True, separators=(",", ":"), ensure_ascii=False)).
    """
    stored_digest = receipt.get("receipt_digest")
    if not isinstance(stored_digest, str) or not stored_digest:
        return False, "receipt has no non-empty 'receipt_digest' string"

    pre_body = {k: v for k, v in receipt.items() if k not in _DIGEST_EXCLUDED_KEYS}
    recomputed = _compute_receipt_digest({"kind": "standing_receipt", "body": pre_body})

    if recomputed == stored_digest:
        return True, f"receipt_digest matches: stored=recomputed={stored_digest}"

    return False, (
        f"receipt_digest MISMATCH: stored={stored_digest!r} recomputed={recomputed!r} "
        f"(reconstructed pre_body keys={sorted(pre_body.keys())})"
    )


def main(argv: list[str]) -> int:
    repo_root = REPO_ROOT
    receipt_path = Path(argv[1]).resolve() if len(argv) > 1 else DEFAULT_RECEIPT_PATH

    print("=" * 78)
    print("RFC-SA2A-002 Gate11/CHI-FRESH -- INDEPENDENT fresh-consumer verifier")
    print("(zero import of autofde_lab.sa2a.conformance.runner or any court module;")
    print(" stdlib only: json, hashlib, subprocess, sys, pathlib)")
    print("=" * 78)
    print(f"repo_root:    {repo_root}")
    print(f"receipt_path: {receipt_path}")
    print()

    if not receipt_path.exists():
        print("STANDING: BLOCKED:RECEIPT_NOT_YET_PRODUCED")
        print()
        print(f"No receipt file at {receipt_path}.")
        print("Run the producer first, then re-run this verifier:")
        print()
        print(f"    {PRODUCER_COMMAND}")
        print(f"    python {Path(__file__).name} {receipt_path}")
        print()
        return 2

    try:
        raw_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"STANDING: BLOCKED:RECEIPT_UNREADABLE ({exc})")
        return 2

    try:
        receipt = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        print(f"STANDING: BLOCKED:RECEIPT_NOT_VALID_JSON ({exc})")
        return 2

    if not isinstance(receipt, dict):
        print(
            f"STANDING: BLOCKED:RECEIPT_NOT_A_JSON_OBJECT (top-level type={type(receipt).__name__})"
        )
        return 2

    checks = [
        ("1. canonical_gates: all 12 present and true", check_canonical_gates(receipt)),
        ("2. gates_passed: exactly 12 entries, all true", check_gates_passed(receipt)),
        (
            "3. exact_sha matches real 'git rev-parse HEAD'",
            check_exact_sha(receipt, repo_root),
        ),
        (
            "4. receipt_digest recomputes to the stored value",
            check_receipt_digest(receipt),
        ),
    ]

    print("-" * 78)
    all_passed = True
    for label, (passed, detail) in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"[{status}] {label}")
        print(f"       {detail}")
    print("-" * 78)

    if all_passed:
        print("STANDING: ALIVE")
        print("(all 4 independent checks passed against the stored receipt, recomputed")
        print(
            " this session from stdlib only, with zero import of the producer module)"
        )
        return 0

    print("STANDING: BUILD_BROKEN")
    print("(one or more independent checks failed -- see FAIL lines above)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
