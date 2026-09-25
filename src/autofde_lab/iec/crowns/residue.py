"""IEC-011: the LLM residue census -- the *Find* step in front of the retirement ledger.

`retirement.py` retires a reasoning class only through a held-out C3 court. It never
says *which* reasoning classes exist. This module does: for one exact commit it reads
every Python blob from the git object database (never the working tree, like
`census.census`) and lists each place the code constructs an LLM reasoning program
or an LLM client. Those are the edges the retirement ledger exists to delete.

    LLMResidue(E) = #{static LLM invocation edges at commit E}

Rules, each a statement the source itself commits to:

1. An **edge** is a call whose callee resolves, through this file's own `import`
   statements (`ast`, not regex), to a name in `INVOCATION_APIS`. An alias or a
   `from dspy import Predict` resolves; an unresolvable callee is not guessed.
2. An **import is not an edge.** A file that imports a provider but makes no
   resolved invocation is listed as `import_only` -- `absence-is-not-evidence.md`'s
   "zero DSPy calls != DSPy provenance", applied in the other direction.
3. A provider-rooted call that is not in `INVOCATION_APIS` is counted per file in
   `other_provider_calls`, never silently dropped: it is what this rule table
   cannot yet classify.
4. A `dspy.Signature` subclass is a **declared reasoning class**: a typed question
   the code pays an LLM to answer.
5. An edge's residue `kind` and its retirement-ledger `class` are `UNKNOWN` unless
   the producer declares them with a `# llm-residue: kind=<k> class=<RC-...>`
   comment on the call line or the line above. Identity is explicit or it does
   not exist (`no-dual-bookkeeping.md`); a signature name that happens to match a
   ledger identity is not a join.

What this census cannot say, and therefore does not:

* **Reachability.** Whether an edge is reachable on a production path is not
  observable from a static read, so `LLMDependencyRatio` (LLM edges over all
  reachable executable edges) has no denominator: it is reported as
  `UNREPRESENTABLE:NO_REACHABILITY_OBSERVATION`, never as a number.
* **Retirement.** `residue_delta` reports edges *removed* between two commits. A
  removed edge is not a retired one -- deleting a feature also removes its LLM
  call. Only `retirement.ledger_entry` over a held-out C3 court retires anything.
* **Frontier value.** The frontier ranks candidate recurrence by the one factor
  observable here (call sites sharing a signature expression). Cost, reuse and
  formalizability stay `UNKNOWN`; they are not zero.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from .census import _ls_tree, iter_blobs
from .corpus import RepositorySubject, observe_checkout, verify_checkout
from .model import FactStanding, canonical_json, content_id

__all__ = [
    "INVOCATION_APIS",
    "LDR_UNREPRESENTABLE",
    "RESIDUE_EXTRACTOR",
    "RESIDUE_KINDS",
    "RESIDUE_VERSION",
    "ResidueEdge",
    "residue_census",
    "residue_delta",
]

RESIDUE_EXTRACTOR = "autofde_lab.iec.crowns.residue"
RESIDUE_VERSION = "1"
LDR_UNREPRESENTABLE = "UNREPRESENTABLE:NO_REACHABILITY_OBSERVATION"

LLM_PROVIDERS = ("anthropic", "dspy", "litellm", "ollama", "openai")

# Qualified callee -> role. `program`: an LLM reasoning program over a signature;
# `client`: an LLM client or LM handle. Anything provider-rooted and absent here is
# rule 3's `other_provider_calls`.
INVOCATION_APIS: Mapping[str, str] = {
    "dspy.Predict": "program",
    "dspy.ChainOfThought": "program",
    "dspy.ChainOfThoughtWithHint": "program",
    "dspy.ReAct": "program",
    "dspy.ProgramOfThought": "program",
    "dspy.MultiChainComparison": "program",
    "dspy.CodeAct": "program",
    "dspy.Refine": "program",
    "dspy.BestOfN": "program",
    "dspy.LM": "client",
    "anthropic.Anthropic": "client",
    "anthropic.AsyncAnthropic": "client",
    "openai.OpenAI": "client",
    "openai.AsyncOpenAI": "client",
    "litellm.completion": "client",
    "litellm.acompletion": "client",
    "ollama.chat": "client",
    "ollama.generate": "client",
}

# Residue kind -> the machinery that retires it. A producer's `kind=` must name one
# of these; the mapping is where a retirement attempt starts, not evidence of one.
RESIDUE_KINDS: Mapping[str, str] = {
    "generation": "ggen",
    "classification": "ontology + SPARQL/Datalog",
    "planning": "HDDL/PDDL/FOND",
    "constraint": "SAT/SMT/CP",
    "concurrency": "TLA+",
    "process": "OCEL + conformance",
    "statistical": "SPC",
    "optimization": "OR",
    "validation": "SHACL",
    "proof": "Lean",
    "workflow": "deterministic automation",
    "evidence": "court receipt",
}

_SIGNATURE_BASES = {"dspy.Signature"}
_MARKER = re.compile(r"#\s*llm-residue:\s*(?P<body>.*)$")
_MARKER_FIELD = re.compile(r"(?P<key>kind|class)=(?P<value>[\w.:-]+)")


def _zone(path: str) -> str:
    """Path zone, by repository layout convention only (`EvidenceStrength.CONVENTION`)."""
    head = PurePosixPath(path).parts[0] if PurePosixPath(path).parts else ""
    return {"src": "package", "tests": "test"}.get(head, "other")


def _dotted(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _aliases(tree: ast.AST) -> dict[str, str]:
    """Local name -> qualified provider name, from this file's own imports."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in LLM_PROVIDERS:
                    local = alias.asname or root
                    aliases[local] = alias.name if alias.asname else root
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module.split(".")[0] in LLM_PROVIDERS:
                for alias in node.names:
                    if alias.name != "*":
                        aliases[alias.asname or alias.name] = (
                            f"{node.module}.{alias.name}"
                        )
    return aliases


