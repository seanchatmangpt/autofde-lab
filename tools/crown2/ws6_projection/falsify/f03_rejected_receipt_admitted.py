"""F03: nothing in the receipt or add_qualified encodes a qualification verdict.
A receipt whose qualification_run_id / evidence says REJECTED is admitted identically."""
from _target import *
rej = QualifiedCapabilityReceipt("cap.rm", "rm_rf", "qr-REJECTED-0007", "sha256:REJECTED", (), (), ())
g, _ = add_qualified(empty_graph(), rej)
d = project_domain(g, {"facts": []}, {"scopes": []})
print("actions:", d["actions"])
assert d["actions"] == ["rm_rf"], "NOT_REPRODUCED"
import dataclasses
print("receipt fields:", [f.name for f in dataclasses.fields(QualifiedCapabilityReceipt)])
assert not any(f.name in ("status", "verdict", "outcome") for f in dataclasses.fields(QualifiedCapabilityReceipt))
print("REPRODUCED: no verdict field/check; a rejected run's receipt enters the graph and the domain")
