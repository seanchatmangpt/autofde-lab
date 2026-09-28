from .identity import require_same_subject,require_distinct_epochs
def validate_pair(a,b):
 require_same_subject(a.subject_id,b.subject_id); require_distinct_epochs(a.epoch_id,b.epoch_id)
 if not a.admitted or not b.admitted: raise ValueError("unadmitted epoch")
 if a.semantic_digest!=b.semantic_digest: raise ValueError("semantic invariant changed")
 if a.realization_digest==b.realization_digest: raise ValueError("realization did not phase")
