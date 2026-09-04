#!/usr/bin/env python3
"""Chicago-style tests: real comparator, real emitter CLI subprocess, real validate.py,
real files on disk. No mocks."""
import json, os, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare, emit_ocel  # noqa: E402

def J(n):
    with open(os.path.join(HERE, "fixtures", n), encoding="utf-8") as f:
        return json.load(f)

with open(os.path.join(HERE, "schema.beam4pm.json"), encoding="utf-8") as _f:
    SCHEMA = json.load(_f)

def by_field(res):
    return {r["field"]: r for r in res["fields"]}

def by_name(res):
    return {r["name"]: r for r in res["transitions"]}

class MixedCase(unittest.TestCase):
    def setUp(self):
        self.res = compare.diff(J("predicted_mixed.json"), J("observed_mixed.json"), SCHEMA, J("prior.json"))
        self.f, self.t = by_field(self.res), by_name(self.res)

    def test_field_classes(self):
        self.assertEqual(self.f["ELIXIR_DEPS_READY"]["class"], "MATCH")
        self.assertEqual(self.f["MIX_TEST_GREEN"]["class"], "MISMATCH")
        self.assertEqual(self.f["CREDO_CLEAN"]["class"], "TYPE_ERROR")           # predicted "yes"
        self.assertEqual(self.f["PROD_RELEASE_HEALTHY"]["class"], "UNOBSERVABLE")
        self.assertEqual(self.f["MIX_TEST_FAILURES"]["class"], "MISSING_PREDICTION")
        self.assertEqual(self.f["MIX_TEST_FAILURES"]["observed"], "18")
        self.assertEqual(self.f["DIALYZER_CLEAN"]["class"], "MISMATCH")

    def test_transition_classes(self):
        self.assertEqual(self.t["deps_fetched"]["class"], "EXPECTED_TRANSITION_HAPPENED")
        self.assertEqual(self.t["tests_greened"]["class"], "EXPECTED_TRANSITION_ABSENT")
        self.assertEqual(self.t["dialyzer_fixed"]["class"], "UNEXPECTED_TRANSITION_HAPPENED")
        self.assertEqual(self.t["deps_stay_ready"]["class"], "NO_TRANSITION")

    def test_verdict_invalid_dominates(self):
        self.assertEqual(self.res["verdict"], "INVALID")

    def test_canonical_digest_stable(self):
        again = compare.diff(J("predicted_mixed.json"), J("observed_mixed.json"), SCHEMA, J("prior.json"))
        self.assertEqual(self.res["digest"], again["digest"])
        self.assertEqual(len(self.res["digest"]), 64)
        core = json.loads(self.res["canonical"])
        self.assertEqual(compare.digest(core), self.res["digest"])

class ConfirmedAndInvariant(unittest.TestCase):
    def test_confirmed(self):
        res = compare.diff(J("predicted_confirmed.json"), J("observed_confirmed.json"), SCHEMA, J("prior.json"))
        self.assertEqual(res["verdict"], "CONFIRMED")
        self.assertEqual(res["counts"]["EXPECTED_TRANSITION_HAPPENED"], 5)
        self.assertEqual(by_field(res)["MIX_TEST_FAILURES"]["class"], "NOT_APPLICABLE")

    def test_invariant_violated(self):
        res = compare.diff(J("predicted_invariant.json"), J("observed_invariant.json"), SCHEMA, J("prior_invariant.json"))
        self.assertEqual(by_name(res)["deps_stay_ready"]["class"], "EXPECTED_INVARIANT_VIOLATED")
        self.assertEqual(res["verdict"], "REFUTED")

    def test_unobservable_with_prediction_is_partial(self):
        p = J("predicted_confirmed.json"); p["PROD_RELEASE_HEALTHY"] = True
        res = compare.diff(p, J("observed_confirmed.json"), SCHEMA, J("prior.json"))
        self.assertEqual(by_field(res)["PROD_RELEASE_HEALTHY"]["class"], "UNOBSERVABLE")
        self.assertEqual(res["verdict"], "PARTIAL")

    def test_missing_observation_is_partial(self):
        res = compare.diff({"ELIXIR_DEPS_READY": True}, {}, SCHEMA)
        self.assertEqual(by_field(res)["ELIXIR_DEPS_READY"]["class"], "MISSING_OBSERVATION")
        self.assertEqual(res["verdict"], "PARTIAL")

    def test_undeclared_prediction_is_type_error(self):
        res = compare.diff({"NOT_A_FIELD": 1}, {}, SCHEMA)
        self.assertEqual(by_field(res)["NOT_A_FIELD"]["class"], "TYPE_ERROR")

    def test_bool_int_confusion_is_type_error(self):
        res = compare.diff({"ELIXIR_DEPS_READY": 1}, {"ELIXIR_DEPS_READY": True}, SCHEMA)
        self.assertEqual(by_field(res)["ELIXIR_DEPS_READY"]["class"], "TYPE_ERROR")

class RealEmitterRoundTrip(unittest.TestCase):
    def test_emit_and_validate_all_cases(self):
        for case in ("mixed", "confirmed", "invariant"):
            with tempfile.TemporaryDirectory() as d:
                out = os.path.join(d, "out.ocel.json")
                res, vout = emit_ocel.emit(out, case)
                self.assertEqual(json.loads(vout), {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0})
                with open(out, encoding="utf-8") as fh:
                    log = json.load(fh)
                ev = [e for e in log["events"] if e["type"] == "PredictionCompared"][0]
                attrs = {a["name"]: a["value"] for a in ev["attributes"]}
                self.assertEqual(attrs["verdict"], res["verdict"])
                self.assertEqual(attrs["digest"], res["digest"])
                self.assertIsInstance(attrs["n_match"], int)
                self.assertEqual(json.loads(attrs["field_classes_json"]), res["fields"])
                self.assertEqual(len(ev["relationships"]), 3)

    def test_emitter_rejects_untyped_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "o.json")
            emitter = os.path.join(HERE, "..", "..", "ocel_v2", "emitter.py")
            subprocess.run([sys.executable, emitter, "init", out], check=True, capture_output=True)
            r = subprocess.run([sys.executable, emitter, "add-event", out, "PredictionCompared", "e1",
                                json.dumps({"verdict": {"nested": True}}), ""], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("nested JSON must use", r.stderr)

if __name__ == "__main__":
    unittest.main(verbosity=2)
