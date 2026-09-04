#!/usr/bin/env python3
"""Chicago-style tests for WS4 gap -> ggen manifest.

Real collaborators only: the on-disk ggen-marketplace pack registry, tomllib,
the real `ggen` CLI (Docker-wrapped) when on PATH, the real OCEL emitter and
validate.py. No mocks/patches.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OCEL_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "ocel_v2"))

from manifest import build_stub, requirements_to_ttl  # noqa: E402
from ocel_emit import emit_stub  # noqa: E402
from packs import load_registry  # noqa: E402
from requirement import CapabilityRequirement, GapDiagnosis, TemplateBinding, fixture_requirements  # noqa: E402
from validate_cli import STAGE_ROOT, ggen_available, validate_stub  # noqa: E402

REG = load_registry()


class RequirementSchemaTests(unittest.TestCase):
    def test_two_fixture_requirements_round_trip_json(self):
        reqs = fixture_requirements()
        self.assertEqual(len(reqs), 2)
        for r in reqs:
            back = CapabilityRequirement.from_json(r.to_json())
            self.assertEqual(back, r)

    def test_invalid_authority_and_anchor_refused(self):
        r = fixture_requirements()[0]
        d = r.to_dict()
        d["authority_class"] = "SUDO"
        with self.assertRaises(ValueError):
            CapabilityRequirement.from_dict(d)
        d = r.to_dict()
        d["semantic_anchors"] = ["http://example.org/nope"]
        with self.assertRaises(ValueError):
            CapabilityRequirement.from_dict(d)


class ManifestStubTests(unittest.TestCase):
    def test_registry_admits_bound_pack(self):
        self.assertIn("capability-lineage-propagation-pack", REG)
        p = REG["capability-lineage-propagation-pack"]
        self.assertIn("propagation-plan.json.tera", p.templates)
        self.assertIn("30-clean-plan.rq", p.queries)

    def test_stub_is_real_ggen_toml_format(self):
        stub = build_stub(fixture_requirements(), REG)
        doc = tomllib.loads(stub.to_toml())
        self.assertEqual(set(doc), {"project", "ontology", "generation"})
        self.assertEqual(doc["ontology"]["source"], "ontology/requirements.ttl")
        self.assertEqual(doc["ontology"]["prefixes"]["afl"], "urn:autofde-lab:")
        rules = doc["generation"]["rules"]
        self.assertEqual(len(rules), 3)   # 2 bound + ws4 projection
        for r in rules:
            self.assertEqual(set(r), {"name", "query", "template", "output_file", "mode"})
            self.assertIn("file", r["query"])
            self.assertIn("file", r["template"])
            self.assertFalse(os.path.isabs(r["query"]["file"]))
        self.assertEqual(rules[0]["template"]["file"],
                         "vendor/capability-lineage-propagation-pack/templates/propagation-plan.json.tera")

    def test_preservation_lists_unmapped_extra_with_reason(self):
        stub = build_stub(fixture_requirements(), REG)
        rep = stub.preservation_report()
        self.assertEqual(rep["unbound"], [])
        self.assertEqual([u["field"] for u in rep["unmapped"]], ["extra"])
        self.assertIn("owner", rep["unmapped"][0]["reason"])
        self.assertFalse(rep["preserved"])
        # second requirement alone has no extra -> fully preserved
        rep2 = build_stub([fixture_requirements()[1]], REG).preservation_report()
        self.assertTrue(rep2["preserved"])
        self.assertEqual(len(rep2["mapped"]), 10)

    def test_unknown_pack_is_reported_unbound_not_silently_dropped(self):
        r = fixture_requirements()[1]
        bad = CapabilityRequirement.from_dict({**r.to_dict(),
                                               "binding": {"pack": "no-such-pack", "template": "x.tera",
                                                           "query": "x.rq", "output_file": "o"}})
        stub = build_stub([bad], REG)
        self.assertEqual(stub.unbound, [{"requirement": r.requirement_id, "reason": "pack not admitted: no-such-pack"}])
        self.assertEqual(len(stub.rules), 1)  # only the ws4 projection rule remains

    def test_ttl_carries_every_semantic_anchor(self):
        reqs = fixture_requirements()
        ttl = requirements_to_ttl(reqs)
        for r in reqs:
            for iri in r.semantic_anchors:
                self.assertIn(f"<{iri}>", ttl)
            self.assertIn(f'ws4:authorityClass "{r.authority_class}"', ttl)


@unittest.skipUnless(ggen_available(), "ggen CLI not on PATH")
class RealGgenCliTests(unittest.TestCase):
    def test_graph_validate_and_dry_run_alive(self):
        res = validate_stub(build_stub(fixture_requirements(), REG), stage_name="test-dry")
        self.assertEqual(res["graph_validate"]["status"], "ALIVE", res["graph_validate"])
        self.assertEqual(res["sync_dry_run"]["status"], "ALIVE", res["sync_dry_run"])
        out = json.loads(res["sync_dry_run"]["stdout_tail"])
        self.assertEqual(sorted(out["written"]), [
            "generated/ws4/propagation-plan.json",
            "generated/ws4/qualification_court.py",
            "generated/ws4/requirements.json",
        ])

    def test_real_sync_projects_every_requirement_field(self):
        reqs = fixture_requirements()
        res = validate_stub(build_stub(reqs, REG), stage_name="test-real")
        pd = res["project_dir"]
        cp = subprocess.run(["ggen", "sync", "run", "--format", "json"], cwd=pd, capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stderr[-1500:])
        with open(os.path.join(pd, "generated/ws4/requirements.json")) as fh:
            rendered = json.load(fh)
        rows = {row["requirement"]: row for row in rendered["requirements"]}
        for r in reqs:
            row = rows[f"urn:crown2:ws4#{r.requirement_id}"]
            self.assertEqual(row["transition"], r.needed_transition)
            self.assertEqual(row["authority"], r.authority_class)
            self.assertEqual(row["strategy"], r.qualification_strategy)
            self.assertEqual(row["observed"], r.gap.observed_state)
            self.assertEqual(set(row["anchors"].split("|")), set(r.semantic_anchors))
            self.assertEqual(set(row["preconditions"].split("|")), set(r.preconditions))
            self.assertEqual(set(row["postconditions"].split("|")), set(r.postconditions))
        # bound pack template rendered from the vendored pack ontology, too
        with open(os.path.join(pd, "generated/ws4/propagation-plan.json")) as fh:
            plan = json.load(fh)
        self.assertEqual(plan["authority"], "CONSTRUCT")
        self.assertEqual(len(plan["plans"]), 1)


class OcelEvidenceTests(unittest.TestCase):
    def test_emit_stub_keeps_validate_green(self):
        log = os.path.join(STAGE_ROOT, "ws4.ocel.json")
        os.makedirs(STAGE_ROOT, exist_ok=True)
        if os.path.exists(log):
            os.remove(log)
        reqs = fixture_requirements()
        out = emit_stub(log, reqs, build_stub(reqs, REG))
        self.assertEqual(out["gaps"], ["gap:gap-001", "gap:gap-002"])
        cp = subprocess.run([sys.executable, os.path.join(OCEL_DIR, "validate.py"), log],
                            capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertEqual(json.loads(cp.stdout.strip().splitlines()[-1]),
                         {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0})
        with open(log) as fh:
            data = json.load(fh)
        ev = {e["id"]: e for e in data["events"]}
        rel = {r["objectId"] for r in ev["ev:plan:ws4:stub:produced"]["relationships"]}
        self.assertEqual(rel, {"plan:ws4:stub", "gap:gap-001", "gap:gap-002"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
