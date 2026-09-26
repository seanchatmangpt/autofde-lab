from hashlib import sha256
import json
def receipt(subject, terms):
    payload={"subject":subject,"terms":sorted(terms),"authority":"NONE"}
    raw=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    return "sha256:"+sha256(raw).hexdigest()
def replay(subject, terms, expected):
    return receipt(subject,terms)==expected
