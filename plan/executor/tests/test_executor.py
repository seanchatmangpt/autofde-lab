import json, os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from pddl import Executor, parse_plan, write_receipts
from replay import verify
FX = os.path.join(os.path.dirname(HERE), "fixtures")
DOM = open(os.path.join(FX, "servengine_ideal_domain.pddl")).read()
PROB = open(os.path.join(FX, "problem_enterprise_ops.pddl")).read()
PLAN = open(os.path.join(FX, "plan_expected.soln")).read()


def run(text):
    return Executor(DOM, PROB).run(parse_plan(text))


class T(unittest.TestCase):
    def test_expected_trace(self):
        ex = run(PLAN)
        self.assertIsNone(ex.refused)
        self.assertTrue(ex.goal_ok())
        self.assertEqual(ex.ledger(), {"AR": 58000, "AP": 25500, "margin": 32500})
        self.assertEqual(len(ex.receipts), 9)
        self.assertTrue(all(r["standing"]["value"] == "PASS" for r in ex.receipts))

    def test_byte_identical_replay(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a"), os.path.join(d, "b")
            write_receipts(a, run(PLAN).receipts); write_receipts(b, run(PLAN).receipts)
            self.assertEqual(open(a, "rb").read(), open(b, "rb").read())
            self.assertTrue(verify(a)[0])

    def test_tamper_one_byte(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.jsonl")
            write_receipts(p, run(PLAN).receipts)
            raw = bytearray(open(p, "rb").read())
            i = raw.index(b"58000")
            raw[i] = ord("9")  # 58000 -> 98000
            open(p, "wb").write(bytes(raw))
            ok, msg = verify(p)
            self.assertFalse(ok, msg)

    def test_tamper_every_line_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.jsonl")
            write_receipts(p, run(PLAN).receipts)
            lines = open(p).read().split("\n")[:-1]
            for i in range(len(lines)):
                bad = list(lines); bad[i] = bad[i].replace('"PASS"', '"PAS5"', 1)
                q = os.path.join(d, f"t{i}")
                open(q, "w").write("\n".join(bad) + "\n")
                self.assertFalse(verify(q)[0], i)

    def test_reorder_refused(self):
        rows = [l for l in PLAN.splitlines() if l and not l.startswith(";")]
        ts = [r.split(":", 1)[0] for r in rows]
        acts = [r.split(":", 1)[1] for r in rows]
        acts[2], acts[3] = acts[3], acts[2]  # dispatch before triage, times kept
        ex = run("\n".join(f"{t}:{a}" for t, a in zip(ts, acts)))
        self.assertIsNotNone(ex.refused)
        self.assertIn("precondition:at-start:(wo-state-triaged wo_reactive_9001)", ex.refused)
        last = ex.receipts[-1]
        self.assertEqual(last["standing"]["value"], "REFUSED")
        self.assertEqual(last["standing"]["broken_term"], ex.refused)
        self.assertFalse(ex.goal_ok())

    def test_remove_action_refused(self):
        rows = [l for l in PLAN.splitlines() if l and not l.startswith(";")]
        ex = run("\n".join(rows[:4] + rows[5:]))  # drop execute-site-visit
        self.assertIsNotNone(ex.refused)
        self.assertIn("at-start", ex.refused)


if __name__ == "__main__":
    unittest.main()
