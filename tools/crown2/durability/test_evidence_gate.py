#!/usr/bin/env python3
"""Chicago-style tests for evidence_gate: real files on disk, real digests,
real tools/ocel_v2/validate.py. No test doubles.

Run: python3 -m unittest tools/crown2/durability/test_evidence_gate.py -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import evidence_gate as eg  # noqa: E402

_OCEL_V2 = os.path.normpath(os.path.join(_HERE, "..", "..", "ocel_v2"))
BOOTSTRAP_OCEL = os.path.join(_OCEL_V2, "bootstrap.ocel.json")
BROKEN_OCEL = os.path.join(_OCEL_V2, "fixture_broken.json")
# The reference that was cited as prior work and never located on disk.
NEVER_FOUND = "/Users/sac/crown-2-integration/autofde-lab/tools/crown2/run/crown-run-v2.ocel.json"
# Durable scratch for mutation cases: inside the repo tree, cleaned per test.
SCRATCH = os.path.join(_HERE, ".test-scratch")


class ResolveTests(unittest.TestCase):
    def setUp(self) -> None:
        os.makedirs(SCRATCH, exist_ok=True)

    def tearDown(self) -> None:
        for n in os.listdir(SCRATCH):
            os.remove(os.path.join(SCRATCH, n))
        os.rmdir(SCRATCH)

    def test_never_found_v2_run_is_refused_at_identity(self) -> None:
        self.assertFalse(os.path.exists(NEVER_FOUND))
        r = eg.resolve({"path": NEVER_FOUND, "sha256": "0" * 64, "parser": "ocel"})
        self.assertEqual(r["status"], "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:identity]")
        self.assertEqual(r["checks"]["identity"]["detail"], "path-does-not-exist")

    def test_bootstrap_ocel_resolves(self) -> None:
        digest = eg.sha256_file(BOOTSTRAP_OCEL)
        r = eg.resolve({"path": BOOTSTRAP_OCEL, "sha256": digest, "parser": "ocel"})
        self.assertEqual(r["status"], "RESOLVED", r)
        self.assertEqual(r["actual_sha256"], digest)
        self.assertEqual(
            r["checks"]["parser"]["detail"],
            'ocel:{"dangling_refs": 0, "duplicate_ids": 0, "strict_type_mismatches": 0}',
        )

    def test_digest_mismatch_is_refused_at_sha256(self) -> None:
        r = eg.resolve({"path": BOOTSTRAP_OCEL, "sha256": "f" * 64, "parser": "ocel"})
        self.assertEqual(r["status"], "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:sha256]")

    def test_missing_digest_is_refused_at_sha256(self) -> None:
        r = eg.resolve({"path": BOOTSTRAP_OCEL, "parser": "ocel"})
        self.assertEqual(r["status"], "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:sha256]")

    def test_broken_ocel_fixture_is_refused_at_parser(self) -> None:
        digest = eg.sha256_file(BROKEN_OCEL)
        r = eg.resolve({"path": BROKEN_OCEL, "sha256": digest, "parser": "ocel"})
        self.assertEqual(r["status"], "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:parser]")
        self.assertTrue(r["checks"]["parser"]["detail"].startswith("ocel:"))

    def test_scratch_paths_are_refused_at_durable(self) -> None:
        for root in ("/private/tmp", os.environ.get("TMPDIR") or "/tmp"):
            d = os.path.join(root, "crown2-evidence-gate-test")
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "x.json")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("{}")
            try:
                r = eg.resolve({"path": p, "sha256": eg.sha256_file(p), "parser": "json"})
                self.assertEqual(r["status"], "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:durable]", r)
            finally:
                os.remove(p)
                os.rmdir(d)

    def test_relative_and_empty_paths_are_refused_at_identity(self) -> None:
        r = eg.resolve({"path": "tools/ocel_v2/bootstrap.ocel.json", "sha256": "0" * 64})
        self.assertEqual(r["checks"]["identity"]["detail"], "path-not-absolute")
        p = os.path.join(SCRATCH, "empty.txt")
        open(p, "w").close()
        r = eg.resolve({"path": p, "sha256": "0" * 64})
        self.assertEqual(r["checks"]["identity"]["detail"], "empty-file")

    def test_sha256_and_markdown_parsers(self) -> None:
        p = os.path.join(SCRATCH, "a.sha256")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("a" * 64 + "  a.json\n")
        r = eg.resolve({"path": p, "sha256": eg.sha256_file(p), "parser": "sha256"})
        self.assertEqual(r["status"], "RESOLVED")
        m = os.path.join(SCRATCH, "r.md")
        with open(m, "w", encoding="utf-8") as fh:
            fh.write("no heading\n")
        r = eg.resolve({"path": m, "sha256": eg.sha256_file(m), "parser": "markdown"})
        self.assertEqual(r["status"], "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:parser]")

    def test_mutation_after_binding_is_refused(self) -> None:
        p = os.path.join(SCRATCH, "m.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"a": 1}, fh)
        bound = eg.sha256_file(p)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"a": 2}, fh)
        r = eg.resolve({"path": p, "sha256": bound, "parser": "json"})
        self.assertEqual(r["status"], "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:sha256]")

    def test_gate_bundle_standing_requires_all_resolved(self) -> None:
        good = {"path": BOOTSTRAP_OCEL, "sha256": eg.sha256_file(BOOTSTRAP_OCEL), "parser": "ocel"}
        rep = eg.gate_bundle([good])
        self.assertEqual(rep["standing"], "ALIVE[ALL_EVIDENCE_RESOLVED_FROM_DURABLE_PATHS]")
        rep = eg.gate_bundle([good, {"path": NEVER_FOUND, "sha256": "0" * 64, "parser": "ocel"}])
        self.assertEqual(rep["standing"], "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:1_of_2]")
        self.assertEqual(rep["unresolved"][0]["path"], NEVER_FOUND)

    def test_canonical_json_is_key_sorted_and_compact(self) -> None:
        self.assertEqual(eg.canonical_json({"b": 1, "a": [1, 2]}), b'{"a":[1,2],"b":1}')


if __name__ == "__main__":
    unittest.main()
