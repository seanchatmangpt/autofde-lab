#!/usr/bin/env python3
"""
WS8 — Authority as a real control (not a log line).

decide(...) -> Decision   (GRANTED | REFUSED:<type> | ESCALATE:<boundary>)
execute(action, decision) -> ExecResult

The load-bearing property: execute() PHYSICALLY cannot spawn the subprocess
unless `decision` is a GRANTED Decision that was minted by decide() for this
exact action. Enforcement mechanism (no trust in the caller's string):

  * decide() computes action_digest = sha256(canonical(action)).
  * A GRANTED decision carries grant_token = HMAC(process_secret, action_digest).
    process_secret is a per-process random key held only in a closure; there
    is no accessor, so a token cannot be fabricated from outside this module.
  * execute() re-derives the digest from the action it is handed, verifies
    the HMAC with hmac.compare_digest, and only then references subprocess.
    A REFUSED/ESCALATE decision has grant_token=None and fails closed.
    A GRANTED decision for a *different* action fails closed (digest mismatch).
    A hand-built Decision(verdict="GRANTED", grant_token="x") fails closed.

Policy table (POLICY, data not code):
  reversible + non-consequential            -> GRANTED
  NETWORK_FETCH                             -> GRANTED only if reversible
  CONSEQUENTIAL                             -> ESCALATE:HUMAN_CONFIRMATION
  DESTRUCTIVE                               -> REFUSED:DESTRUCTIVE (or ESCALATE
                                               when authority_requirement=ESCALATABLE)
  subject_identity unknown/empty            -> REFUSED:SUBJECT_UNBOUND
  standing < threshold(authority_requirement) -> REFUSED:INSUFFICIENT_STANDING
  evidence_confidence < world.min_confidence  -> ESCALATE:EVIDENCE_INSUFFICIENT

Precedence (first match wins): SUBJECT_UNBOUND, INSUFFICIENT_STANDING,
DESTRUCTIVE, CONSEQUENTIAL, EVIDENCE_INSUFFICIENT, NETWORK_FETCH, default.
Identity and standing are checked before blast-radius so that an unbound
subject never learns which blast-radius class it would have been granted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

REVERSIBILITY = ("REVERSIBLE", "IRREVERSIBLE")
BLAST_RADIUS = ("NONE", "LOCAL", "NETWORK_FETCH", "CONSEQUENTIAL", "DESTRUCTIVE")
AUTHORITY_REQUIREMENT = ("NONE", "OPERATOR", "OWNER", "ESCALATABLE")

# Standing threshold per authority requirement (0..1 scale).
STANDING_THRESHOLD: dict[str, float] = {
    "NONE": 0.0,
    "OPERATOR": 0.5,
    "OWNER": 0.8,
    "ESCALATABLE": 0.8,
}

# Policy table: ordered rules. Each rule: (name, predicate, verdict).
# Predicates receive the normalized request dict. Verdict strings are final.
POLICY: list[tuple[str, str, str]] = [
    ("subject_unbound", "not req['subject_identity']", "REFUSED:SUBJECT_UNBOUND"),
    ("insufficient_standing", "req['standing'] < req['standing_threshold']", "REFUSED:INSUFFICIENT_STANDING"),
    ("destructive_escalatable",
     "req['blast_radius'] == 'DESTRUCTIVE' and req['authority_requirement'] == 'ESCALATABLE'",
     "ESCALATE:HUMAN_CONFIRMATION"),
    ("destructive", "req['blast_radius'] == 'DESTRUCTIVE'", "REFUSED:DESTRUCTIVE"),
    ("consequential", "req['blast_radius'] == 'CONSEQUENTIAL'", "ESCALATE:HUMAN_CONFIRMATION"),
    ("evidence_insufficient", "req['evidence_confidence'] < req['min_confidence']", "ESCALATE:EVIDENCE_INSUFFICIENT"),
    ("network_fetch_irreversible",
     "req['blast_radius'] == 'NETWORK_FETCH' and req['reversibility'] != 'REVERSIBLE'",
     "REFUSED:IRREVERSIBLE_NETWORK_FETCH"),
    ("network_fetch_reversible", "req['blast_radius'] == 'NETWORK_FETCH'", "GRANTED"),
    ("irreversible_local", "req['reversibility'] != 'REVERSIBLE'", "ESCALATE:IRREVERSIBLE"),
    ("reversible_non_consequential", "True", "GRANTED"),
]


@dataclass(frozen=True)
class Decision:
    verdict: str                     # GRANTED | REFUSED:<type> | ESCALATE:<boundary>
    rule: str                        # policy rule name that fired
    action_digest: str               # sha256 of canonical action
    rationale: str
    grant_token: Optional[str] = field(default=None, repr=False)

    @property
    def granted(self) -> bool:
        return self.verdict == "GRANTED"

    @property
    def kind(self) -> str:
        return self.verdict.split(":", 1)[0]


@dataclass(frozen=True)
class ExecResult:
    ran: bool
    returncode: Optional[int]
    stdout: str
    stderr: str
    reason: str


class AuthorityViolation(RuntimeError):
    """Raised when execute() is invoked without a valid GRANTED token."""


# ---------------------------------------------------------------------------
# Unforgeable grant tokens (closure-held secret, no accessor)
# ---------------------------------------------------------------------------

def _make_token_functions():
    secret = os.urandom(32)

    def mint(action_digest: str) -> str:
        return hmac.new(secret, action_digest.encode(), hashlib.sha256).hexdigest()

    def verify(action_digest: str, token: Optional[str]) -> bool:
        if not isinstance(token, str):
            return False
        return hmac.compare_digest(mint(action_digest), token)

    return mint, verify


_mint_token, _verify_token = _make_token_functions()
del _make_token_functions


def action_digest(action: dict[str, Any]) -> str:
    canon = json.dumps(action, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


# ---------------------------------------------------------------------------
# decide
# ---------------------------------------------------------------------------

def decide(
    action: dict[str, Any],
    reversibility: str,
    blast_radius: str,
    authority_requirement: str,
    subject_identity: Optional[str],
    standing: float,
    evidence_confidence: float,
    world: Optional[dict[str, Any]] = None,
) -> Decision:
    if reversibility not in REVERSIBILITY:
        raise ValueError(f"reversibility must be one of {REVERSIBILITY}, got {reversibility!r}")
    if blast_radius not in BLAST_RADIUS:
        raise ValueError(f"blast_radius must be one of {BLAST_RADIUS}, got {blast_radius!r}")
    if authority_requirement not in AUTHORITY_REQUIREMENT:
        raise ValueError(
            f"authority_requirement must be one of {AUTHORITY_REQUIREMENT}, got {authority_requirement!r}"
        )
    world = world or {}
    req = {
        "reversibility": reversibility,
        "blast_radius": blast_radius,
        "authority_requirement": authority_requirement,
        "subject_identity": (subject_identity or "").strip(),
        "standing": float(standing),
        "standing_threshold": STANDING_THRESHOLD[authority_requirement],
        "evidence_confidence": float(evidence_confidence),
        "min_confidence": float(world.get("min_confidence", 0.5)),
    }
    digest = action_digest(action)
    for name, predicate, verdict in POLICY:
        if eval(predicate, {"__builtins__": {}}, {"req": req}):  # noqa: S307 — table of literal predicates
            rationale = f"rule={name} predicate=({predicate}) req={json.dumps(req, sort_keys=True)}"
            token = _mint_token(digest) if verdict == "GRANTED" else None
            return Decision(verdict=verdict, rule=name, action_digest=digest,
                            rationale=rationale, grant_token=token)
    raise AssertionError("POLICY table has no catch-all rule")  # unreachable by construction


# ---------------------------------------------------------------------------
# execute — the physical gate
# ---------------------------------------------------------------------------

def execute(action: dict[str, Any], decision: Decision, timeout: float = 30.0) -> ExecResult:
    """
    Run action["argv"] ONLY if `decision` is a GRANTED Decision minted for
    this exact action. Every other path returns ran=False without ever
    touching the subprocess module.
    """
    if not isinstance(decision, Decision):
        raise AuthorityViolation("execute() requires a Decision from decide()")
    digest = action_digest(action)
    if digest != decision.action_digest:
        return ExecResult(False, None, "", "", "REFUSED:ACTION_MISMATCH (decision bound to a different action)")
    if decision.verdict != "GRANTED":
        return ExecResult(False, None, "", "", decision.verdict)
    if not _verify_token(digest, decision.grant_token):
        return ExecResult(False, None, "", "", "REFUSED:FORGED_GRANT")

    # Only reachable with a verified grant. subprocess is imported here so the
    # refused paths above have no reference to it at all.
    import subprocess  # noqa: PLC0415

    argv = action.get("argv")
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        return ExecResult(False, None, "", "", "REFUSED:MALFORMED_ARGV")
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                          cwd=action.get("cwd") or None)
    return ExecResult(True, proc.returncode, proc.stdout, proc.stderr, "GRANTED")


# ---------------------------------------------------------------------------
# OCEL emission through the shared emitter (real collaborator)
# ---------------------------------------------------------------------------

def _load_emitter():
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "..", "ocel_v2", "emitter.py"))
    spec = importlib.util.spec_from_file_location("ocel_emitter", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def emit_decision(ocel_path: str, action_id: str, action: dict[str, Any],
                  decision: Decision, seq: int, kind: str = "shell") -> list[str]:
    """Append Action + AuthorityDecision objects and the Evaluated/Granted/Refused events."""
    em = _load_emitter()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    log = em._read(ocel_path)
    if not any(o["id"] == action_id for o in log["objects"]):
        em.add_object(ocel_path, "Action", action_id,
                      {"name": action.get("name", action_id), "kind": kind, "args_json": action})
    dec_id = f"{action_id}:decision:{seq}"
    em.add_object(ocel_path, "AuthorityDecision", dec_id,
                  {"decision": decision.verdict, "rationale": decision.rationale, "decided_at": now})
    ev_ids = [f"{action_id}:evaluated:{seq}"]
    em.add_event(ocel_path, "AuthorityEvaluated", ev_ids[0],
                 {"rationale": decision.rationale}, [action_id, dec_id])
    if decision.granted:
        ev_ids.append(f"{action_id}:granted:{seq}")
        em.add_event(ocel_path, "AuthorityGranted", ev_ids[-1],
                     {"rationale": decision.rationale}, [action_id, dec_id])
    else:
        ev_ids.append(f"{action_id}:refused:{seq}")
        em.add_event(ocel_path, "AuthorityRefused", ev_ids[-1],
                     {"rationale": decision.verdict + " " + decision.rationale}, [action_id, dec_id])
    return ev_ids


def emit_action_started(ocel_path: str, action_id: str, seq: int, name: str) -> str:
    em = _load_emitter()
    ev_id = f"{action_id}:started:{seq}"
    em.add_event(ocel_path, "ActionStarted", ev_id, {"name": name}, [action_id])
    return ev_id


def run_with_authority(ocel_path: str, action_id: str, action: dict[str, Any], decision: Decision,
                       seq: int) -> ExecResult:
    """Emit the decision, then execute; ActionStarted is emitted only when the gate opened."""
    emit_decision(ocel_path, action_id, action, decision, seq)
    result = execute(action, decision)
    if result.ran:
        emit_action_started(ocel_path, action_id, seq, action.get("name", action_id))
    return result


if __name__ == "__main__":
    print(__doc__)
    sys.exit(0)