def _resolve(node: ast.AST, aliases: Mapping[str, str]) -> str | None:
    dotted = _dotted(node)
    if dotted is None:
        return None
    head, _, rest = dotted.partition(".")
    if head not in aliases:
        return None
    return f"{aliases[head]}.{rest}" if rest else aliases[head]


def _canonical_api(qualified: str) -> str:
    """`dspy.predict.Predict` and `dspy.Predict` are one API: match on root + leaf."""
    parts = qualified.split(".")
    short = f"{parts[0]}.{parts[-1]}"
    return short if short in INVOCATION_APIS else qualified


def _signature_expression(call: ast.Call) -> str | None:
    candidates = list(call.args[:1]) + [
        keyword.value for keyword in call.keywords if keyword.arg == "signature"
    ]
    for node in candidates:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return repr(node.value)
        dotted = _dotted(node)
        if dotted is not None:
            return dotted
    return None


def _declaration(lines: list[str], lineno: int) -> dict[str, str]:
    for index in (lineno - 1, lineno - 2):
        if 0 <= index < len(lines):
            match = _MARKER.search(lines[index])
            if match:
                fields = {
                    m.group("key"): m.group("value")
                    for m in _MARKER_FIELD.finditer(match.group("body"))
                }
                fields["marker_line"] = str(index + 1)
                return fields
    return {}


@dataclass(frozen=True)
class ResidueEdge:
    path: str
    blob: str
    line: int
    api: str
    role: str
    signature: str | None
    kind: str
    reasoning_class: str
    declaration: Mapping[str, str]

    @property
    def zone(self) -> str:
        return _zone(self.path)

    @property
    def id(self) -> str:
        return content_id(self.path, self.blob, self.line, self.api)

    @property
    def delta_key(self) -> tuple[str, str, str]:
        """Line-free identity for comparing commits: edits above a call move its line."""
        return (self.path, self.api, self.signature or "")

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "blob": self.blob,
            "line": self.line,
            "zone": self.zone,
            "api": self.api,
            "role": self.role,
            "signature": self.signature,
            "kind": self.kind,
            "retirement_mechanism": RESIDUE_KINDS.get(self.kind, "UNKNOWN"),
            "reasoning_class": self.reasoning_class,
            "declaration": dict(self.declaration),
            "standing": FactStanding.OBSERVED.value,
        }


