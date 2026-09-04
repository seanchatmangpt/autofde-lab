#!/usr/bin/env python3
"""Run the sparql/*.rq falsifiers over the RDF projection of an OCEL log.

Requires rdflib. If rdflib is not importable this exits 3 and prints a JSON
record naming the missing library; rules.py (pure stdlib) is the executable
path in that case. Output shape mirrors rules.py: {rule_id: [event ids]}.

CLI: python3 run_sparql.py <log.ocel.json> [--evidence-root DIR]
"""
from __future__ import annotations

import glob
import json
import os
import sys

from ocel_parser import load_ocel
from rdf_projection import project

HERE = os.path.dirname(os.path.abspath(__file__))
SPARQL_DIR = os.path.join(HERE, "sparql")


def run(path: str, evidence_root: str) -> dict[str, list[str]]:
    import rdflib  # noqa: F401  (deferred so the ImportError is reportable)

    g = rdflib.Graph()
    g.parse(data="\n".join(project(load_ocel(path), evidence_root)) + "\n", format="nt")
    out: dict[str, list[str]] = {}
    for rq in sorted(glob.glob(os.path.join(SPARQL_DIR, "R*.rq"))):
        rid = os.path.splitext(os.path.basename(rq))[0]
        with open(rq, encoding="utf-8") as f:
            rows = g.query(f.read())
        ids = sorted(str(r[0]).removeprefix("urn:ev:") for r in rows)
        out[rid] = ids
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    root = os.path.dirname(os.path.abspath(path))
    if "--evidence-root" in argv:
        root = argv[argv.index("--evidence-root") + 1]
    try:
        res = run(path, root)
    except ImportError as e:
        print(json.dumps({"log": path, "status": "BLOCKED", "missing_library": "rdflib",
                          "error": str(e), "executable_path": "rules.py"}))
        return 3
    print(json.dumps({"log": path, "engine": "sparql/rdflib", "violations": res}, indent=1))
    return 1 if any(res.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
