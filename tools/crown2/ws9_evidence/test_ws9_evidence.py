#!/usr/bin/env python3
"""
Chicago-style tests for WS9 evidence durability. Every test creates REAL files
(under a durable root inside this worktree, and under real transient roots
/tmp and $TMPDIR) and deletes them in tearDown. No mocks, no patching.

Run:  python3 -m unittest -v tools/crown2/ws9_evidence/test_ws9_evidence.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from evidence import (  # noqa: E402
    ArtifactReceipt, Claim, EvidenceRef, RESOLVED, make_ref, refusal, resolve, standing,
    transient_roots, sha256_of,
)

REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
DURABLE_ROOT = os.path.join(HERE, ".testroot")          # inside the worktree => durable
OCEL_BOOTSTRAP = os.path.join(REPO, "tools", "ocel_v2", "bootstrap.ocel.json")
GATE_CLI = os.path.join(HERE, "evidence_gate.py")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class WS9EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = uuid.uuid4().hex[:8]
        self.durable_dir = os.path.join(DURABLE_ROOT, self.run_id)
        os.makedirs(self.durable_dir, exist_ok=True)
        self.tmp_dirs: list[str] = []
        # 82-record hook JSONL — the exact artifact shape that went missing.
        lines = "\n".join(json.dumps({"i": i, "tool": "Bash", "ok": True}) for i in range(82)) + "\n"
        self.hook_jsonl = _write(os.path.join(self.durable_dir, "hook-run.jsonl"), lines)
        self.ocel_copy = shutil.copy(OCEL_BOOTSTRAP, os.path.join(self.durable_dir, "crown-run-v2.ocel.json"))

    def tearDown(self) -> None:
        shutil.rmtree(self.durable_dir, ignore_errors=True)
        for d in self.tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        if os.path.isdir(DURABLE_ROOT) and not os.listdir(DURABLE_ROOT):
            os.rmdir(DURABLE_ROOT)

    def _tmp_dir(self, base: str) -> str:
        d = os.path.join(base, f"ws9-{self.run_id}")
        os.makedirs(d, exist_ok=True)
        self.tmp_dirs.append(d)
        return d

    def _receipt(self, ref: EvidenceRef, name="receipt.json", **over) -> str:
        kw = dict(receipt_id=f"rcpt-{self.run_id}", subject_identity=ref.identity,
                  subject_sha256=ref.sha256, issued_at="2026-09-03T00:00:00+00:00", issuer="ws9-test")
        kw.update(over)
        return ArtifactReceipt(**kw).write(os.path.join(self.durable_dir, name))

    # --- happy paths -------------------------------------------------------

    def test_durable_jsonl_resolves_with_82_records(self):
        ref = make_ref("hook-run-82", self.hook_jsonl, "jsonl")
        res = resolve(ref)
        self.assertEqual(res.status, RESOLVED, res.to_dict())
        replay = next(c for c in res.checks if c.check == "ReplayCheck")
        self.assertEqual(replay.detail["records"], 82)

    def test_durable_ocel_resolves_through_real_validator(self):
        ref = make_ref("crown-run-v2.ocel", self.ocel_copy, "ocel")
        res = resolve(ref)
        self.assertEqual(res.status, RESOLVED, res.to_dict())
        replay = next(c for c in res.checks if c.check == "ReplayCheck")
        self.assertEqual(replay.detail["strict_type_mismatches"], 0)
        self.assertEqual(replay.detail["objects"], 2)

    def test_standing_issued_only_when_all_refs_resolve(self):
        good = make_ref("hook-run-82", self.hook_jsonl, "jsonl")
        rp = self._receipt(good)
        good = EvidenceRef(good.identity, good.durable_path, good.sha256, good.parser, rp)
        st = standing(Claim("c1", "82-record run happened", (good,)))
        self.assertTrue(st.issued)
        self.assertEqual(st.status, "STANDING")
        # one bad ref poisons the claim
        gone = EvidenceRef("ghost", os.path.join(self.durable_dir, "nope.json"), good.sha256, "json")
        st2 = standing(Claim("c2", "same claim + a ghost", (good, gone)))
        self.assertFalse(st2.issued)
        self.assertEqual(st2.status, refusal("DurabilityCheck"))
        st3 = standing(Claim("c3", "cites nothing", ()))
        self.assertFalse(st3.issued)

    # --- required failure classes ------------------------------------------

    def test_tmp_only_artifact_refused_durability(self):
        for base in ["/tmp", os.environ.get("TMPDIR") or "/tmp"]:
            d = self._tmp_dir(base)
            p = _write(os.path.join(d, "crown-run-v2.ocel.json"), _read(self.ocel_copy))
            self.assertTrue(os.path.exists(p))
            res = resolve(make_ref("tmp-ocel", p, "ocel"))
            self.assertEqual(res.status, refusal("DurabilityCheck"), (base, res.to_dict()))
            self.assertIn("transient root", res.checks[0].reason)

    def test_tmpdir_under_home_is_still_transient(self):
        # Falsifier for "durable == under $HOME": on this machine TMPDIR=~/.cache/tmp.
        tmpdir = os.environ.get("TMPDIR")
        self.assertIsNotNone(tmpdir)
        self.assertIn(os.path.realpath(tmpdir), transient_roots())

    def test_deleted_artifact_refused_durability(self):
        ref = make_ref("hook-run-82", self.hook_jsonl, "jsonl")
        self.assertEqual(resolve(ref).status, RESOLVED)
        os.remove(self.hook_jsonl)
        res = resolve(ref)
        self.assertEqual(res.status, refusal("DurabilityCheck"))
        self.assertIn("does not exist", res.checks[0].reason)

    def test_digest_mismatch_refused(self):
        ref = make_ref("hook-run-82", self.hook_jsonl, "jsonl")
        with open(self.hook_jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps({"i": 82, "tool": "Bash", "ok": True}) + "\n")   # now 83 records
        res = resolve(ref)
        self.assertEqual(res.status, refusal("DigestCheck"))
        self.assertNotEqual(res.checks[1].detail["actual"], ref.sha256)

    def test_stale_symlink_refused(self):
        link = os.path.join(self.durable_dir, "latest.jsonl")
        os.symlink(self.hook_jsonl, link)
        ref = EvidenceRef("hook-run-82", link, sha256_of(self.hook_jsonl), "jsonl")
        self.assertEqual(resolve(ref).status, RESOLVED)          # live symlink inside durable root OK
        os.remove(self.hook_jsonl)                               # target gone -> dangling
        res = resolve(ref)
        self.assertEqual(res.status, refusal("DurabilityCheck"))
        self.assertIn("dangling", res.checks[0].reason)

    def test_symlink_into_tmp_refused(self):
        d = self._tmp_dir("/tmp")
        target = _write(os.path.join(d, "hook.jsonl"), _read(self.hook_jsonl))
        link = os.path.join(self.durable_dir, "looks-durable.jsonl")
        os.symlink(target, link)
        res = resolve(EvidenceRef("hook-run-82", link, sha256_of(target), "jsonl"))
        self.assertEqual(res.status, refusal("DurabilityCheck"))
        self.assertIn("symlink into transient root", res.checks[0].reason)

    def test_replay_failure_refused(self):
        bad = _write(os.path.join(self.durable_dir, "broken.ocel.json"), '{"objects": [], "events": []}')
        res = resolve(make_ref("broken", bad, "ocel"))
        self.assertEqual(res.status, refusal("ReplayCheck"))
        bad2 = _write(os.path.join(self.durable_dir, "not.jsonl"), "{\n")
        self.assertEqual(resolve(make_ref("nj", bad2, "jsonl")).status, refusal("ReplayCheck"))

    def test_wrong_subject_receipt_refused(self):
        ref = make_ref("hook-run-82", self.hook_jsonl, "jsonl")
        other_sha = sha256_of(self.ocel_copy)
        rp = self._receipt(ref, subject_sha256=other_sha)
        res = resolve(EvidenceRef(ref.identity, ref.durable_path, ref.sha256, ref.parser, rp))
        self.assertEqual(res.status, refusal("ReceiptCheck"))
        self.assertIn("wrong subject", res.checks[-1].reason)
        rp2 = self._receipt(ref, name="r2.json", subject_identity="something-else")
        res2 = resolve(EvidenceRef(ref.identity, ref.durable_path, ref.sha256, ref.parser, rp2))
        self.assertIn("identity mismatch", res2.checks[-1].reason)

    def test_unreadable_receipt_refused(self):
        ref = make_ref("hook-run-82", self.hook_jsonl, "jsonl")
        rp = _write(os.path.join(self.durable_dir, "garbage.json"), "not json {")
        res = resolve(EvidenceRef(ref.identity, ref.durable_path, ref.sha256, ref.parser, rp))
        self.assertEqual(res.status, refusal("ReceiptCheck"))
        self.assertIn("unreadable receipt", res.checks[-1].reason)
        missing = os.path.join(self.durable_dir, "never-written.json")
        res2 = resolve(EvidenceRef(ref.identity, ref.durable_path, ref.sha256, ref.parser, missing))
        self.assertEqual(res2.status, refusal("ReceiptCheck"))
        self.assertIn("receipt not durable", res2.checks[-1].reason)

    def test_superseded_receipt_refused(self):
        ref = make_ref("hook-run-82", self.hook_jsonl, "jsonl")
        rp = self._receipt(ref, superseded_by="rcpt-newer")
        res = resolve(EvidenceRef(ref.identity, ref.durable_path, ref.sha256, ref.parser, rp))
        self.assertEqual(res.status, refusal("ReceiptCheck"))
        self.assertEqual(res.checks[-1].reason, "receipt superseded")

    # --- CLI + OCEL emission ------------------------------------------------

    def test_cli_gate_and_ocel_emission(self):
        good = make_ref("hook-run-82", self.hook_jsonl, "jsonl")
        tmpd = self._tmp_dir("/tmp")
        tmp_art = _write(os.path.join(tmpd, "x.json"), "{}")
        bad = make_ref("tmp-only", tmp_art, "json")
        refs = {"claim_id": "cli", "text": "t", "refs": [good.__dict__, bad.__dict__]}
        refs_path = _write(os.path.join(self.durable_dir, "refs.json"), json.dumps(refs))
        log = os.path.join(self.durable_dir, "gate.ocel.json")
        emitter = os.path.join(REPO, "tools", "ocel_v2", "emitter.py")
        subprocess.run([sys.executable, emitter, "init", log], check=True, capture_output=True)
        p = subprocess.run([sys.executable, GATE_CLI, refs_path, "--ocel", log], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("RESOLVED", p.stdout)
        self.assertIn(refusal("DurabilityCheck"), p.stdout)
        self.assertIn("issued=False", p.stdout)
        v = subprocess.run([sys.executable, os.path.join(REPO, "tools", "ocel_v2", "validate.py"), log],
                           capture_output=True, text=True)
        self.assertEqual(v.returncode, 0, v.stdout)
        doc = json.load(open(log))
        self.assertEqual({e["type"] for e in doc["events"]}, {"EvidenceResolved", "EvidenceRefused"})
        # all-good refs => exit 0
        refs_ok = _write(os.path.join(self.durable_dir, "ok.json"), json.dumps({"refs": [good.__dict__]}))
        p2 = subprocess.run([sys.executable, GATE_CLI, refs_ok], capture_output=True, text=True)
        self.assertEqual(p2.returncode, 0, p2.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
