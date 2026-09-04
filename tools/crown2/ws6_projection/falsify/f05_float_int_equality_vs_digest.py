"""F05: equal Python values (1 == 1.0 == True) hash into the same frozenset (same admission)
but canonicalize to different JSON => same inputs (by ==) give different digests;
also NaN is emitted as non-JSON and never equals itself."""
from _target import *
g, _ = add_qualified(empty_graph(), QualifiedCapabilityReceipt("c", "act", "qr", "sha256:00", (1,), (), ()))
a = project_domain(g, {"facts": [1]}, {"scopes": []})
b = project_domain(g, {"facts": [1.0]}, {"scopes": []})
t = project_domain(g, {"facts": [True]}, {"scopes": []})
print("actions:", a["actions"], b["actions"], t["actions"])
print("digests:", a["digest"][:20], b["digest"][:20], t["digest"][:20])
assert a["actions"] == b["actions"] == t["actions"] == ["act"]
assert len({a["digest"], b["digest"], t["digest"]}) == 3, "NOT_REPRODUCED"
nan = float("nan")
cb = canonical_bytes({"facts": [nan]})
print("canonical bytes with NaN:", cb)
assert b"NaN" in cb  # not valid JSON per RFC 8259/8785
print("REPRODUCED: ==-equal inputs, 3 digests; NaN produces non-JSON canonical bytes")
