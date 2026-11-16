"""Independent PDDL-subset interpreter + fail-closed durative-plan state machine (L7)."""
import hashlib, json, re

GENESIS = "0" * 64
ACTOR_CLASS = {
    "activate-entity": "super_admin", "certify-provider-alignment": "coordinator",
    "triage-and-route-work-order": "coordinator", "auto-dispatch-aligned-provider": "system",
    "execute-site-visit": "provider", "commit-external-client-attendance": "system",
    "run-ai-vision-closeout-gate": "system", "emit-and-deliver-client-invoice": "system",
    "settle-provider-ap-payout": "ap_manager", "til": "environment",
}


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def num(x):
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


# ---------------- s-expression parsing ----------------
def sexp(text):
    text = re.sub(r";[^\n]*", "", text).lower()
    toks = re.findall(r"\(|\)|[^\s()]+", text)
    pos = 0

    def rd():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == "(":
            out = []
            while toks[pos] != ")":
                out.append(rd())
            pos += 1
            return out
        return t
    r = rd()
    return r


def typed(lst):
    """['a','b','-','t','c'] -> [(a,t),(b,t),(c,object)]"""
    out, pend, i = [], [], 0
    while i < len(lst):
        if lst[i] == "-":
            out += [(n, lst[i + 1]) for n in pend]; pend = []; i += 2
        else:
            pend.append(lst[i]); i += 1
    out += [(n, "object") for n in pend]
    return out


def isnum(s):
    try:
        float(s); return True
    except (ValueError, TypeError):
        return False


class Domain:
    def __init__(self, text):
        d = sexp(text)
        self.parent = {"object": None}
        self.constants = {}
        self.actions = {}
        self.fluent_names = set()
        for sec in d[2:]:
            k = sec[0]
            if k == ":types":
                for n, p in typed(sec[1:]):
                    self.parent[n] = p
            elif k == ":constants":
                self.constants = dict(typed(sec[1:]))
            elif k == ":functions":
                self.fluent_names = {x[0] for x in sec[1:] if isinstance(x, list)}
            elif k == ":durative-action":
                self.actions[sec[1]] = self._action(sec)
        self.sha = None

    def _action(self, sec):
        a = {"name": sec[1]}
        i = 2
        while i < len(sec):
            a[sec[i][1:]] = sec[i + 1]; i += 2
        a["params"] = [(n, t) for n, t in typed(a["parameters"])]
        dur = a["duration"]  # (= ?duration expr)
        a["dur_expr"] = dur[2] if dur[0] == "=" else dur[0]
        a["cond"] = self._timed(a["condition"], "c")
        a["eff"] = self._timed(a["effect"], "e")
        return a

    def _timed(self, x, kind):
        out = []
        if x == [] or x is None:
            return out
        if x[0] == "and":
            for y in x[1:]:
                out += self._timed(y, kind)
        elif x[0] == "at":
            out.append((x[1], x[2]))
        elif x[0] == "over":
            out.append(("over", x[2]))
        else:
            raise ValueError(f"untimed {kind}: {x}")
        return out

    def is_a(self, t, anc):
        while t is not None:
            if t == anc:
                return True
            t = self.parent.get(t)
        return False


class Problem:
    def __init__(self, text):
        p = sexp(text)
        self.objects = {}
        self.facts = set()
        self.fluents = {}
        self.til = []
        self.goal = None
        for sec in p[2:]:
            k = sec[0]
            if k == ":objects":
                self.objects = dict(typed(sec[1:]))
            elif k == ":init":
                for e in sec[1:]:
                    if e[0] == "=":
                        self.fluents[tuple(e[1])] = num(float(e[2]))
                    elif e[0] == "at":
                        self.til.append((float(e[1]), e[2]))
                    else:
                        self.facts.add(tuple(e))
            elif k == ":goal":
                self.goal = sec[1]
        self.til.sort(key=lambda x: x[0])


class Refusal(Exception):
    def __init__(self, term):
        self.term = term


# ---------------- evaluation ----------------
def term(x, b, st):
    if isinstance(x, list):
        op = x[0]
        if op in ("+", "-", "*", "/"):
            v = [term(y, b, st) for y in x[1:]]
            if op == "-" and len(v) == 1:
                return -v[0]
            r = v[0]
            for y in v[1:]:
                r = r + y if op == "+" else r - y if op == "-" else r * y if op == "*" else r / y
            return num(r)
        key = tuple([op] + [b.get(a, a) for a in x[1:]])
        if key not in st.fluents:
            raise Refusal(f"undefined-fluent:{fmt(key)}")
        return st.fluents[key]
    if x.startswith("?"):
        return b[x]
    if isnum(x):
        return num(float(x))
    return x


def fmt(t):
    return "(" + " ".join(map(str, t)) + ")"


