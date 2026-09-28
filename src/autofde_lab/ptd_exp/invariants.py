def semantic_invariant(ds):
    return bool(ds) and len(set(ds)) == 1


def realization_nonpersistent(ds):
    return len(ds) >= 2 and len(set(ds)) == len(ds)


def exact_epoch_order(ids):
    return len(ids) >= 2 and len(ids) == len(set(ids))
