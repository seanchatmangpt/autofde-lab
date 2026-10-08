def buyer_value(auditability, operability, compliance, interoperability, assurance):
    xs = [auditability, operability, compliance, interoperability, assurance]
    if not all(0 <= x <= 1 for x in xs):  # NaN-safe: NaN fails the chained compare
        raise ValueError("dimensions must be in [0,1]")
    return sum(xs) / len(xs)
