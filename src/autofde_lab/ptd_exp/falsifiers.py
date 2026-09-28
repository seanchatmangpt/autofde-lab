def falsifiers(retention,ra,semantic_ok,common_mode,authority_compromised):
 out=[]
 if not semantic_ok: out.append("semantic_invariance_failed")
 if retention>=1: out.append("knowledge_did_not_depreciate")
 if ra<=1: out.append("defender_economics_failed")
 if common_mode>=1: out.append("common_mode_persisted")
 if authority_compromised: out.append("persistent_authority_compromise")
 return out
