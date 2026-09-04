#!/usr/bin/env python3
"""
WS5 Qualification-before-Admission: ProjectGym.

A candidate capability is never admitted to the capability graph on the
strength of its own description. It is first *qualified*: an exact isolated
subject is materialized (a scratch git worktree, or a copied fixture dir),
the bounded qualification command runs there under timeout + cwd pinning,
each declared postcondition is observed for real, the subject is cleaned up,
and a QualificationReceipt is issued. Only a QUALIFIED receipt passes
`admit()`; anything else raises AdmissionRefused.

Verdict rule (fixed, not heuristic):
  INCONCLUSIVE  the command could not be observed to completion
                (timeout, spawn failure, materialization failure)
  REJECTED      the command completed but >= 1 postcondition observed False
  QUALIFIED     the command completed and every postcondition observed True

Postcondition kinds (declarative, JSON-serializable, see candidates.json):
  {"kind": "exit_code",   "expected": 0}
  {"kind": "file_exists", "path": "rel/path", "expected": true}
  {"kind": "output_regex","stream": "stdout"|"stderr", "pattern": "..."}
  {"kind": "state_probe", "command": ["sh","-c","..."], "pattern": "..."}
      -- runs a second bounded command in the subject after the action and
         matches its stdout against `pattern` (a real probe, not a replay)

Stdlib only. Python 3.
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
GYM_ROOT = os.path.join(HERE, "_gym")
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EMITTER_PATH = os.path.join(REPO_ROOT, "tools", "ocel_v2", "emitter.py")

QUALIFIED = "QUALIFIED"
REJECTED = "REJECTED"
INCONCLUSIVE = "INCONCLUSIVE"
VERDICTS = (QUALIFIED, REJECTED, INCONCLUSIVE)


class AdmissionRefused(Exception):
    """Raised by admit() for any receipt that is not a verified QUALIFIED receipt."""


class GymError(Exception):
    """Materialization / infrastructure failure (maps to INCONCLUSIVE)."""


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    name: str
    subject_kind: str  # "fixture" | "worktree"
    subject_source: str  # fixture: dir path; worktree: git ref (e.g. HEAD)
    command: list[str]
    postconditions: list[dict[str, Any]]
    timeout_s: float = 30.0
    description: str = ""

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Candidate":
        return Candidate(
            name=d["name"],
            subject_kind=d["subject_kind"],
            subject_source=d["subject_source"],
            command=list(d["command"]),
            postconditions=list(d["postconditions"]),
            timeout_s=float(d.get("timeout_s", 30.0)),
            description=d.get("description", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class QualificationReceipt:
    candidate: dict[str, Any]
    subject_kind: str
    subject_digest_before: str
    subject_digest_after: str
    observed_effects: list[dict[str, Any]]
    verdict: str
    evidence: dict[str, Any]
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    receipt_id: str = field(default_factory=lambda: "qr_" + uuid.uuid4().hex[:12])

    def body(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d.pop("digest", None)
        return d

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        d = self.body()
        d["digest"] = self.digest
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "QualificationReceipt":
        d = dict(d)
        claimed = d.pop("digest", None)
        r = QualificationReceipt(**d)
        if claimed is not None and claimed != r.digest:
            raise AdmissionRefused(f"receipt digest mismatch: claimed {claimed} != {r.digest}")
        return r


# ---------------------------------------------------------------------------
# Subject digest: content-addressed snapshot of a directory tree (no .git)
# ---------------------------------------------------------------------------


def digest_tree(root: str) -> str:
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            h.update(rel.encode() + b"\0")
            with open(p, "rb") as f:
                h.update(hashlib.sha256(f.read()).digest())
    return h.hexdigest()


def list_tree(root: str) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for fn in sorted(filenames):
            out.append(os.path.relpath(os.path.join(dirpath, fn), root))
    return sorted(out)


# ---------------------------------------------------------------------------
# Subject materialization
# ---------------------------------------------------------------------------


class Subject:
    def __init__(self, kind: str, path: str, cleanup):
        self.kind = kind
        self.path = path
        self._cleanup = cleanup

    def cleanup(self) -> None:
        self._cleanup()


def _materialize(c: Candidate, run_dir: str) -> Subject:
    subj = os.path.join(run_dir, "subject")
    if c.subject_kind == "fixture":
        src = c.subject_source if os.path.isabs(c.subject_source) else os.path.join(HERE, c.subject_source)
        if not os.path.isdir(src):
            raise GymError(f"fixture dir not found: {src}")
        shutil.copytree(src, subj, symlinks=False)
        return Subject("fixture", subj, lambda: shutil.rmtree(run_dir, ignore_errors=True))
    if c.subject_kind == "worktree":
        r = subprocess.run(
            ["git", "worktree", "add", "--detach", subj, c.subject_source],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            raise GymError(f"git worktree add failed: {r.stderr.strip()}")

        def _rm():
            subprocess.run(["git", "worktree", "remove", "--force", subj],
                           cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
            shutil.rmtree(run_dir, ignore_errors=True)
            subprocess.run(["git", "worktree", "prune"], cwd=REPO_ROOT, capture_output=True, timeout=60)
        return Subject("worktree", subj, _rm)
    raise GymError(f"unknown subject_kind {c.subject_kind!r}")


# ---------------------------------------------------------------------------
# Postcondition observation (real, against the subject after execution)
# ---------------------------------------------------------------------------


def _observe(pc: dict[str, Any], subj: str, run: dict[str, Any]) -> dict[str, Any]:
    kind = pc["kind"]
    obs: dict[str, Any] = {"postcondition": pc, "kind": kind}
    if kind == "exit_code":
        obs["observed"] = run["returncode"]
        obs["holds"] = run["returncode"] == pc["expected"]
    elif kind == "file_exists":
        p = os.path.join(subj, pc["path"])
        exists = os.path.isfile(p)
        obs["observed"] = exists
        if exists:
            with open(p, "rb") as f:
                obs["content_sha256"] = hashlib.sha256(f.read()).hexdigest()
        obs["holds"] = exists == bool(pc.get("expected", True))
    elif kind == "output_regex":
        text = run[pc.get("stream", "stdout")]
        m = re.search(pc["pattern"], text, re.M)
        obs["observed"] = m.group(0) if m else None
        obs["holds"] = m is not None
    elif kind == "state_probe":
        try:
            pr = subprocess.run(pc["command"], cwd=subj, capture_output=True, text=True,
                                timeout=float(pc.get("timeout_s", 10)))
            obs["probe_stdout"] = pr.stdout
            obs["probe_returncode"] = pr.returncode
            m = re.search(pc["pattern"], pr.stdout, re.M)
            obs["observed"] = m.group(0) if m else None
            obs["holds"] = m is not None
        except subprocess.TimeoutExpired:
            obs["observed"] = "probe timeout"
            obs["holds"] = False
    else:
        obs["observed"] = f"unknown postcondition kind {kind!r}"
        obs["holds"] = False
    return obs


# ---------------------------------------------------------------------------
# ProjectGym
# ---------------------------------------------------------------------------


class ProjectGym:
    def __init__(self, gym_root: str = GYM_ROOT):
        self.gym_root = gym_root
        os.makedirs(gym_root, exist_ok=True)

    def qualify(self, c: Candidate) -> QualificationReceipt:
        run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:6]
        run_dir = os.path.join(self.gym_root, run_id)
        os.makedirs(run_dir)
        evidence: dict[str, Any] = {"run_id": run_id, "run_dir": run_dir, "cwd_pinned": None}
        subject = None
        try:
            subject = _materialize(c, run_dir)
        except (GymError, subprocess.TimeoutExpired, OSError) as e:
            evidence["materialize_error"] = repr(e)
            shutil.rmtree(run_dir, ignore_errors=True)
            return QualificationReceipt(c.to_dict(), c.subject_kind, "", "", [], INCONCLUSIVE, evidence)

        try:
            before = digest_tree(subject.path)
            files_before = list_tree(subject.path)
            evidence["cwd_pinned"] = subject.path
            t0 = time.monotonic()
            try:
                r = subprocess.run(c.command, cwd=subject.path, capture_output=True, text=True,
                                   timeout=c.timeout_s, env={**os.environ, "GYM_SUBJECT": subject.path})
                run = {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
                       "elapsed_s": round(time.monotonic() - t0, 4), "timed_out": False}
            except subprocess.TimeoutExpired as e:
                run = {"returncode": None, "stdout": (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""),
                       "stderr": (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or ""),
                       "elapsed_s": round(time.monotonic() - t0, 4), "timed_out": True}
            except OSError as e:
                run = {"returncode": None, "stdout": "", "stderr": repr(e),
                       "elapsed_s": round(time.monotonic() - t0, 4), "timed_out": False, "spawn_error": repr(e)}
            after = digest_tree(subject.path)
            files_after = list_tree(subject.path)
            evidence["command"] = c.command
            evidence["run"] = run
            evidence["files_added"] = sorted(set(files_after) - set(files_before))
            evidence["files_removed"] = sorted(set(files_before) - set(files_after))

            if run["timed_out"] or run["returncode"] is None:
                verdict = INCONCLUSIVE
                observed = []
            else:
                observed = [_observe(pc, subject.path, run) for pc in c.postconditions]
                verdict = QUALIFIED if all(o["holds"] for o in observed) else REJECTED
            evidence["postconditions_declared"] = len(c.postconditions)
            evidence["postconditions_held"] = sum(1 for o in observed if o["holds"])
            return QualificationReceipt(c.to_dict(), c.subject_kind, before, after, observed, verdict, evidence)
        finally:
            subject.cleanup()
            evidence["subject_restored"] = not os.path.exists(run_dir)


# ---------------------------------------------------------------------------
# Admission rule (the only gate into the capability graph)
# ---------------------------------------------------------------------------


def admit(receipt: QualificationReceipt | dict[str, Any]) -> QualificationReceipt:
    """Return the receipt iff it is a digest-intact QUALIFIED receipt; raise otherwise."""
    if isinstance(receipt, dict):
        receipt = QualificationReceipt.from_dict(receipt)  # raises on digest tamper
    if not isinstance(receipt, QualificationReceipt):
        raise AdmissionRefused(f"not a QualificationReceipt: {type(receipt).__name__}")
    if receipt.verdict not in VERDICTS:
        raise AdmissionRefused(f"unknown verdict {receipt.verdict!r}")
    if receipt.verdict != QUALIFIED:
        raise AdmissionRefused(
            f"admission refused: receipt {receipt.receipt_id} for "
            f"{receipt.candidate.get('name')!r} has verdict {receipt.verdict}, not {QUALIFIED}"
        )
    if not receipt.observed_effects or not all(o.get("holds") for o in receipt.observed_effects):
        raise AdmissionRefused("admission refused: QUALIFIED verdict without all-holding observed effects")
    return receipt


# ---------------------------------------------------------------------------
# OCEL emission via the real emitter module
# ---------------------------------------------------------------------------


def _load_emitter():
    spec = importlib.util.spec_from_file_location("ocel_emitter", EMITTER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def emit_ocel(log_path: str, receipt: QualificationReceipt, init: bool = False) -> None:
    em = _load_emitter()
    if init or not os.path.exists(log_path):
        em.init(log_path)
    rid = receipt.receipt_id
    name = receipt.candidate["name"]
    em.add_object(log_path, "Action", f"action_{rid}", {
        # args_json omitted on purpose: validate.py has no type entry for
        # "string:canonical-json", so canonical-json attrs on OBJECTS count as
        # strict_type_mismatches; the command is carried in the event metrics.
        "name": name, "kind": "qualification_candidate",
    })
    em.add_object(log_path, "QualificationRun", f"qrun_{rid}", {
        "name": name, "result": receipt.verdict,
    })
    em.add_object(log_path, "Receipt", f"receipt_{rid}", {
        "kind": "QualificationReceipt", "digest": receipt.digest, "issued_at": receipt.issued_at,
    })
    em.add_event(log_path, "QualificationObserved", f"ev_qobs_{rid}", {
        "result": receipt.verdict,
        "metrics_json": {
            "postconditions_declared": receipt.evidence.get("postconditions_declared"),
            "postconditions_held": receipt.evidence.get("postconditions_held"),
            "subject_digest_before": receipt.subject_digest_before,
            "subject_digest_after": receipt.subject_digest_after,
            "elapsed_s": (receipt.evidence.get("run") or {}).get("elapsed_s"),
            "command": receipt.candidate["command"],
        },
    }, [f"action_{rid}", f"qrun_{rid}"])
    em.add_event(log_path, "ReceiptIssued", f"ev_rissued_{rid}", {"digest": receipt.digest},
                 [f"qrun_{rid}", f"receipt_{rid}"])


def load_candidates(path: str) -> list[Candidate]:
    with open(path, encoding="utf-8") as f:
        return [Candidate.from_dict(d) for d in json.load(f)]


if __name__ == "__main__":
    # gym.py <candidates.json> <receipts_out_dir> <ocel_out.json>
    cands = load_candidates(sys.argv[1])
    out_dir, ocel_path = sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    g = ProjectGym()
    first = True
    for c in cands:
        rc = g.qualify(c)
        with open(os.path.join(out_dir, f"{c.name}.receipt.json"), "w") as f:
            json.dump(rc.to_dict(), f, indent=2, sort_keys=True)
        emit_ocel(ocel_path, rc, init=first)
        first = False
        print(json.dumps({"candidate": c.name, "verdict": rc.verdict, "receipt_id": rc.receipt_id,
                          "digest": rc.digest, "before": rc.subject_digest_before[:12],
                          "after": rc.subject_digest_after[:12],
                          "held": f"{rc.evidence.get('postconditions_held')}/{rc.evidence.get('postconditions_declared')}",
                          "restored": rc.evidence.get("subject_restored")}))
