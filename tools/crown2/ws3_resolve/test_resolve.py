#!/usr/bin/env python3
"""
Chicago-style tests for WS3 resolve(): real marketplace dir, real ontology dir,
real OCEL emitter/validator. No mocks. Named skips only if a real dir is absent.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import resolve as R  # noqa: E402

MARKET = os.path.expanduser("~/ggen-marketplace/packs")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ONTOLOGY = os.path.join(REPO, "ontology")
OCEL_DIR = os.path.join(REPO, "tools", "ocel_v2")

HAS_MARKET = os.path.isdir(MARKET) and os.path.isfile(os.path.join(MARKET, "ocel-drift-pack", "pack.toml"))
HAS_ONTOLOGY = os.path.isfile(os.path.join(ONTOLOGY, "domain-evidence.ttl"))

ACTIONS = [
    {"name": "checkout_branch", "preconditions": ["repo_present"], "postconditions": ["on_branch"]},
    {"name": "run_tests", "preconditions": ["on_branch"], "postconditions": ["tests_green"]},
    {"name": "tag_release", "preconditions": ["tests_green"], "postconditions": ["release_tagged"]},
    {"name": "publish_docs", "preconditions": ["release_tagged"], "postconditions": ["docs_published"]},
]


def _kinds(cands):
    return [c.kind for c in cands]


class ResolveTests(unittest.TestCase):
    def test_invariant_no_generation_kind_exists(self):
        self.assertNotIn("code_generation", R.SOURCE_RANK)
        self.assertNotIn("generation", R.SOURCE_RANK)
        self.assertEqual(R.RULES["search_order"][-1]["kind"], "MANUFACTURING_GAP")

    @unittest.skipUnless(HAS_MARKET, f"real marketplace absent at {MARKET}")
    def test_marketplace_pack_covers_gap_and_generation_not_selected(self):
        gap = {"keywords": ["ocel", "drift"], "label": "coverage-gate for generation drift"}
        res = R.resolve(gap, local_actions=[], marketplace_dir=MARKET, ontology_dir=ONTOLOGY)
        self.assertEqual(res.selected.kind, "marketplace_pack")
        self.assertTrue(res.selected.ref.endswith("/ocel-drift-pack"), res.selected.ref)
        self.assertEqual(res.selected.score, 1.0)
        self.assertFalse(res.route_to_codegen)
        for c in res.candidates + res.dominated:
            self.assertNotIn("gener", c.kind)
        # non-dominated alternatives with equal score are retained, not collapsed
        equal = [c for c in res.candidates if c.kind == "marketplace_pack" and c.score == 1.0]
        self.assertGreaterEqual(len(equal), 1)
        self.assertTrue(os.path.isfile(res.selected.evidence["manifest"]))

    @unittest.skipUnless(HAS_MARKET, f"real marketplace absent at {MARKET}")
    def test_local_action_outranks_marketplace_but_marketplace_still_recorded(self):
        gap = {"keywords": ["ocel", "drift"]}
        acts = [{"name": "ocel_drift_check", "preconditions": [], "postconditions": ["drift_report"]}]
        res = R.resolve(gap, acts, marketplace_dir=MARKET, ontology_dir=ONTOLOGY)
        self.assertEqual(res.selected.kind, "local_action")
        allk = _kinds(res.candidates + res.dominated)
        self.assertIn("marketplace_pack", allk)
        # marketplace pack with equal score/depth but worse rank is dominated, and preserved in dominated[]
        self.assertTrue(any(c.kind == "marketplace_pack" and c.ref.endswith("ocel-drift-pack") for c in res.dominated))

    def test_composable_chain_depth_le_3(self):
        gap = {"keywords": ["release"], "current_facts": ["repo_present"], "needed_facts": ["release_tagged"]}
        res = R.resolve(gap, ACTIONS, marketplace_dir="/nonexistent", ontology_dir="/nonexistent")
        chains = [c for c in res.candidates + res.dominated if c.kind == "composable_chain"]
        self.assertEqual(len(chains), 1)
        self.assertEqual(chains[0].ref, "checkout_branch>run_tests>tag_release")
        self.assertEqual(chains[0].depth, 3)
        # keyword hit on tag_release (local, depth 1) but it does NOT cover needed facts from current state;
        # both are retained as non-dominated (local wins rank, chain wins score/coverage)
        self.assertIn("local_action", _kinds(res.candidates))
        self.assertIn("composable_chain", _kinds(res.candidates))
        self.assertFalse(res.route_to_codegen)

    def test_composable_chain_depth_4_not_found(self):
        gap = {"keywords": ["zz"], "current_facts": ["repo_present"], "needed_facts": ["docs_published"]}
        res = R.resolve(gap, ACTIONS, marketplace_dir="/nonexistent", ontology_dir="/nonexistent")
        self.assertEqual(res.selected.kind, "MANUFACTURING_GAP")

    @unittest.skipUnless(HAS_ONTOLOGY, f"real ontology absent at {ONTOLOGY}")
    def test_ontology_capability_individual_found_by_real_read(self):
        gap = {"keywords": ["merge", "recovery"]}
        res = R.resolve(gap, [], marketplace_dir="/nonexistent", ontology_dir=ONTOLOGY)
        self.assertEqual(res.selected.kind, "ontology_capability")
        self.assertEqual(res.selected.ref, "afl:domain_fix_git_cap_1")
        self.assertEqual(res.selected.evidence["capabilityName"], "merge_recovery")
        self.assertTrue(res.selected.evidence["file"].endswith("domain-evidence.ttl"))
        self.assertIn("recovery_branch_exists", res.selected.evidence["precondition"])

    @unittest.skipUnless(HAS_MARKET and HAS_ONTOLOGY, "real dirs absent")
    def test_manufacturing_gap_never_routes_to_codegen(self):
        gap = {"keywords": ["zorblat", "quuxification"]}
        res = R.resolve(gap, ACTIONS, marketplace_dir=MARKET, ontology_dir=ONTOLOGY)
        self.assertEqual(res.selected.kind, "MANUFACTURING_GAP")
        self.assertEqual(res.candidates, [res.selected])
        self.assertEqual(res.dominated, [])
        self.assertFalse(res.route_to_codegen)
        self.assertEqual(res.selected.evidence["searched"],
                         ["local_action", "marketplace_pack", "composable_chain", "ontology_capability"])

    def test_to_dict_matches_schema_shape(self):
        with open(os.path.join(HERE, "capability_resolution.schema.json")) as f:
            schema = json.load(f)
        res = R.resolve({"keywords": ["nothing"]}, [], "/nonexistent", "/nonexistent").to_dict()
        for k in schema["required"]:
            self.assertIn(k, res)
        self.assertIs(res["route_to_codegen"], False)
        self.assertIn(res["selected"]["kind"], schema["$defs"]["candidate"]["properties"]["kind"]["enum"])

    @unittest.skipUnless(HAS_MARKET and HAS_ONTOLOGY, "real dirs absent")
    def test_ocel_emission_validates_green(self):
        sys.path.insert(0, OCEL_DIR)
        import emitter  # noqa
        import emit_ocel  # noqa
        gap = {"keywords": ["ocel", "drift"], "label": "ws3-ocel-test"}
        res = R.resolve(gap, [], marketplace_dir=MARKET, ontology_dir=ONTOLOGY)
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "ws3.ocel.json")
            emitter.init(out)
            emit_ocel.emit_resolution(out, res, "res_1")
            p = subprocess.run([sys.executable, os.path.join(OCEL_DIR, "validate.py"), out],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(json.loads(p.stdout),
                             {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0})
            with open(out) as fh:
                log = json.load(fh)
            self.assertEqual(log["objects"][0]["type"], "CapabilityResolution")
            self.assertEqual(log["events"][0]["type"], "CapabilityResolved")


if __name__ == "__main__":
    unittest.main(verbosity=2)
