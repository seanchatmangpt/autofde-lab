"""F07: world_state.facts / authority.scopes accept any iterable: a str is iterated per char,
a dict contributes its keys. A string-valued 'facts' admits actions by single letters."""
from _target import *
g, _ = add_qualified(empty_graph(), QualifiedCapabilityReceipt("c", "act", "qr", "sha256:00", ("a",), (), ("s",)))
d = project_domain(g, {"facts": "banana"}, {"scopes": {"s": False}})
print("actions:", d["actions"])
assert d["actions"] == ["act"], "NOT_REPRODUCED"
print("REPRODUCED: facts='banana' + scopes={'s':False} admits action requiring fact 'a' and scope 's'")
