"""Constrained covering arrays over the plan-scenario factor space (pairwise and order-3).

Generator preference: pypict (if importable) -> allpairspy -> greedy in-file. Whatever generates, the
result is checked by exhaustive tuple coverage against the constrained space (`uncovered`)."""
from __future__ import annotations

import itertools

FACTORS = {
    "stage": [1, 2], "part": [0, 1], "tag": [0, 1], "attest_ok": [0, 1], "providers": [1, 2],
    "blacklist": [0, 1], "expired": [0, 1], "filtered": [0, 1], "unapproved": [0, 1],
    "rate_gte_client": [0, 1], "territory_out": [0, 1], "nte_below": [0, 1],
}
NAMES = list(FACTORS)

# (python predicate over a row dict, PICT constraint text); N/A values are pinned to a canonical one.
CONSTRAINTS = [
    (lambda r: r["stage"] == 2 or (r["tag"] == 0 and r["attest_ok"] == 1 and r["nte_below"] == 0),
     "IF [stage]=1 THEN [tag]=0 AND [attest_ok]=1 AND [nte_below]=0;"),
    (lambda r: r["part"] == 1 or r["tag"] == 0, "IF [part]=0 THEN [tag]=0;"),
    (lambda r: not (r["blacklist"] == 1 and r["providers"] == 1 and r["stage"] == 2),
     "IF [blacklist]=1 AND [providers]=1 THEN [stage]=1;"),
]


def valid(row: dict) -> bool:
    return all(p(row) for p, _ in CONSTRAINTS)


def space() -> list[tuple]:
    out = []
    for vals in itertools.product(*FACTORS.values()):
        if valid(dict(zip(NAMES, vals))):
            out.append(vals)
    return out


def required_tuples(rows, t):
    """Every t-way (factor-subset, values) tuple present in at least one valid row."""
    req = set()
    for row in rows:
        for idx in itertools.combinations(range(len(NAMES)), t):
            req.add((idx, tuple(row[i] for i in idx)))
    return req


def covered_tuples(rows, t):
    return required_tuples(rows, t)


def uncovered(array, t, sp=None):
    sp = sp if sp is not None else space()
    return required_tuples(sp, t) - required_tuples(array, t)


def greedy(t, sp=None):
    sp = sp if sp is not None else space()
    need = required_tuples(sp, t)
    combos = list(itertools.combinations(range(len(NAMES)), t))
    out = []
    while need:
        best, best_gain = None, -1
        for row in sp:
            gain = sum(((idx, tuple(row[i] for i in idx)) in need) for idx in combos)
            if gain > best_gain:
                best, best_gain = row, gain
        out.append(best)
        need -= {(idx, tuple(best[i] for i in idx)) for idx in combos}
    return out


def _pypict(t):
    from pypict import cmd  # type: ignore
    model = "\n".join(f"{k}: {', '.join(map(str, v))}" for k, v in FACTORS.items())
    model += "\n" + "\n".join(c for _, c in CONSTRAINTS) + "\n"
    rows = cmd.from_model(model, order=t)
    return [tuple(int(x) for x in r) for r in rows]


def _allpairs(t):
    from allpairspy import AllPairs  # type: ignore
    ap = AllPairs(list(FACTORS.values()), filter_func=_prefix_ok, n=t)
    return [tuple(r) for r in ap]


def _prefix_ok(row):
    """Reject a partial row only if no valid completion exists."""
    k = len(row)
    for rest in itertools.product(*[FACTORS[n] for n in NAMES[k:]]):
        if valid(dict(zip(NAMES, tuple(row) + rest))):
            return True
    return False


def generate(t):
    """-> (rows as tuples, generator name). Falls through to the next generator on any failure
    or on incomplete coverage of the constrained space."""
    sp = space()
    for name, fn in (("pypict", _pypict), ("allpairspy", _allpairs)):
        try:
            rows = fn(t)
        except Exception:
            continue
        if rows and all(valid(dict(zip(NAMES, r))) for r in rows) and not uncovered(rows, t, sp):
            return rows, name
    return greedy(t, sp), "greedy"


if __name__ == "__main__":
    sp = space()
    print(f"factors={len(NAMES)} valid_rows={len(sp)} of {2 ** len(NAMES)}")
    for label, t in (("pairwise", 2), ("order-3", 3)):
        rows, gen = generate(t)
        print(f"{label}: size={len(rows)} generator={gen} uncovered={len(uncovered(rows, t, sp))}")