def _scan(path: str, blob: str, source: bytes) -> dict[str, Any]:
    text = source.decode("utf-8", errors="replace")
    try:
        with warnings.catch_warnings():
            # A subject's invalid string escapes are its business, not this census's.
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text, filename=path)
    except SyntaxError as exc:
        return {"unparseable": f"{type(exc).__name__}: line {exc.lineno}"}
    aliases = _aliases(tree)
    if not aliases:
        return {}
    lines = text.splitlines()
    edges: list[ResidueEdge] = []
    other: Counter[str] = Counter()
    rejected: list[dict[str, Any]] = []
    signatures: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = {_resolve(base, aliases) for base in node.bases}
            if {_canonical_api(b) for b in bases if b} & _SIGNATURE_BASES:
                doc = (ast.get_docstring(node) or "").strip().splitlines()
                signatures.append(
                    {
                        "path": path,
                        "blob": blob,
                        "line": node.lineno,
                        "name": node.name,
                        "question": doc[0] if doc else "",
                    }
                )
        if not isinstance(node, ast.Call):
            continue
        qualified = _resolve(node.func, aliases)
        if qualified is None:
            continue
        api = _canonical_api(qualified)
        role = INVOCATION_APIS.get(api)
        if role is None:
            other[api] += 1
            continue
        declared = _declaration(lines, node.lineno)
        kind = declared.get("kind", "UNKNOWN")
        if kind != "UNKNOWN" and kind not in RESIDUE_KINDS:
            rejected.append({"path": path, "line": node.lineno, "declared_kind": kind})
            kind = "UNKNOWN"
        edges.append(
            ResidueEdge(
                path=path,
                blob=blob,
                line=node.lineno,
                api=api,
                role=role,
                signature=_signature_expression(node) if role == "program" else None,
                kind=kind,
                reasoning_class=declared.get("class", "UNKNOWN"),
                declaration=declared,
            )
        )
    return {
        "providers": sorted({q.split(".")[0] for q in aliases.values()}),
        "edges": edges,
        "other": dict(sorted(other.items())),
        "rejected": rejected,
        "signatures": signatures,
    }


def _frontier(
    edges: Iterable[ResidueEdge], declared: Iterable[str]
) -> list[dict[str, Any]]:
    """Recurring signatures. Only a string literal or a name whose last segment is a
    declared `dspy.Signature` class is grouped: a local variable (`sig`) shared by two
    files is a coincidence of spelling, not a recurring question."""
    declared = set(declared)
    groups: dict[str, list[ResidueEdge]] = {}
    for edge in edges:
        signature = edge.signature
        if edge.role != "program" or signature is None:
            continue
        if signature.startswith(("'", '"')) or signature.split(".")[-1] in declared:
            groups.setdefault(signature.split(".")[-1], []).append(edge)
    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    return [
        {
            "signature": signature,
            "call_sites": len(members),
            "files": len({edge.path for edge in members}),
            "edge_ids": sorted(edge.id for edge in members),
            "grouping_evidence": "CONVENTION:same-signature-name-or-literal",
            "standing": FactStanding.INFERRED_CANDIDATE.value,
            "llm_cost": "UNKNOWN",
            "reuse": "UNKNOWN",
            "formalizability": "UNKNOWN",
        }
        for signature, members in ranked
        if len(members) >= 2
    ]


