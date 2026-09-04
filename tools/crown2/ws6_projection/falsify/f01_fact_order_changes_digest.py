"""F01: world_state.facts is a set semantically, but project_domain hashes it as a list.
Same facts, different list order / duplicates => same admitted actions, DIFFERENT domain digest."""
from _target import *
g, _ = add_qualified(empty_graph(), QualifiedCapabilityReceipt("c", "act", "qr", "sha256:00", ("p1", "p2"), (), ("s",)))
auth = {"scopes": ["s"]}
a = project_domain(g, {"facts": ["p1", "p2"]}, auth)
b = project_domain(g, {"facts": ["p2", "p1"]}, auth)
c = project_domain(g, {"facts": ["p1", "p1", "p2"]}, auth)
print("actions equal:", a["actions"] == b["actions"] == c["actions"] == ["act"])
print("digests:", a["digest"][:24], b["digest"][:24], c["digest"][:24])
assert a["actions"] == b["actions"] == c["actions"]
assert a["digest"] != b["digest"] and a["digest"] != c["digest"], "NOT_REPRODUCED"
print("REPRODUCED: list order / duplicate facts change the domain digest with identical semantics")
