TECHNIQUES={"diversity","dynamic_positioning","non_persistence","unpredictability","adaptive_response","realignment","segmentation","substantiated_integrity"}
def coverage(observed): return len(observed&TECHNIQUES)/len(TECHNIQUES)
def unknown_techniques(observed): return observed-TECHNIQUES
