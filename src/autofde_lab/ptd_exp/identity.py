import hashlib,json
def canonical_digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def require_same_subject(a,b):
 if not a or a!=b: raise ValueError("PTD exact-subject mismatch")
def require_distinct_epochs(a,b):
 if not a or not b or a==b: raise ValueError("PTD requires distinct epochs")
