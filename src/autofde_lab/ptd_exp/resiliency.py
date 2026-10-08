TECHNIQUES = {
    "diversity",
    "dynamic_positioning",
    "non_persistence",
    "unpredictability",
    "adaptive_response",
    "realignment",
    "segmentation",
    "substantiated_integrity",
}


def coverage(observed):
    return len(observed & TECHNIQUES) / len(TECHNIQUES)


def unknown_techniques(observed):
    return observed - TECHNIQUES


def resiliency_report(observed):
    """Technique coverage over what the experiment *declared*, or ``None`` when nothing was declared.

    ``not_declared`` is absence of a claim, not evidence a technique is absent.
    """
    if observed is None:
        return None
    seen = set(observed)
    return {
        "coverage": coverage(seen),
        "declared": sorted(seen & TECHNIQUES),
        "not_declared": sorted(TECHNIQUES - seen),
        "unknown_techniques": sorted(unknown_techniques(seen)),
    }
