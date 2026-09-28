def common_mode_persistence(previous,current): return 0. if not previous else len(previous&current)/len(previous)
def reject_persistent_critical(critical,previous,current): return sorted(critical&previous&current)
