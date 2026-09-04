#!/usr/bin/env python3
"""
WS3 Capability Resolution — resolve(gap) over four real, ordered sources.

Search order (fixed; see rules.json, which is the machine-readable source of
truth this module loads at import time):

  1. project-local actions      (list passed in by the caller)
  2. ggen-marketplace packs     (real scan of ~/ggen-marketplace/packs/*/{pack,ggen}.toml)
  3. composable capabilities    (chains of local actions whose post/pre link, depth<=3)
  4. admitted public semantics  (real scan of <ontology_dir>/*.ttl for afl:Capability
                                 individuals with afl:capabilityName)
  5. MANUFACTURING_GAP          (sentinel — NEVER "generate code")

Every source is searched and every hit is recorded in `candidates`, even when
an earlier source already produced a selectable hit. Pareto domination is
computed over (source_rank asc, score desc, depth asc); dominated candidates
are moved to `dominated`, non-dominated ones stay in `candidates`. `selected`
is the lexicographically best non-dominated candidate. An ACTION_GAP never
routes to code generation: there is no "generation" candidate kind, and
`route_to_codegen` is a constant False on the result.

Stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(HERE, "rules.json")

with open(RULES_PATH, "r", encoding="utf-8") as _f:
    RULES: dict[str, Any] = json.load(_f)

SOURCE_RANK: dict[str, int] = {s["kind"]: s["rank"] for s in RULES["search_order"]}
MAX_CHAIN_DEPTH: int = int(RULES["max_chain_depth"])
MIN_SCORE: float = float(RULES["min_keyword_score"])
STOPWORDS: set[str] = set(RULES["stopwords"])
GAP_KIND = "MANUFACTURING_GAP"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 1}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Action:
    name: str
    preconditions: frozenset[str] = frozenset()
    postconditions: frozenset[str] = frozenset()
    cost: float = 1.0

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Action":
        return Action(
            name=d["name"],
            preconditions=frozenset(d.get("preconditions", [])),
            postconditions=frozenset(d.get("postconditions", [])),
            cost=float(d.get("cost", 1.0)),
        )


@dataclass(frozen=True)
class Gap:
    """An ACTION_GAP: transition keywords + (optional) state facts."""

    keywords: frozenset[str]
    current_facts: frozenset[str] = frozenset()
    needed_facts: frozenset[str] = frozenset()
    label: str = ""

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Gap":
        kws = set()
        for k in d.get("keywords", []):
            kws |= tokenize(k)
        return Gap(
            keywords=frozenset(kws),
            current_facts=frozenset(d.get("current_facts", [])),
            needed_facts=frozenset(d.get("needed_facts", [])),
            label=d.get("label", ""),
        )


@dataclass
class Candidate:
    kind: str  # local_action | marketplace_pack | composable_chain | ontology_capability | MANUFACTURING_GAP
    ref: str  # action name / pack path / chain "a>b>c" / ttl IRI
    score: float  # keyword coverage in [0,1]
    depth: int  # 1 for atomic, chain length for composable
    matched_keywords: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def source_rank(self) -> int:
        return SOURCE_RANK[self.kind]

    def sort_key(self) -> tuple:
        return (self.source_rank, -self.score, self.depth, self.ref)

    def dominates(self, other: "Candidate") -> bool:
        no_worse = (
            self.source_rank <= other.source_rank
            and self.score >= other.score
            and self.depth <= other.depth
        )
        strictly_better = (
            self.source_rank < other.source_rank
            or self.score > other.score
            or self.depth < other.depth
        )
        return no_worse and strictly_better


@dataclass
class CapabilityResolution:
    gap: dict[str, Any]
    candidates: list[Candidate]
    selected: Candidate
    rationale: str
    dominated: list[Candidate]
    route_to_codegen: bool = False  # invariant: ACTION_GAP never routes to generation

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["route_to_codegen"] = False
        return d


# ---------------------------------------------------------------------------
# Source 1: project-local actions
# ---------------------------------------------------------------------------


def _keyword_score(gap: Gap, text_tokens: set[str]) -> tuple[float, list[str]]:
    if not gap.keywords:
        return 0.0, []
    hit = sorted(gap.keywords & text_tokens)
    return len(hit) / len(gap.keywords), hit


def search_local_actions(gap: Gap, actions: Iterable[Action]) -> list[Candidate]:
    out = []
    for a in actions:
        toks = tokenize(a.name) | set().union(*(tokenize(p) for p in a.postconditions)) if a.postconditions else tokenize(a.name)
        score, hit = _keyword_score(gap, toks)
        applicable = a.preconditions <= gap.current_facts
        covers_needed = bool(gap.needed_facts) and gap.needed_facts <= a.postconditions and applicable
        if covers_needed:
            score = max(score, 1.0)
        elif gap.needed_facts:
            # keyword match only: does not achieve the needed transition from current_facts
            score *= 0.5
        if score >= MIN_SCORE or covers_needed:
            out.append(
                Candidate(
                    kind="local_action",
                    ref=a.name,
                    score=round(score, 4),
                    depth=1,
                    matched_keywords=hit,
                    evidence={
                        "preconditions": sorted(a.preconditions),
                        "postconditions": sorted(a.postconditions),
                        "applicable_from_current_facts": applicable,
                        "covers_needed_facts": covers_needed,
                    },
                )
            )
    return out


# ---------------------------------------------------------------------------
# Source 2: ggen-marketplace packs (real filesystem scan)
# ---------------------------------------------------------------------------

_TOML_KV_RE = re.compile(r'^\s*(name|description|version)\s*=\s*(.*)$')


def _read_manifest(path: str) -> dict[str, str]:
    """Minimal TOML reader for name/version/description (handles triple-quoted strings)."""
    fields: dict[str, str] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    for key in ("name", "version", "description"):
        m = re.search(rf'^\s*{key}\s*=\s*"""(.*?)"""', text, re.S | re.M)
        if not m:
            m = re.search(rf'^\s*{key}\s*=\s*"([^"\n]*)"', text, re.M)
        if m:
            fields[key] = m.group(1).strip()
    return fields


def scan_marketplace(packs_dir: str) -> list[dict[str, Any]]:
    packs = []
    if not os.path.isdir(packs_dir):
        return packs
    for entry in sorted(os.listdir(packs_dir)):
        pdir = os.path.join(packs_dir, entry)
        if not os.path.isdir(pdir):
            continue
        manifest = None
        for mf in ("pack.toml", "ggen.toml"):
            cand = os.path.join(pdir, mf)
            if os.path.isfile(cand):
                manifest = cand
                break
        fields = _read_manifest(manifest) if manifest else {}
        packs.append(
            {
                "dir": pdir,
                "manifest": manifest,
                "name": fields.get("name", entry),
                "version": fields.get("version", ""),
                "description": fields.get("description", ""),
            }
        )
    return packs


def search_marketplace(gap: Gap, packs_dir: str) -> list[Candidate]:
    out = []
    for p in scan_marketplace(packs_dir):
        name_toks = tokenize(p["name"])
        desc_toks = tokenize(p["description"])
        name_score, name_hit = _keyword_score(gap, name_toks)
        full_score, full_hit = _keyword_score(gap, name_toks | desc_toks)
        # Name hits are strong signal; description-only hits need >= min score.
        # score = mean(name coverage, name+description coverage): a pack named for
        # the transition outranks one merely mentioning its words in prose.
        if name_hit or full_score >= MIN_SCORE:
            score = (name_score + full_score) / 2.0
            out.append(
                Candidate(
                    kind="marketplace_pack",
                    ref=p["dir"],
                    score=round(score, 4),
                    depth=1,
                    matched_keywords=full_hit,
                    evidence={
                        "pack": p["name"],
                        "version": p["version"],
                        "manifest": p["manifest"],
                        "name_keyword_hits": name_hit,
                    },
                )
            )
    return out


# ---------------------------------------------------------------------------
# Source 3: composable capabilities (chains, depth <= 3)
# ---------------------------------------------------------------------------


def search_composable(gap: Gap, actions: Iterable[Action]) -> list[Candidate]:
    """BFS over action chains whose pre/post-conditions link, from current_facts to needed_facts."""
    acts = list(actions)
    if not gap.needed_facts:
        return []
    out = []
    frontier: list[tuple[frozenset[str], tuple[Action, ...]]] = [(gap.current_facts, ())]
    for depth in range(1, MAX_CHAIN_DEPTH + 1):
        nxt = []
        for facts, chain in frontier:
            for a in acts:
                if a in chain:
                    continue
                if not a.preconditions <= facts:
                    continue
                new_facts = facts | a.postconditions
                new_chain = chain + (a,)
                if gap.needed_facts <= new_facts:
                    if depth >= 2:  # depth-1 hits are already local_action candidates
                        out.append(
                            Candidate(
                                kind="composable_chain",
                                ref=">".join(x.name for x in new_chain),
                                score=1.0,
                                depth=depth,
                                matched_keywords=sorted(gap.needed_facts),
                                evidence={
                                    "chain": [x.name for x in new_chain],
                                    "total_cost": sum(x.cost for x in new_chain),
                                    "final_facts": sorted(new_facts),
                                },
                            )
                        )
                else:
                    nxt.append((new_facts, new_chain))
        frontier = nxt
    return out


# ---------------------------------------------------------------------------
# Source 4: admitted public semantics (real .ttl scan)
# ---------------------------------------------------------------------------

_SUBJECT_RE = re.compile(r"^\s*(\S+)\s+a\s+afl:Capability\s*;", re.M)
_PROP_RE = re.compile(r'afl:(capabilityName|capabilityPrecondition|capabilityConsequence)\s+"((?:[^"\\]|\\.)*)"')


def scan_ontology(ontology_dir: str) -> list[dict[str, Any]]:
    individuals = []
    if not os.path.isdir(ontology_dir):
        return individuals
    for fn in sorted(os.listdir(ontology_dir)):
        if not fn.endswith(".ttl"):
            continue
        path = os.path.join(ontology_dir, fn)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        for m in _SUBJECT_RE.finditer(text):
            block_end = text.find(" .", m.end())
            block = text[m.end(): block_end if block_end != -1 else len(text)]
            props = {k: v for k, v in _PROP_RE.findall(block)}
            individuals.append(
                {
                    "iri": m.group(1),
                    "file": path,
                    "line": text.count("\n", 0, m.start()) + 1,
                    "name": props.get("capabilityName", ""),
                    "precondition": props.get("capabilityPrecondition", ""),
                    "consequence": props.get("capabilityConsequence", ""),
                }
            )
    return individuals


def search_ontology(gap: Gap, ontology_dir: str) -> list[Candidate]:
    out = []
    seen = set()
    for ind in scan_ontology(ontology_dir):
        key = (ind["iri"], ind["file"])
        if key in seen:
            continue
        seen.add(key)
        toks = tokenize(ind["name"]) | tokenize(ind["iri"].split(":")[-1])
        score, hit = _keyword_score(gap, toks)
        if score >= MIN_SCORE:
            out.append(
                Candidate(
                    kind="ontology_capability",
                    ref=ind["iri"],
                    score=round(score, 4),
                    depth=1,
                    matched_keywords=hit,
                    evidence={
                        "file": ind["file"],
                        "line": ind["line"],
                        "capabilityName": ind["name"],
                        "precondition": ind["precondition"],
                        "consequence": ind["consequence"],
                    },
                )
            )
    return out


# ---------------------------------------------------------------------------
# resolve()
# ---------------------------------------------------------------------------


def pareto_split(cands: list[Candidate]) -> tuple[list[Candidate], list[Candidate]]:
    nondom, dom = [], []
    for c in cands:
        if any(o is not c and o.dominates(c) for o in cands):
            dom.append(c)
        else:
            nondom.append(c)
    nondom.sort(key=Candidate.sort_key)
    dom.sort(key=Candidate.sort_key)
    return nondom, dom


def resolve(
    gap: Gap | dict[str, Any],
    local_actions: Iterable[Action | dict[str, Any]] = (),
    marketplace_dir: str = os.path.expanduser("~/ggen-marketplace/packs"),
    ontology_dir: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "ontology"),
) -> CapabilityResolution:
    if isinstance(gap, dict):
        gap = Gap.from_dict(gap)
    actions = [a if isinstance(a, Action) else Action.from_dict(a) for a in local_actions]

    all_cands: list[Candidate] = []
    all_cands += search_local_actions(gap, actions)
    all_cands += search_marketplace(gap, marketplace_dir)
    all_cands += search_composable(gap, actions)
    all_cands += search_ontology(gap, ontology_dir)

    nondom, dom = pareto_split(all_cands)
    counts = {}
    for c in all_cands:
        counts[c.kind] = counts.get(c.kind, 0) + 1

    if nondom:
        sel = nondom[0]
        rationale = (
            f"selected {sel.kind} {sel.ref!r} (rank={sel.source_rank}, score={sel.score}, depth={sel.depth}); "
            f"{len(all_cands)} candidates over sources {counts}; {len(nondom)} non-dominated retained, "
            f"{len(dom)} dominated; code generation not a candidate kind (route_to_codegen=False)"
        )
    else:
        sel = Candidate(
            kind=GAP_KIND,
            ref=GAP_KIND,
            score=0.0,
            depth=0,
            matched_keywords=[],
            evidence={
                "searched": [s["kind"] for s in RULES["search_order"] if s["kind"] != GAP_KIND],
                "marketplace_dir": marketplace_dir,
                "ontology_dir": ontology_dir,
                "local_action_count": len(actions),
            },
        )
        nondom = [sel]
        rationale = (
            f"no candidate in any of {len(SOURCE_RANK) - 1} sources for keywords {sorted(gap.keywords)}; "
            f"this is a MANUFACTURING_GAP to be scheduled as manufacturing work (pack/ontology extension), "
            f"NOT routed to code generation (route_to_codegen=False)"
        )

    return CapabilityResolution(
        gap={"keywords": sorted(gap.keywords), "current_facts": sorted(gap.current_facts),
             "needed_facts": sorted(gap.needed_facts), "label": gap.label},
        candidates=nondom,
        selected=sel,
        rationale=rationale,
        dominated=dom,
        route_to_codegen=False,
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: resolve.py '<gap-json>' [actions-json-file] [marketplace_dir] [ontology_dir]")
        return 2
    gap = json.loads(argv[1])
    actions = []
    if len(argv) > 2 and argv[2]:
        with open(argv[2], "r", encoding="utf-8") as f:
            actions = json.load(f)
    kw = {}
    if len(argv) > 3:
        kw["marketplace_dir"] = argv[3]
    if len(argv) > 4:
        kw["ontology_dir"] = argv[4]
    res = resolve(gap, actions, **kw)
    print(json.dumps(res.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
