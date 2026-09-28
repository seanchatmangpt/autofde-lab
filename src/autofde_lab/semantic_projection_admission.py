from dataclasses import dataclass
from hashlib import sha256
import json

class ProjectionRefusal(ValueError): pass

@dataclass(frozen=True)
class ProjectionClaim:
    source_subject:str
    consumer_subject:str
    source_digest:str
    consumer_digest:str
    required_terms:tuple[str,...]
    projected_terms:tuple[str,...]
    consequence_digest:str
    authority:str="NONE"

def digest(v):
    return "sha256:"+sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def exact_subject(v):
    if "@" not in v: return False
    s=v.rsplit("@",1)[1].split(":",1)[0]
    return len(s)==40 and all(c in "0123456789abcdef" for c in s)

def admit(claim):
    if not exact_subject(claim.source_subject) or not exact_subject(claim.consumer_subject):
        raise ProjectionRefusal("EXACT_SUBJECT_REQUIRED")
    if not claim.source_digest.startswith("sha256:") or not claim.consumer_digest.startswith("sha256:"):
        raise ProjectionRefusal("CONTENT_DIGEST_REQUIRED")
    if claim.authority!="NONE": raise ProjectionRefusal("AUTHORITY_WIDENING")
    if not claim.consequence_digest.startswith("sha256:"):
        raise ProjectionRefusal("CONSEQUENCE_WITNESS_REQUIRED")
    missing=sorted(set(claim.required_terms)-set(claim.projected_terms))
    if missing: raise ProjectionRefusal("SEMANTIC_LOSS:"+",".join(missing))
    canonical={"source_subject":claim.source_subject,"consumer_subject":claim.consumer_subject,
      "source_digest":claim.source_digest,"consumer_digest":claim.consumer_digest,
      "required_terms":sorted(set(claim.required_terms)),"projected_terms":sorted(set(claim.projected_terms)),
      "consequence_digest":claim.consequence_digest,"authority":"NONE"}
    claim_digest=digest(canonical)
    receipt={"claim_digest":claim_digest,"authority":"NONE","standing":"ALIVE"}
    return {**receipt,"receipt_digest":digest(receipt)}

def replay(claim,receipt):
    return admit(claim)==receipt
