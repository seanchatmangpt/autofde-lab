def phase_budget(costs, budget):
    if budget < 0:
        raise ValueError("budget must be nonnegative")
    used = 0.0
    count = 0
    for cost in costs:
        if cost < 0:
            raise ValueError("cost must be nonnegative")
        if used + cost > budget:
            break
        used += cost
        count += 1
    return count
