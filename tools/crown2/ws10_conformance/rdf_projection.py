#!/usr/bin/env python3
"""Project an OCEL 2.0 JSON log to RDF (N-Triples, stdlib only).

Vocabulary (prefix ocel: <https://crown2.local/ocel#>):
  <ev:ID>  a ocel:Event ; ocel:eventType "T" ; ocel:time "..."^^xsd:dateTime ;
           ocel:relates <obj:ID> ; ocel:episode <obj:EP> ; ocel:attr_<name> literal .
  <obj:ID> a ocel:Object ; ocel:objectType "T" ; ocel:attr_<name> literal .

Two derived facts are materialized at projection time because SPARQL cannot
compute them: ocel:episode (the related ProcessEpisode, the case scope) and
ocel:evidenceExists (xsd:boolean; filesystem check of evidence_path relative
to --evidence-root). The .rq rules consume those triples.

CLI: python3 rdf_projection.py <log.ocel.json> [--evidence-root DIR] > out.nt
"""
from __future__ import annotations

import json
import os
import sys

from ocel_parser import OcelLog, load_ocel

OCEL = "https://crown2.local/ocel#"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF_TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _lit(v) -> str:
    if isinstance(v, bool):
        return f'"{str(v).lower()}"^^<{XSD}boolean>'
    if isinstance(v, int):
        return f'"{v}"^^<{XSD}integer>'
    if isinstance(v, float):
        return f'"{v}"^^<{XSD}double>'
    return f'"{_esc(str(v))}"'


def _iri(kind: str, ident: str) -> str:
    return f"<urn:{kind}:{ident}>"


def project(log: OcelLog, evidence_root: str = ".") -> list[str]:
    t: list[str] = []
    p = lambda name: f"<{OCEL}{name}>"  # noqa: E731
    for o in log.objects.values():
        s = _iri("obj", o.id)
        t.append(f"{s} {RDF_TYPE} {p('Object')} .")
        t.append(f"{s} {p('objectType')} {_lit(o.type)} .")
        for k, v in o.attrs.items():
            t.append(f"{s} {p('attr_' + k)} {_lit(v)} .")
    for e in log.events:
        s = _iri("ev", e.id)
        t.append(f"{s} {RDF_TYPE} {p('Event')} .")
        t.append(f"{s} {p('eventType')} {_lit(e.type)} .")
        t.append(f"{s} {p('time')} \"{e.time.isoformat()}\"^^<{XSD}dateTime> .")
        for oid in e.objects:
            t.append(f"{s} {p('relates')} {_iri('obj', oid)} .")
            if oid in log.objects and log.objects[oid].type == "ProcessEpisode":
                t.append(f"{s} {p('episode')} {_iri('obj', oid)} .")
        for k, v in e.attrs.items():
            t.append(f"{s} {p('attr_' + k)} {_lit(v)} .")
        if e.type == "ReceiptIssued":
            path = e.attrs.get("evidence_path")
            if path is None:
                for oid in log.related_of_type(e, "Receipt"):
                    path = log.objects[oid].attrs.get("evidence_path", path)
            exists = isinstance(path, str) and bool(path) and os.path.exists(
                path if os.path.isabs(path) else os.path.join(evidence_root, path))
            t.append(f"{s} {p('evidenceExists')} {_lit(bool(exists))} .")
    return t


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    root = os.path.dirname(os.path.abspath(path))
    if "--evidence-root" in argv:
        root = argv[argv.index("--evidence-root") + 1]
    sys.stdout.write("\n".join(project(load_ocel(path), root)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
