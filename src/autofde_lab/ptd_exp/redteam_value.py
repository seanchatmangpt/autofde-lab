def redteam_value(recon_reuse, predictability, authority_reuse, common_mode):
    xs = [recon_reuse, predictability, authority_reuse, common_mode]
    if not all(0 <= x <= 1 for x in xs):  # NaN-safe: NaN fails the chained compare
        raise ValueError("dimensions must be in [0,1]")
    return sum(xs) / len(xs)
