"""F06: canonicalization is not total: any non-str key next to the str key 'facts'
crashes json.dumps(sort_keys=True) with TypeError (project_domain is not total over dicts).
Collision part: {1:'x'} and {'1':'x'} (no str keys) are distinct dicts with one digest."""
from _target import *
g = empty_graph()
w1, w2 = {1: "x"}, {"1": "x"}
d1 = project_domain(g, w1, {"scopes": []})["digest"]
d2 = project_domain(g, w2, {"scopes": []})["digest"]
print("distinct dicts equal?", w1 == w2, " digests equal?", d1 == d2)
assert w1 != w2 and d1 == d2, "NOT_REPRODUCED (collision)"
try:
    project_domain(g, {"facts": [], 1: "x"}, {"scopes": []})
    raise AssertionError("NOT_REPRODUCED (no crash)")
except TypeError as e:
    print("mixed-key crash:", e)
print("REPRODUCED: digest collision on {1:..} vs {'1':..}; TypeError on mixed key types")
