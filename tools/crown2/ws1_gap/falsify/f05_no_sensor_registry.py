#!/usr/bin/env python3
"""F05: real beam4pm has no sensor registry at all (sensors=[]). The canonical
'disallowed consequential' fixture with sensors removed collapses to OBSERVATION_GAP:
'unmodelled' is conflated with 'missing'. Correct (per the fixture): AUTHORITY_GAP."""
import json, os
from _common import HERE, run
fx = json.load(open(os.path.join(HERE, "..", "fixtures", "canonical_disallowed_consequential.json")))
exp = fx.pop("expected_gap_type"); fx["sensors"] = []
rec = run("f05_no_sensor_registry", fx, exp, "sensors=[] => every supplied transition becomes OBSERVATION_GAP")
assert rec["reproduces"], "did not reproduce"
