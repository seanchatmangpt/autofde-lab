import sys
from rdflib import Graph
g = Graph().parse(sys.argv[1], format="turtle")
from pyshacl import validate
ok, _, txt = validate(g, shacl_graph=g, inference="rdfs")
print("triples", len(g), "conforms", ok)
if not ok: print(txt)
sys.exit(0 if ok else 1)
