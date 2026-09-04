#!/usr/bin/env python3
"""
WS9 Evidence Durability — EvidenceRef / ArtifactReceipt / resolve() / standing gate.

Capitalizes the incident where a prior session's `crown-run-v2.ocel.json` and an
"82-record hook JSONL run" existed only in transient paths ($TMPDIR, /tmp,
/var/folders) and could not be resolved later. A claim that cites evidence is
only allowed *standing* if every cited EvidenceRef RESOLVES right now, against
the real filesystem — not against memory of a prior run.

Check order (first failure wins; the refusal names the check):

  DurabilityCheck  path is absolute, lexists, is not a symlink whose realpath
                   leaves the durable roots, is not dangling, is a regular
                   file, and its realpath is under a durable root and NOT
                   under any transient root (/tmp, /private/tmp, /var/folders,
                   /private/var/folders, $TMPDIR, tempfile.gettempdir()).
  DigestCheck      sha256(file bytes) == ref.sha256.
  ReplayCheck      ref.parser (json | jsonl | ocel | text) parses the file.
  ReceiptCheck     if ref.receipt_path is set: receipt is itself durable +
                   readable JSON, receipt.subject_identity == ref.identity,
                   receipt.subject_sha256 == ref.sha256, and the receipt is
                   not superseded (superseded_by is null/absent).

resolve(ref) -> Resolution(status="RESOLVED") or
               Resolution(status="REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:<check>]")

standing(claim) -> Standing; .issued is True only if every ref RESOLVED.

Stdlib only. No mocks anywhere; tests create/delete real files.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_OCEL_V2_DIR = os.path.normpath(os.path.join(_HERE, "..", "..", "ocel_v2"))

REFUSAL_PREFIX = "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:"
RESOLVED = "RESOLVED"

CHECK_DURABILITY = "DurabilityCheck"
CHECK_DIGEST = "DigestCheck"
CHECK_REPLAY = "ReplayCheck"
CHECK_RECEIPT = "ReceiptCheck"
CHECK_ORDER = (CHECK_DURABILITY, CHECK_DIGEST, CHECK_REPLAY, CHECK_RECEIPT)


def refusal(check: str) -> str:
    return f"{REFUSAL_PREFIX}{check}]"


# ---------------------------------------------------------------------------
# Transient / durable roots
# ---------------------------------------------------------------------------

_STATIC_TRANSIENT = ("/tmp", "/private/tmp", "/var/folders", "/private/var/folders")


def _real(p: str) -> str:
    return os.path.realpath(os.path.abspath(os.path.expanduser(p)))


def transient_roots(env: Optional[dict[str, str]] = None) -> list[str]:
    """Realpaths of every root considered non-durable. $TMPDIR is included even
    when it lives under $HOME (on this machine TMPDIR=~/.cache/tmp)."""
    env = os.environ if env is None else env
    roots = [_real(r) for r in _STATIC_TRANSIENT]
    for candidate in (env.get("TMPDIR"), env.get("TMP"), env.get("TEMP"), tempfile.gettempdir()):
        if candidate:
            roots.append(_real(candidate))
    # de-dup, keep order
    out: list[str] = []
    for r in roots:
        if r not in out:
            out.append(r)
    return out


def default_durable_roots(env: Optional[dict[str, str]] = None) -> list[str]:
    env = os.environ if env is None else env
    configured = env.get("WS9_DURABLE_ROOTS")
    if configured:
        return [_real(r) for r in configured.split(os.pathsep) if r.strip()]
    home = env.get("HOME") or os.path.expanduser("~")
    return [_real(home)]


def _under(path: str, root: str) -> bool:
    path = path.rstrip(os.sep)
    root = root.rstrip(os.sep)
    return path == root or path.startswith(root + os.sep)


# ---------------------------------------------------------------------------
# Parsers (ReplayCheck)
# ---------------------------------------------------------------------------

def _parse_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"kind": type(data).__name__, "records": len(data) if isinstance(data, (list, dict)) else 1}


def _parse_jsonl(path: str) -> dict[str, Any]:
    n = 0
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"line {lineno}: JSONL record is not an object")
            n += 1
    if n == 0:
        raise ValueError("JSONL file has zero records")
    return {"records": n}


def _parse_ocel(path: str) -> dict[str, Any]:
    """Replay through the real OCEL v2 validator (tools/ocel_v2/validate.py)."""
    if _OCEL_V2_DIR not in sys.path:
        sys.path.insert(0, _OCEL_V2_DIR)
    import validate as ocel_validate  # type: ignore

    with open(path, "r", encoding="utf-8") as f:
        ocel = json.load(f)
    for key in ("objectTypes", "eventTypes", "objects", "events"):
        if key not in ocel:
            raise ValueError(f"OCEL log missing top-level key {key!r}")
    summary = ocel_validate.validate(ocel)
    if any(v != 0 for v in summary.values()):
        raise ValueError(f"OCEL strict validation failed: {summary}")
    return {"objects": len(ocel["objects"]), "events": len(ocel["events"]), **summary}


def _parse_text(path: str) -> dict[str, Any]:
    with open(path, "rb") as f:
        data = f.read()
    data.decode("utf-8")
    return {"bytes": len(data)}


PARSERS: dict[str, Callable[[str], dict[str, Any]]] = {
    "json": _parse_json,
    "jsonl": _parse_jsonl,
    "ocel": _parse_ocel,
    "text": _parse_text,
}


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceRef:
    identity: str            # stable logical name, e.g. "crown-run-v2.ocel"
    durable_path: str        # absolute path; must survive the session
    sha256: str              # hex digest of the bytes the claim was made against
    parser: str              # key into PARSERS
    receipt_path: Optional[str] = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "EvidenceRef":
        return EvidenceRef(
            identity=str(d["identity"]),
            durable_path=str(d["durable_path"]),
            sha256=str(d["sha256"]).lower(),
            parser=str(d["parser"]),
            receipt_path=d.get("receipt_path"),
        )


@dataclass(frozen=True)
class ArtifactReceipt:
    receipt_id: str
    subject_identity: str
    subject_sha256: str
    issued_at: str
    issuer: str = ""
    superseded_by: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "ArtifactReceipt":
        return ArtifactReceipt(
            receipt_id=str(d["receipt_id"]),
            subject_identity=str(d["subject_identity"]),
            subject_sha256=str(d["subject_sha256"]).lower(),
            issued_at=str(d["issued_at"]),
            issuer=str(d.get("issuer", "")),
            superseded_by=d.get("superseded_by"),
        )

    def write(self, path: str) -> str:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
        return path


@dataclass
class CheckResult:
    check: str
    ok: bool
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Resolution:
    identity: str
    status: str
    checks: list[CheckResult]

    @property
    def resolved(self) -> bool:
        return self.status == RESOLVED

    def to_dict(self) -> dict[str, Any]:
        return {"identity": self.identity, "status": self.status,
                "checks": [asdict(c) for c in self.checks]}


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def durability_check(path: str, durable_roots: Optional[list[str]] = None,
                     transient: Optional[list[str]] = None) -> CheckResult:
    durable_roots = default_durable_roots() if durable_roots is None else durable_roots
    transient = transient_roots() if transient is None else transient
    detail: dict[str, Any] = {"path": path}

    if not os.path.isabs(path):
        return CheckResult(CHECK_DURABILITY, False, "path is not absolute", detail)
    if not os.path.lexists(path):
        return CheckResult(CHECK_DURABILITY, False, "artifact does not exist (deleted or never durable)", detail)

    # Walk every component: any symlink along the way must resolve, and the
    # final realpath must not land in a transient root.
    if os.path.islink(path) and not os.path.exists(path):
        detail["link_target"] = os.readlink(path)
        return CheckResult(CHECK_DURABILITY, False, "stale (dangling) symlink", detail)

    real = _real(path)
    detail["realpath"] = real
    for t in transient:
        if _under(real, t):
            why = "symlink into transient root" if os.path.islink(path) or real != os.path.abspath(path) else "path under transient root"
            detail["transient_root"] = t
            return CheckResult(CHECK_DURABILITY, False, f"{why} {t}", detail)
    if not any(_under(real, r) for r in durable_roots):
        detail["durable_roots"] = durable_roots
        return CheckResult(CHECK_DURABILITY, False, "realpath not under any durable root", detail)
    if not os.path.isfile(real):
        return CheckResult(CHECK_DURABILITY, False, "not a regular file", detail)
    return CheckResult(CHECK_DURABILITY, True, "", detail)


def digest_check(path: str, expected_sha256: str) -> CheckResult:
    try:
        actual = sha256_of(path)
    except OSError as e:
        return CheckResult(CHECK_DIGEST, False, f"unreadable: {e}", {"path": path})
    ok = actual == expected_sha256.lower()
    return CheckResult(CHECK_DIGEST, ok, "" if ok else "sha256 mismatch",
                       {"expected": expected_sha256.lower(), "actual": actual})


def replay_check(path: str, parser: str) -> CheckResult:
    fn = PARSERS.get(parser)
    if fn is None:
        return CheckResult(CHECK_REPLAY, False, f"unknown parser {parser!r}", {"known": sorted(PARSERS)})
    try:
        summary = fn(path)
    except Exception as e:  # parser failure is the signal, whatever its class
        return CheckResult(CHECK_REPLAY, False, f"{type(e).__name__}: {e}", {"parser": parser})
    return CheckResult(CHECK_REPLAY, True, "", {"parser": parser, **summary})


def receipt_check(ref: EvidenceRef, durable_roots: Optional[list[str]] = None,
                  transient: Optional[list[str]] = None) -> CheckResult:
    if ref.receipt_path is None:
        return CheckResult(CHECK_RECEIPT, True, "no receipt referenced", {})
    d = durability_check(ref.receipt_path, durable_roots, transient)
    if not d.ok:
        return CheckResult(CHECK_RECEIPT, False, f"receipt not durable: {d.reason}", d.detail)
    try:
        with open(ref.receipt_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        receipt = ArtifactReceipt.from_dict(raw)
    except (OSError, ValueError, KeyError, TypeError) as e:
        return CheckResult(CHECK_RECEIPT, False, f"unreadable receipt: {type(e).__name__}: {e}",
                           {"receipt_path": ref.receipt_path})
    detail = {"receipt_id": receipt.receipt_id, "receipt_path": ref.receipt_path}
    if receipt.subject_identity != ref.identity:
        detail.update(expected_identity=ref.identity, receipt_identity=receipt.subject_identity)
        return CheckResult(CHECK_RECEIPT, False, "wrong subject: identity mismatch", detail)
    if receipt.subject_sha256 != ref.sha256.lower():
        detail.update(expected_sha256=ref.sha256.lower(), receipt_sha256=receipt.subject_sha256)
        return CheckResult(CHECK_RECEIPT, False, "wrong subject: receipt subject sha != artifact sha", detail)
    if receipt.superseded_by:
        detail["superseded_by"] = receipt.superseded_by
        return CheckResult(CHECK_RECEIPT, False, "receipt superseded", detail)
    return CheckResult(CHECK_RECEIPT, True, "", detail)


# ---------------------------------------------------------------------------
# resolve / standing
# ---------------------------------------------------------------------------

def resolve(ref: EvidenceRef, durable_roots: Optional[list[str]] = None,
            transient: Optional[list[str]] = None) -> Resolution:
    checks: list[CheckResult] = []
    d = durability_check(ref.durable_path, durable_roots, transient)
    checks.append(d)
    if not d.ok:
        return Resolution(ref.identity, refusal(CHECK_DURABILITY), checks)
    g = digest_check(ref.durable_path, ref.sha256)
    checks.append(g)
    if not g.ok:
        return Resolution(ref.identity, refusal(CHECK_DIGEST), checks)
    r = replay_check(ref.durable_path, ref.parser)
    checks.append(r)
    if not r.ok:
        return Resolution(ref.identity, refusal(CHECK_REPLAY), checks)
    c = receipt_check(ref, durable_roots, transient)
    checks.append(c)
    if not c.ok:
        return Resolution(ref.identity, refusal(CHECK_RECEIPT), checks)
    return Resolution(ref.identity, RESOLVED, checks)


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    refs: tuple[EvidenceRef, ...]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Claim":
        return Claim(str(d["claim_id"]), str(d.get("text", "")),
                     tuple(EvidenceRef.from_dict(r) for r in d.get("refs", [])))


@dataclass
class Standing:
    claim_id: str
    issued: bool
    status: str                      # "STANDING" or the first refusal
    resolutions: list[Resolution]

    def to_dict(self) -> dict[str, Any]:
        return {"claim_id": self.claim_id, "issued": self.issued, "status": self.status,
                "resolutions": [r.to_dict() for r in self.resolutions]}


def standing(claim: Claim, durable_roots: Optional[list[str]] = None,
             transient: Optional[list[str]] = None) -> Standing:
    """Invariant: standing is issued only if EVERY referenced EvidenceRef resolves.
    A claim with zero refs is refused too — an unreferenced claim cites nothing."""
    if not claim.refs:
        return Standing(claim.claim_id, False, refusal("NoEvidenceReferenced"), [])
    resolutions = [resolve(r, durable_roots, transient) for r in claim.refs]
    failed = [r for r in resolutions if not r.resolved]
    if failed:
        return Standing(claim.claim_id, False, failed[0].status, resolutions)
    return Standing(claim.claim_id, True, "STANDING", resolutions)


def make_ref(identity: str, path: str, parser: str, receipt_path: Optional[str] = None) -> EvidenceRef:
    """Build a ref from a real file (digest computed now, path made absolute)."""
    return EvidenceRef(identity, os.path.abspath(path), sha256_of(path), parser, receipt_path)
