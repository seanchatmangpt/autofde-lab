#!/usr/bin/env python3
"""Chicago-style tests: real subprocesses, real fixture copies, real git worktree,
real emitter + validator. No mocks."""
import json, os, subprocess, sys, unittest, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gym  # noqa: E402

VALIDATE = os.path.join(gym.REPO_ROOT, "tools", "ocel_v2", "validate.py")


class GymTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cands = {c.name: c for c in gym.load_candidates(os.path.join(HERE, "candidates.json"))}
        cls.g = gym.ProjectGym()

    def test_marker_action_qualified_and_subject_restored(self):
        r = self.g.qualify(self.cands["marker_file_action"])
        self.assertEqual(r.verdict, gym.QUALIFIED)
        self.assertNotEqual(r.subject_digest_before, r.subject_digest_after)
        self.assertEqual(r.evidence["files_added"], ["MARKER.txt"])
        self.assertTrue(r.evidence["subject_restored"])
        self.assertFalse(os.path.exists(r.evidence["run_dir"]))
        self.assertFalse(os.path.exists(os.path.join(HERE, "fixtures/marker_subject/MARKER.txt")))
        self.assertIs(gym.admit(r), r)
        self.assertIs(type(gym.admit(r.to_dict())), gym.QualificationReceipt)

    def test_false_postcondition_rejected_and_refused(self):
        r = self.g.qualify(self.cands["false_postcondition_action"])
        self.assertEqual(r.verdict, gym.REJECTED)
        self.assertEqual(r.subject_digest_before, r.subject_digest_after)
        held = [o["holds"] for o in r.observed_effects]
        self.assertEqual(held, [True, False])
        with self.assertRaises(gym.AdmissionRefused):
            gym.admit(r)

    def test_worktree_timeout_inconclusive(self):
        r = self.g.qualify(self.cands["worktree_timeout_action"])
        self.assertEqual(r.verdict, gym.INCONCLUSIVE)
        self.assertTrue(r.evidence["run"]["timed_out"])
        self.assertTrue(r.evidence["subject_restored"])
        wt = subprocess.run(["git", "worktree", "list"], cwd=gym.REPO_ROOT, capture_output=True, text=True).stdout
        self.assertNotIn(r.evidence["run_dir"], wt)
        with self.assertRaises(gym.AdmissionRefused):
            gym.admit(r)

    def test_tampered_receipt_refused(self):
        r = self.g.qualify(self.cands["false_postcondition_action"])
        d = r.to_dict()
        d["verdict"] = gym.QUALIFIED  # forge verdict, keep old digest
        with self.assertRaises(gym.AdmissionRefused):
            gym.admit(d)
        d.pop("digest")  # forge verdict, drop digest: still refused (effects not all holding)
        with self.assertRaises(gym.AdmissionRefused):
            gym.admit(d)

    def test_ocel_emit_validates(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "ws5.ocel.json")
            r1 = self.g.qualify(self.cands["marker_file_action"])
            r2 = self.g.qualify(self.cands["false_postcondition_action"])
            gym.emit_ocel(p, r1, init=True)
            gym.emit_ocel(p, r2)
            out = subprocess.run([sys.executable, VALIDATE, p], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            self.assertEqual(json.loads(out.stdout), {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0})
            with open(p) as fh:
                log = json.load(fh)
            self.assertEqual(sorted(e["type"] for e in log["events"]),
                             ["QualificationObserved", "QualificationObserved", "ReceiptIssued", "ReceiptIssued"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
