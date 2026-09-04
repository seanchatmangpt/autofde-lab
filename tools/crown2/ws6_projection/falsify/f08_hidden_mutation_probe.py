"""F08 (expected NOT to reproduce): probe for hidden mutation/aliasing via add_qualified,
project_domain, and returned structures. Mutating any output must not change other outputs."""
from _target import *
import copy
g0 = empty_graph()
r = QualifiedCapabilityReceipt("c", "act", "qr", "sha256:00", ("p",), ("e",), ("s",))
snap = copy.deepcopy(g0)
g1, d1 = add_qualified(g0, r)
ws = {"facts": ["p"], "nested": {"k": [1, 2]}}
au = {"scopes": ["s"]}
ws_s, au_s = copy.deepcopy(ws), copy.deepcopy(au)
dom = project_domain(g1, ws, au)
dom["preconditions"]["act"].extend(["zzz"])   # mutate output
dom["actions"].extend(["zzz"])
dom2 = project_domain(g1, ws, au)
ok = (g0 == snap and ws == ws_s and au == au_s and dom2["actions"] == ["act"]
      and dom2["preconditions"]["act"] == ["p"] and g1["capabilities"]["c"]["preconditions"] == ["p"]
      and graph_digest(g1) == d1)
print("mutation leaked:", not ok)
assert ok, "REPRODUCED: hidden mutation"
print("NOT_REPRODUCED: no hidden mutation/aliasing found")
