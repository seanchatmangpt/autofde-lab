#!/usr/bin/env python3
"""
Chicago-style tests for WS6 (real files, real subprocess validate.py, no mocks).

Run:  python3 -m unittest tools/crown2/ws6_projection/test_ws6_projection.py -v
"""

from __future__ import annotations

import glob
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from capability_graph import (  # noqa: E402
    QualifiedCapabilityReceipt,
    add_qualified,
    canonical_bytes,
    digest_of,
    domain_digest,
    empty_graph,
    graph_digest,
    load_graph,
    project_domain,
    save_graph,
)
import emit_projection  # noqa: E402


def _shuffle_keys(obj, rng):
    """Deep-copy with randomized dict insertion order (lists untouched)."""
    if isinstance(obj, dict):
        items = list(obj.items())
        rng.shuffle(items)
        return {k: _shuffle_keys(v, rng) for k, v in items}
    if isinstance(obj, list):
        return [_shuffle_keys(v, rng) for v in obj]
    return obj


R1 = QualifiedCapabilityReceipt(
    capability_id="cap.a", action="act_a", qualification_run_id="qr1",
    evidence_digest="sha256:aa", preconditions=("p1", "p2"), scopes=("s1",),
)
R2 = QualifiedCapabilityReceipt(
    capability_id="cap.b", action="act_b", qualification_run_id="qr2",
    evidence_digest="sha256:bb", preconditions=("p3",), scopes=("s2",),
)
WS = {"facts": ["p2", "p1", "p3"]}
AUTH = {"scopes": ["s1"]}


class Purity(unittest.TestCase):
    def test_add_qualified_is_immutable(self):
        g0 = empty_graph()
        d0 = graph_digest(g0)
        b0 = canonical_bytes(g0)
        g1, d1 = add_qualified(g0, R1)
        self.assertEqual(canonical_bytes(g0), b0)
        self.assertEqual(graph_digest(g0), d0)
        self.assertNotEqual(d0, d1)
        self.assertIn("cap.a", g1["capabilities"])
        self.assertNotIn("cap.a", g0["capabilities"])
        # aliasing falsifier: mutating g1 must not reach g0
        g1["capabilities"]["cap.a"]["action"] = "tampered"
        self.assertEqual(graph_digest(g0), d0)

    def test_add_qualified_rejects_duplicate_id(self):
        g1, _ = add_qualified(empty_graph(), R1)
        with self.assertRaises(ValueError):
            add_qualified(g1, R1)

    def test_add_order_independent_digest(self):
        g_ab, d_ab = add_qualified(add_qualified(empty_graph(), R1)[0], R2)
        g_ba, d_ba = add_qualified(add_qualified(empty_graph(), R2)[0], R1)
        self.assertEqual(d_ab, d_ba)

    def test_project_domain_deterministic_and_key_order_independent(self):
        g, _ = add_qualified(add_qualified(empty_graph(), R1)[0], R2)
        ref = project_domain(g, WS, AUTH)
        self.assertEqual(ref["actions"], ["act_a"])  # act_b needs scope s2
        self.assertEqual(ref["preconditions"], {"act_a": ["p1", "p2"]})
        self.assertEqual(domain_digest(ref), ref["digest"])
        rng = random.Random(1234)
        for _ in range(25):
            g_s, ws_s, au_s = _shuffle_keys(g, rng), _shuffle_keys(WS, rng), _shuffle_keys(AUTH, rng)
            out = project_domain(g_s, ws_s, au_s)
            self.assertEqual(canonical_bytes(out), canonical_bytes(ref))
            self.assertEqual(out["digest"], ref["digest"])
        # repeated call on the same objects is byte-identical
        self.assertEqual(canonical_bytes(project_domain(g, WS, AUTH)), canonical_bytes(ref))

    def test_project_domain_does_not_mutate_inputs(self):
        g, _ = add_qualified(empty_graph(), R1)
        before = (canonical_bytes(g), canonical_bytes(WS), canonical_bytes(AUTH))
        project_domain(g, WS, AUTH)
        self.assertEqual((canonical_bytes(g), canonical_bytes(WS), canonical_bytes(AUTH)), before)

    def test_world_state_and_authority_change_domain_digest(self):
        g, _ = add_qualified(empty_graph(), R1)
        d_full = project_domain(g, WS, AUTH)
        d_nofacts = project_domain(g, {"facts": []}, AUTH)
        d_noauth = project_domain(g, WS, {"scopes": []})
        self.assertEqual(d_nofacts["actions"], [])
        self.assertEqual(d_noauth["actions"], [])
        self.assertEqual(len({d_full["digest"], d_nofacts["digest"], d_noauth["digest"]}), 3)

    def test_no_append_on_action_lists_in_package(self):
        # The whole package, this test file included, must be append-free.
        needle = ".append" + "("
        def _lines(path):
            with open(path, encoding="utf-8") as f:
                return f.read().splitlines()

        hits = [
            f"{path}:{i}:{line.strip()}"
            for path in sorted(glob.glob(os.path.join(HERE, "*.py")))
            for i, line in enumerate(_lines(path), 1)
            if needle in line
        ]
        self.assertEqual(hits, [], f"found list accumulation: {hits}")


class Store(unittest.TestCase):
    def test_content_addressed_roundtrip_and_tamper_detection(self):
        g, d = add_qualified(empty_graph(), R1)
        with tempfile.TemporaryDirectory() as td:
            p = save_graph(td, g)
            self.assertEqual(os.path.basename(p), d.split(":")[1] + ".json")
            self.assertEqual(graph_digest(load_graph(p)), d)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"schema": g["schema"], "capabilities": {}}, f)
            with self.assertRaises(ValueError):
                load_graph(p)


class OcelEmission(unittest.TestCase):
    def test_emit_projection_validates_green_and_shows_delta(self):
        with tempfile.TemporaryDirectory() as td:
            delta = emit_projection.run(td)
            self.assertEqual(delta["validate_exit"], 0, delta["validate_stdout"])
            self.assertEqual(json.loads(delta["validate_stdout"]),
                             {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0})
            self.assertTrue(delta["graph_digest_changed"])
            self.assertTrue(delta["domain_digest_changed"])
            self.assertEqual(delta["before"]["actions"], [])
            self.assertEqual(delta["after"]["actions"], ["git_commit"])
            log = json.load(open(delta["ocel_log"], encoding="utf-8"))
            evs = [e for e in log["events"] if e["type"] == "DomainProjected"]
            self.assertEqual(len(evs), 2)
            attrs = {a["name"]: a["value"] for a in evs[1]["attributes"]}
            self.assertEqual(attrs["graph_digest"], delta["after"]["graph_digest"])
            self.assertEqual(attrs["domain_digest"], delta["after"]["domain_digest"])
            self.assertEqual(attrs["action_count"], 1)

    def test_bootstrap_log_still_validates(self):
        v = os.path.join(emit_projection.OCEL_DIR, "validate.py")
        b = os.path.join(emit_projection.OCEL_DIR, "bootstrap.ocel.json")
        r = subprocess.run([sys.executable, v, b], capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
