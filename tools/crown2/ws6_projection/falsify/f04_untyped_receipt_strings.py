"""F04: dataclass fields are unchecked; passing a str where a tuple is expected is
silently exploded into characters, changing admission semantics."""
from _target import *
r = QualifiedCapabilityReceipt("c", "act", "qr", "sha256:00", preconditions="repo_clean", scopes=())
g, _ = add_qualified(empty_graph(), r)
print("stored preconditions:", g["capabilities"]["c"]["preconditions"])
d_wrong = project_domain(g, {"facts": ["repo_clean"]}, {"scopes": []})
d_chars = project_domain(g, {"facts": list("repo_clean")}, {"scopes": []})
print("facts=['repo_clean'] ->", d_wrong["actions"], " facts=chars ->", d_chars["actions"])
assert d_wrong["actions"] == [] and d_chars["actions"] == ["act"], "NOT_REPRODUCED"
print("REPRODUCED: str receipt field accepted, precondition contract silently becomes per-character")