def residue_census(subject: RepositorySubject, checkout: Path) -> dict[str, Any]:
    """The residue census of `subject.commit`, as one canonical JSON document."""
    checkout = Path(checkout)
    verify_checkout(subject, checkout)
    entries = [
        (object_id, path)
        for mode, object_type, object_id, path in _ls_tree(checkout, subject.commit)
        if object_type == "blob" and mode != "120000" and path.endswith(".py")
    ]
    contents = dict(
        iter_blobs(checkout, sorted({object_id for object_id, _ in entries}))
    )

    edges: list[ResidueEdge] = []
    signatures: list[dict[str, Any]] = []
    import_only: list[str] = []
    unparseable: dict[str, str] = {}
    other: dict[str, dict[str, int]] = {}
    rejected: list[dict[str, Any]] = []
    for object_id, path in sorted(entries, key=lambda entry: entry[1]):
        scanned = _scan(path, object_id, contents[object_id])
        if "unparseable" in scanned:
            unparseable[path] = scanned["unparseable"]
            continue
        if not scanned:
            continue
        edges.extend(scanned["edges"])
        signatures.extend(scanned["signatures"])
        rejected.extend(scanned["rejected"])
        if scanned["other"]:
            other[path] = scanned["other"]
        if not scanned["edges"]:
            import_only.append(path)

    document: dict[str, Any] = {
        "extractor": RESIDUE_EXTRACTOR,
        "extractor_version": RESIDUE_VERSION,
        "subject": subject.to_json(),
        "rules": {
            "providers": list(LLM_PROVIDERS),
            "invocation_apis": dict(sorted(INVOCATION_APIS.items())),
            "residue_kinds": dict(RESIDUE_KINDS),
        },
        "llm_residue": len(edges),
        "llm_residue_by_zone": dict(sorted(Counter(e.zone for e in edges).items())),
        "llm_residue_by_api": dict(sorted(Counter(e.api for e in edges).items())),
        "llm_residue_by_kind": dict(sorted(Counter(e.kind for e in edges).items())),
        "llm_dependency_ratio": LDR_UNREPRESENTABLE,
        "edges": [edge.to_json() for edge in edges],
        "declared_reasoning_classes": signatures,
        "import_only": import_only,
        "other_provider_calls": other,
        "rejected_declarations": rejected,
        "unparseable": unparseable,
        "frontier": _frontier(edges, (s["name"] for s in signatures)),
    }
    document["id"] = content_id(document)
    return document


def residue_delta(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any]:
    """Edges removed and added between two censuses, compared without line numbers.

    `removed` is not `retired`: see the module docstring.
    """

    def keys(document: Mapping[str, Any]) -> Counter[tuple[str, str, str]]:
        return Counter(
            (edge["path"], edge["api"], edge["signature"] or "")
            for edge in document["edges"]
        )

    old, new = keys(before), keys(after)
    removed, added = old - new, new - old

    def rows(counter: Counter[tuple[str, str, str]]) -> list[dict[str, Any]]:
        return [
            {"path": p, "api": a, "signature": s or None, "count": n}
            for (p, a, s), n in sorted(counter.items())
        ]

    total_before, total_after = sum(old.values()), sum(new.values())
    direction = (
        "DECREASED"
        if total_after < total_before
        else "INCREASED"
        if total_after > total_before
        else "UNCHANGED"
    )
    delta = {
        "before": {"census_id": before["id"], "commit": before["subject"]["commit"]},
        "after": {"census_id": after["id"], "commit": after["subject"]["commit"]},
        "llm_residue_before": total_before,
        "llm_residue_after": total_after,
        "direction": direction,
        "removed": rows(removed),
        "added": rows(added),
        "retired": "UNKNOWN:removal-is-not-retirement;see-retirement-ledger",
    }
    delta["id"] = content_id(delta)
    return delta


def _write(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path, help="output directory")
    parser.add_argument("--checkout", type=Path, default=Path("."))
    parser.add_argument("--repository", default="seanchatmangpt/autofde-lab")
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--base", help="earlier commit to diff against")
    parser.add_argument("--visibility", default="public")
    args = parser.parse_args(argv)

    def subject(commit: str) -> RepositorySubject:
        return observe_checkout(
            args.checkout,
            repository=args.repository,
            branch="",
            visibility=args.visibility,
            inclusion_reason="LLM residue census",
            commit=commit,
        )

    after = residue_census(subject(args.commit), args.checkout)
    _write(args.out / "residue-census.json", after)
    print(
        canonical_json(
            {k: after[k] for k in ("id", "llm_residue", "llm_residue_by_zone")}
        )
    )
    if args.base:
        before = residue_census(subject(args.base), args.checkout)
        _write(args.out / "residue-census.base.json", before)
        delta = residue_delta(before, after)
        _write(args.out / "residue-delta.json", delta)
        print(
            canonical_json(
                {
                    k: delta[k]
                    for k in ("direction", "llm_residue_before", "llm_residue_after")
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
