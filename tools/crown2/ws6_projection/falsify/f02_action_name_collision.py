"""F02: two qualified capabilities exposing the same action name with different
preconditions collide in the dict comprehension; the exposed preconditions are those of
whichever capability_id sorts last, silently dropping the other's contract."""
from _target import *
g, _ = add_qualified(empty_graph(), QualifiedCapabilityReceipt("cap.a", "deploy", "qr1", "sha256:01", ("tests_green",), (), ()))
g, _ = add_qualified(g, QualifiedCapabilityReceipt("cap.b", "deploy", "qr2", "sha256:02", ("approved",), (), ()))
d = project_domain(g, {"facts": ["tests_green", "approved"]}, {"scopes": []})
print("actions:", d["actions"], "preconditions:", d["preconditions"])
assert d["actions"] == ["deploy"]
assert d["preconditions"]["deploy"] == ["approved"], "NOT_REPRODUCED"
assert "tests_green" not in d["preconditions"]["deploy"]
# and: only cap.a satisfied -> deploy admitted with cap.a's preconditions; consumer cannot tell which capability authorised it
d2 = project_domain(g, {"facts": ["tests_green"]}, {"scopes": []})
print("only cap.a satisfied ->", d2["preconditions"])
print("REPRODUCED: action-name collision; graph accepts both, projection loses one contract")
