#!/usr/bin/env python3
"""Chicago-style tests: real fixtures on disk, real emitter, real validate.py,
real rules engine, real rdflib SPARQL (skipped visibly if rdflib is absent).

Run: python3 -m unittest -v test_conformance   (from this directory)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
VALIDATE = os.path.join(HERE, "..", "..", "ocel_v2", "validate.py")
sys.path.insert(0, HERE)

from ocel_parser import load_ocel  # noqa: E402
from rules import RULES, check  # noqa: E402

RULE_IDS = list(RULES)
EXPECTED = {  # fixture -> {rule_id: violating event ids}; empty = clean
    "clean": {},
    "violates_R01": {"R01": ["e03"]},
    "violates_R02": {"R02": ["e04"]},
    "violates_R03": {"R03": ["e08"]},
    "violates_R04": {"R04": ["e08"]},
    "violates_R05": {"R05": ["e08"]},
    "violates_R06": {"R06": ["e09"]},
    "violates_R07": {"R07": ["e09", "e11"]},
    "violates_R08": {"R08": ["e01"]},
    "violates_R09": {"R09": ["e18b"]},
    "violates_R10": {"R10": ["e15"]},
}


def _expand(short: dict) -> dict:
    full = {rid: [] for rid in RULE_IDS}
    for k, v in short.items():
        full[next(r for r in RULE_IDS if r.startswith(k))] = v
    return full


try:
    import rdflib  # noqa: F401
    HAVE_RDFLIB = True
except ImportError:
    HAVE_RDFLIB = False


class FixturesBuilt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, os.path.join(FIX, "build_fixtures.py")], check=True,
                       capture_output=True)

    def test_every_fixture_passes_strict_validate(self):
        for name in EXPECTED:
            p = subprocess.run([sys.executable, VALIDATE, os.path.join(FIX, f"{name}.ocel.json")],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, f"{name}: {p.stdout}")
            self.assertEqual(json.loads(p.stdout),
                             {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0})


class PythonEngine(unittest.TestCase):
    def test_each_fixture_violates_exactly_expected_rules(self):
        for name, short in EXPECTED.items():
            with self.subTest(fixture=name):
                res = check(load_ocel(os.path.join(FIX, f"{name}.ocel.json")), FIX)
                self.assertEqual(res, _expand(short))

    def test_rules_cli_exit_code(self):
        clean = subprocess.run([sys.executable, os.path.join(HERE, "rules.py"),
                                os.path.join(FIX, "clean.ocel.json")], capture_output=True)
        self.assertEqual(clean.returncode, 0)
        bad = subprocess.run([sys.executable, os.path.join(HERE, "rules.py"),
                              os.path.join(FIX, "violates_R08.ocel.json")], capture_output=True)
        self.assertEqual(bad.returncode, 1)


@unittest.skipUnless(HAVE_RDFLIB, "rdflib not importable in this interpreter; rules.py is the executable path")
class SparqlEngine(unittest.TestCase):
    def test_sparql_agrees_with_python_engine(self):
        from run_sparql import run
        for name, short in EXPECTED.items():
            with self.subTest(fixture=name):
                self.assertEqual(run(os.path.join(FIX, f"{name}.ocel.json"), FIX), _expand(short))


if __name__ == "__main__":
    unittest.main()
