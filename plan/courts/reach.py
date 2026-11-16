#!/usr/bin/env python3
"""STRIPS-RELAXED grounded forward-reachability checker (fallback solver for L8 courts).

RELAXATION, NOT A PLANNER: delete effects ignored, durations/ordering ignored, numeric
effects ignored. Numeric preconditions are evaluated against init fluent values (static).
Negative preconditions `(not p)` hold iff p is absent from init or some action deletes p
(over-approximation). Timed-initial-literals ignored. Therefore:
  UNSOLVABLE here  => truly unsolvable (relaxation is sound for unreachability).
  SOLVABLE here    => only "relaxed-reachable"; NOT a plan.
Exit: 0 relaxed-reachable, 2 unreachable (UNSOLVABLE), 3 parse/usage error.
"""
import sys, itertools, re

def tok(s):
    s = re.sub(r";[^\n]*", "", s)
    return s.replace("(", " ( ").replace(")", " ) ").split()

def parse(ts):
    st = [[]]
    for t in ts:
        if t == "(": st.append([])
        elif t == ")":
            x = st.pop(); st[-1].append(x)
        else: st[-1].append(t.lower())
    return st[0][0]

def typed(lst):
    out, pend = [], []
    i = 0
    while i < len(lst):
        if lst[i] == "-":
            out += [(n, lst[i + 1]) for n in pend]; pend = []; i += 2
        else: pend.append(lst[i]); i += 1
    out += [(n, "object") for n in pend]
    return out

def section(d, key):
    return [x for x in d if isinstance(x, list) and x and x[0] == key]

class Dom:
    def __init__(s, dsrc, psrc):
        d = parse(tok(open(dsrc).read())); p = parse(tok(open(psrc).read()))
        s.parent = {}
        for sec in section(d, ":types"):
            for n, t in typed(sec[1:]): s.parent[n] = t
        s.objs = {}
        for sec in section(d, ":constants") + section(p, ":objects"):
            for n, t in typed(sec[1:]): s.objs[n] = t
        s.actions = []
        for sec in section(d, ":durative-action") + section(d, ":action"):
            a = {"name": sec[1]}
            i = 2
            while i < len(sec):
                a[sec[i]] = sec[i + 1]; i += 2
            a["params"] = typed(a[":parameters"])
            s.actions.append(a)
        s.init, s.fl = set(), {}
        for sec in section(p, ":init"):
            for f in sec[1:]:
                if f[0] == "=":
                    s.fl[s.key(f[1])] = float(f[2])
                elif f[0] == "at": pass  # TIL ignored (relaxation)
                else: s.init.add(s.key(f))
        g = section(p, ":goal")[0][1]
        s.goal = [s.key(x) for x in (g[1:] if g[0] == "and" else [g])]
    def isa(s, t, anc):
        while t:
            if t == anc: return True
            t = s.parent.get(t)
        return anc == "object"
    @staticmethod
    def key(f): return tuple(f)

def sub(f, b):
    if isinstance(f, list): return [sub(x, b) for x in f]
    return b.get(f, f)

def flat(c, out):
    """flatten condition to list of (kind, tree); time wrappers stripped."""
    if c[0] == "and":
        for x in c[1:]: flat(x, out)
    elif c[0] in ("at", "over"):
        flat(c[2], out)
    else: out.append(c)

def num(e, D):
    if isinstance(e, str):
        try: return float(e)
        except ValueError: return None
    if e[0] in ("+", "-", "*", "/"):
        v = [num(x, D) for x in e[1:]]
        if None in v: return None
        r = v[0]
        for x in v[1:]:
            r = r + x if e[0] == "+" else r - x if e[0] == "-" else r * x if e[0] == "*" else r / x
        return r
    return D.fl.get(tuple(e))

def holds(c, D, facts, dels):
    h = c[0]
    if h == "and": return all(holds(x, D, facts, dels) for x in c[1:])
    if h == "or": return any(holds(x, D, facts, dels) for x in c[1:])
    if h in ("at", "over"): return holds(c[2], D, facts, dels)
    if h == "not":
        x = c[1]
        if x[0] in ("=", "<", ">", "<=", ">="): return not holds(x, D, facts, dels)
        t = tuple(x)
        return t not in D.init or t in dels
    if h in ("=", "<", ">", "<=", ">="):
        a, b = num(c[1], D), num(c[2], D)
        if a is None or b is None: return False
        return {"=": a == b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[h]
    return tuple(c) in facts

def effs(e, add, dele):
    if e[0] == "and":
        for x in e[1:]: effs(x, add, dele)
    elif e[0] == "at": effs(e[2], add, dele)
    elif e[0] == "not": dele.add(tuple(e[1]))
    elif e[0] in ("assign", "increase", "decrease"): pass
    else: add.add(tuple(e))

def solve(dsrc, psrc):
    D = Dom(dsrc, psrc)
    ground = []
    for a in D.actions:
        pools = [[n for n, t in D.objs.items() if D.isa(t, pt)] for _, pt in a["params"]]
        for combo in itertools.product(*pools):
            b = {a["params"][i][0]: combo[i] for i in range(len(combo))}
            cond = sub(a.get(":condition", ["and"]), b)
            add, dele = set(), set()
            effs(sub(a[":effect"], b), add, dele)
            ground.append((a["name"], combo, cond, add, dele))
    dels = set().union(*[g[4] for g in ground]) if ground else set()
    facts, fired = set(D.init), set()
    ch = True
    while ch:
        ch = False
        for i, (n, c, cond, add, _) in enumerate(ground):
            if i in fired or not holds(cond, D, facts, dels): continue
            fired.add(i); ch = True; facts |= add
    miss = [g for g in D.goal if g not in facts]
    return (not miss), miss, len(ground), len(fired)

if __name__ == "__main__":
    if len(sys.argv) != 3: print("usage: reach.py domain problem"); sys.exit(3)
    try: ok, miss, ng, nf = solve(*sys.argv[1:])
    except Exception as e: print("ERROR", repr(e)); sys.exit(3)
    print(f"RELAXED-REACHABLE ground={ng} fired={nf}" if ok else
          f"UNSOLVABLE(relaxation) unreachable_goals={miss} ground={ng} fired={nf}")
    sys.exit(0 if ok else 2)
