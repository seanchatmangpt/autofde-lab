def knowledge_retention(stale,fresh):
 if fresh<=0 or stale<0: raise ValueError("invalid performance")
 return stale/fresh
def knowledge_depreciation(stale,fresh): return 1-knowledge_retention(stale,fresh)