def holds(c, b, st):
    op = c[0]
    if op == "and":
        return all(holds(y, b, st) for y in c[1:])
    if op == "or":
        return any(holds(y, b, st) for y in c[1:])
    if op == "not":
        return not holds(c[1], b, st)
    if op == "imply":
        return (not holds(c[1], b, st)) or holds(c[2], b, st)
    if op in ("=", "<", ">", "<=", ">="):
        x, y = term(c[1], b, st), term(c[2], b, st)
        return {"=": x == y, "<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y}[op]
    return tuple([op] + [b.get(a, a) for a in c[1:]]) in st.facts


def ground(c, b):
    """grounded textual form of a condition for broken_term."""
    if isinstance(c, list):
        return "(" + " ".join(ground(y, b) for y in c) + ")"
    return b.get(c, c)


def unmet(c, b, st):
    """Return the minimal unmet atomic sub-condition (grounded string) or None."""
    if holds(c, b, st):
        return None
    if c[0] == "and":
        for y in c[1:]:
            u = unmet(y, b, st)
            if u:
                return u
    return ground(c, b)


class State:
    def __init__(self, facts, fluents):
        self.facts = set(facts)
        self.fluents = dict(fluents)

    def snapshot(self):
        return (frozenset(self.facts), dict(self.fluents))

    def hash(self):
        return sha(canon({"facts": sorted(map(list, self.facts)),
                          "fluents": sorted([list(k), v] for k, v in self.fluents.items())}))


def diff(before, after):
    bf, bl = before
    af, al = after.facts, after.fluents
    return {"added": sorted(map(list, af - bf)), "removed": sorted(map(list, bf - af)),
            "fluents": sorted([list(k), bl.get(k), al[k]] for k in al if bl.get(k) != al[k])}


def merge(d1, d2):
    """compose sequential own-effect deltas"""
    added = {tuple(x) for x in d1["added"]}; removed = {tuple(x) for x in d1["removed"]}
    for x in map(tuple, d2["added"]):
        removed.discard(x); added.add(x)
    for x in map(tuple, d2["removed"]):
        added.discard(x); removed.add(x)
    fl = {tuple(k): [o, n] for k, o, n in d1["fluents"]}
    for k, o, n in d2["fluents"]:
        k = tuple(k)
        fl[k] = [fl[k][0] if k in fl else o, n]
    return {"added": sorted(map(list, added)), "removed": sorted(map(list, removed)),
            "fluents": sorted([list(k), o, n] for k, (o, n) in fl.items() if o != n)}


EMPTY = {"added": [], "removed": [], "fluents": []}


def apply_delta(st, d):
    for r in d["removed"]:
        st.facts.discard(tuple(r))
    for a in d["added"]:
        st.facts.add(tuple(a))
    for k, o, n in d["fluents"]:
        st.fluents[tuple(k)] = n


def apply_effect(e, b, st, adds_dels):
    op = e[0]
    if op == "and":
        for y in e[1:]:
            apply_effect(y, b, st, adds_dels)
    elif op == "not":
        st.facts.discard(tuple([e[1][0]] + [b.get(a, a) for a in e[1][1:]]))
    elif op == "when":
        if holds(e[1], b, st):
            apply_effect(e[2], b, st, adds_dels)
    elif op in ("assign", "increase", "decrease"):
        f = e[1]
        key = tuple([f[0]] + [b.get(a, a) for a in f[1:]])
        v = term(e[2], b, st)
        if op == "assign":
            st.fluents[key] = v
        else:
            if key not in st.fluents:
                raise Refusal(f"undefined-fluent:{fmt(key)}")
            st.fluents[key] = num(st.fluents[key] + (v if op == "increase" else -v))
    else:
        st.facts.add(tuple([op] + [b.get(a, a) for a in e[1:]]))


# ---------------- plan ----------------
PLAN_RE = re.compile(r"^\s*([\d.]+)\s*:\s*\((.*)\)\s*(?:\[([\d.]+)\])?\s*$")


def parse_plan(text):
    out = []
    for ln in text.splitlines():
        ln = ln.split(";", 1)[0].strip().lower()
        if not ln:
            continue
        m = PLAN_RE.match(ln)
        if not m:
            raise ValueError(f"bad plan line: {ln!r}")
        toks = m.group(2).split()
        out.append({"t": num(float(m.group(1))), "name": toks[0], "args": toks[1:],
                    "dur": num(float(m.group(3))) if m.group(3) else None})
    return out


class Executor:
    def __init__(self, domain_text, problem_text):
        self.dom = Domain(domain_text)
        self.prob = Problem(problem_text)
        self.dsha, self.psha = sha(domain_text), sha(problem_text)
        self.st = State(self.prob.facts, self.prob.fluents)
        self.receipts = []
        self.prev = GENESIS
        self.refused = None

    # receipt construction -------------------------------------------------
    def emit(self, label, name, args, before_hash, delta, standing, term_, t, overlap):
        body = {
            "seq": len(self.receipts), "time": t,
            "identity": {"digest": sha(self.dsha + self.psha + label + before_hash),
                         "domain_sha256": self.dsha, "problem_sha256": self.psha,
                         "action": label, "state_before": before_hash},
            "authority": {"action": name, "actor_class": ACTOR_CLASS.get(name, "unclassified")},
            "consequence": {"delta": delta, "state_after": self.st.hash(), "overlap": overlap},
            "standing": {"value": standing, "broken_term": term_},
        }
        this = sha(self.prev + canon(body))
        r = dict(body); r["replay"] = {"prev": self.prev, "this": this}
        self.receipts.append(r)
        self.prev = this

    # run -------------------------------------------------------------------
    def run(self, plan):
        dom = self.dom
        events = []  # (time, order(0=end,1=til,2=start), idx, kind, payload)
        for i, s in enumerate(plan):
            events.append((s["t"], 2, i, "start", s))
        for j, (t, e) in enumerate(self.prob.til):
            events.append((t, 1, j, "til", e))
        active = {}  # idx -> info
        pending = sorted(events, key=lambda e: (e[0], e[1], e[2]))
        try:
            while pending:
                pending.sort(key=lambda e: (e[0], e[1], e[2]))
                if all(e[3] == "til" for e in pending) and not active:
                    break  # plan exhausted; later TILs are outside the executed horizon
                t, order, idx, kind, pl = pending.pop(0)
                if kind == "til":
                    bh, snap = self.st.hash(), self.st.snapshot()
                    apply_effect(pl, {}, self.st, None)
                    self._invariants(active, t)
                    self.emit(f"(til {fmt([t])})", "til", [], bh, diff(snap, self.st),
                              "PASS", None, t, len(active) > 0)
                elif kind == "start":
                    self._start(pl, idx, t, active, pending)
                else:
                    self._end(idx, t, active)
        except Refusal as r:
            self.refused = r.term
        return self

    def _bind(self, s, a):
        if s["name"] not in self.dom.actions:
            raise Refusal(f"unknown-action:{s['name']}")
        if len(s["args"]) != len(a["params"]):
            raise Refusal(f"arity:{s['name']}")
        b = {}
        for (v, ty), o in zip(a["params"], s["args"]):
            ot = self.prob.objects.get(o) or self.dom.constants.get(o)
            if ot is None:
                raise Refusal(f"unknown-object:{o}")
            if not self.dom.is_a(ot, ty):
                raise Refusal(f"type-mismatch:{o}:{ot}!<:{ty}")
            b[v] = o
        return b

    def _fail(self, s, label, term_, bh, t, active):
        # emit REFUSED receipt (chained), then abort
        self.emit(label, s["name"], s["args"], bh, EMPTY, "REFUSED", term_, t, len(active) > 0)
        raise Refusal(term_)

    def _start(self, s, idx, t, active, pending):
        a = self.dom.actions.get(s["name"])
        label = fmt([s["name"]] + s["args"])
        bh, snap = self.st.hash(), self.st.snapshot()
        try:
            if a is None:
                raise Refusal(f"unknown-action:{s['name']}")
            b = self._bind(s, a)
            for when, c in a["cond"]:
                if when in ("start", "over"):
                    u = unmet(c, b, self.st)
                    if u:
                        raise Refusal(f"precondition:{'at-start' if when == 'start' else 'over-all'}:{u}")
            d = term(a["dur_expr"], b, self.st)
            if s["dur"] is not None and s["dur"] != d:
                raise Refusal(f"duration-mismatch:plan={s['dur']}:domain={d}")
        except Refusal as r:
            self._fail(s, label, r.term, bh, t, active)
        overlap = len(active) > 0
        for o in active.values():
            o["overlap"] = True
        for when, e in a["eff"]:
            if when == "start":
                apply_effect(e, b, self.st, None)
        d1 = diff(snap, self.st)
        active[idx] = {"s": s, "a": a, "b": b, "label": label, "bh": bh, "d": d1, "overlap": overlap,
                       "end": num(t + d)}
        pending.append((num(t + d), 0, idx, "end", None))
        self._invariants(active, t)

    def _invariants(self, active, t):
        for info in active.values():
            for when, c in info["a"]["cond"]:
                if when == "over":
                    u = unmet(c, info["b"], self.st)
                    if u:
                        self._fail(info["s"], info["label"], f"invariant:over-all:{u}", info["bh"], t, {})

    def _end(self, idx, t, active):
        info = active[idx]
        a, b = info["a"], info["b"]
        for when, c in a["cond"]:
            if when == "end":
                u = unmet(c, b, self.st)
                if u:
                    self._fail(info["s"], info["label"], f"precondition:at-end:{u}", info["bh"], t, {})
        snap = self.st.snapshot()
        for when, e in a["eff"]:
            if when == "end":
                apply_effect(e, b, self.st, None)
        d = merge(info["d"], diff(snap, self.st))
        del active[idx]
        self._invariants(active, t)
        self.emit(info["label"], a["name"], info["s"]["args"], info["bh"], d, "PASS", None, t,
                  info["overlap"])

    # goal / ledger ------------------------------------------------------------
    def goal_ok(self):
        return holds(self.prob.goal, {}, self.st)

    def ledger(self):
        ar = sum(v for k, v in self.st.fluents.items() if k[0] == "invoice-amount")
        ap = sum(v for k, v in self.st.fluents.items() if k[0] == "ap-payout-amount")
        return {"AR": ar, "AP": ap, "margin": ar - ap}


def write_receipts(path, receipts):
    with open(path, "w", newline="\n") as f:
        for r in receipts:
            f.write(canon(r) + "\n")
