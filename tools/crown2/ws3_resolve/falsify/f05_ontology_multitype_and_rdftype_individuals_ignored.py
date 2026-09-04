#!/usr/bin/env python3
"""F05 (WEAKENS_CLAIM): scan_ontology only matches the literal form '<s> a afl:Capability ;'.
Valid Turtle spellings ('a owl:NamedIndividual , afl:Capability ;' and 'rdf:type afl:Capability ;')
are ignored, and a duplicate-IRI individual in the same file is dropped by (iri,file) dedupe
even when its capabilityName differs. Real file uses the matched form, so this is WEAKENS."""
import os, tempfile
from _common import R
TTL = '''@prefix afl: <http://x/afl#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
afl:cap_multi a owl:NamedIndividual , afl:Capability ;
    afl:capabilityName "rotate_credentials" .
afl:cap_rdftype rdf:type afl:Capability ;
    afl:capabilityName "revoke_session" .
afl:cap_dup a afl:Capability ;
    afl:capabilityName "first_name" .
afl:cap_dup a afl:Capability ;
    afl:capabilityName "quarantine_host" .
'''
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "x.ttl"), "w") as f:
        f.write(TTL)
    found = {i["name"] for i in R.scan_ontology(td)}
    print("scanned names:", sorted(found))
    missing = {"rotate_credentials", "revoke_session", "quarantine_host"} - found
    sel = [R.resolve({"keywords": [k]}, [], "/nonexistent", td).selected.kind
           for k in ("rotate credentials", "revoke session", "quarantine host")]
    print("resolve kinds:", sel)
    unresolved = [k for k, kind in zip(("rotate_credentials", "revoke_session", "quarantine_host"), sel) if kind != "ontology_capability"]
    assert not missing and not unresolved, (
        f"WRONG: scan ignored {sorted(missing)}; resolve() returned MANUFACTURING_GAP for {unresolved} "
        f"(quarantine_host is scanned but dropped by (iri,file) dedupe in search_ontology)")
print("F05 did not reproduce")
