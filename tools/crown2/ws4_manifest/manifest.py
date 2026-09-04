#!/usr/bin/env python3
"""manifest.py — CapabilityRequirement -> GGenManifestStub (real ggen.toml format).

The format is the one actually used in this ecosystem, read from
/Users/sac/crown-2-orthogonal/ggen.toml and marketplace packs' ggen.toml:

    [project] name/version/description
    [ontology] source = "..." ; imports = [...]
    [ontology.prefixes] afl = "urn:autofde-lab:" ...
    [generation] output_dir = "."
    [[generation.rules]] name / query = {file=} / template = {file=} / output_file / mode

A stub is: that manifest + a requirement ontology (`ontology/requirements.ttl`,
one RDF individual per requirement) + a ws4-owned query/template pair that
re-projects each requirement so semantic content survives generation.

Semantic preservation: every CapabilityRequirement field is either mapped to
a manifest/ontology field (with the exact target named) or listed UNMAPPED
with a reason. Nothing is silently dropped.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from packs import PackInfo, load_registry
from requirement import CapabilityRequirement

HERE = os.path.dirname(os.path.abspath(__file__))
WS4_NS = "urn:crown2:ws4#"
PREFIXES = {
    "afl": "urn:autofde-lab:",
    "ws4": WS4_NS,
    "clp": "https://ggen.dev/ontology/capability-lineage-propagation#",
    "prov": "http://www.w3.org/ns/prov#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}


@dataclass(frozen=True)
class FieldMapping:
    requirement_field: str
    status: str            # MAPPED | UNMAPPED
    target: str            # manifest/ontology field, or reason when UNMAPPED


@dataclass
class GGenManifestStub:
    project_name: str
    version: str
    description: str
    ontology_source: str
    ontology_imports: list[str]
    prefixes: dict[str, str]
    output_dir: str
    rules: list[dict]
    requirements_ttl: str
    mappings: list[FieldMapping]
    unbound: list[dict] = field(default_factory=list)   # bindings that failed

    # --- serialization -----------------------------------------------------
    def to_toml(self) -> str:
        q = json.dumps  # TOML basic strings == JSON string escaping for our content
        lines = [
            "[project]",
            f"name = {q(self.project_name)}",
            f"version = {q(self.version)}",
            f"description = {q(self.description)}",
            "",
            "[ontology]",
            f"source = {q(self.ontology_source)}",
            "imports = [",
            *[f"    {q(i)}," for i in self.ontology_imports],
            "]",
            "",
            "[ontology.prefixes]",
            *[f"{k} = {q(v)}" for k, v in self.prefixes.items()],
            "",
            "[generation]",
            f"output_dir = {q(self.output_dir)}",
        ]
        for r in self.rules:
            lines += [
                "",
                "[[generation.rules]]",
                f"name = {q(r['name'])}",
                f"query = {{ file = {q(r['query'])} }}",
                f"template = {{ file = {q(r['template'])} }}",
                f"output_file = {q(r['output_file'])}",
                f"mode = {q(r.get('mode', 'Create'))}",
            ]
        return "\n".join(lines) + "\n"

    def preservation_report(self) -> dict:
        unmapped = [m for m in self.mappings if m.status == "UNMAPPED"]
        return {
            "mapped": [m.requirement_field for m in self.mappings if m.status == "MAPPED"],
            "unmapped": [{"field": m.requirement_field, "reason": m.target} for m in unmapped],
            "unbound": self.unbound,
            "preserved": not unmapped and not self.unbound,
        }

    def write(self, project_dir: str, registry: dict[str, PackInfo]) -> dict[str, str]:
        """Materialize a runnable ggen project directory. Returns written paths."""
        os.makedirs(os.path.join(project_dir, "ontology"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "queries"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "templates"), exist_ok=True)
        written = {}
        p = os.path.join(project_dir, "ggen.toml")
        with open(p, "w") as fh:
            fh.write(self.to_toml())
        written["ggen.toml"] = p
        p = os.path.join(project_dir, self.ontology_source)
        with open(p, "w") as fh:
            fh.write(self.requirements_ttl)
        written["requirements.ttl"] = p
        # ws4-owned query/template: copy from this module's directory
        for sub, fn in (("queries", "ws4-requirement.rq"), ("templates", "ws4-requirement.json.tera")):
            src = os.path.join(HERE, sub, fn)
            dst = os.path.join(project_dir, sub, fn)
            with open(src) as s, open(dst, "w") as d:
                d.write(s.read())
            written[fn] = dst
        # vendor bound pack files (ggen runs in Docker with $PWD mounted at
        # /workspace, so every path must be relative and inside project_dir)
        for rule in self.rules:
            for key in ("query", "template"):
                rel = rule[key]
                if not rel.startswith("vendor/"):
                    continue
                pack_name = rel.split("/")[1]
                src = os.path.join(registry[pack_name].path, *rel.split("/")[2:])
                dst = os.path.join(project_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(src) as s_, open(dst, "w") as d_:
                    d_.write(s_.read())
                written[rel] = dst
        for rel in self.ontology_imports:
            pack_name = rel.split("/")[1]
            src = registry[pack_name].ontology
            dst = os.path.join(project_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(src) as s_, open(dst, "w") as d_:
                d_.write(s_.read())
            written[rel] = dst
        p = os.path.join(project_dir, "preservation.json")
        with open(p, "w") as fh:
            json.dump(self.preservation_report(), fh, indent=2, sort_keys=True)
        written["preservation.json"] = p
        return written


# --- TTL projection ---------------------------------------------------------
def _lit(s: str) -> str:
    return json.dumps(s)


def requirements_to_ttl(reqs: list[CapabilityRequirement]) -> str:
    out = [f"@prefix {k}: <{v}> ." for k, v in PREFIXES.items()]
    out.append("")
    out.append("ws4:CapabilityRequirement a rdfs:Class .")
    out.append("ws4:GapDiagnosis a rdfs:Class .")
    out.append("")
    for r in reqs:
        g = r.gap
        gid = f"ws4:{g.gap_id}"
        out.append(f"{gid} a ws4:GapDiagnosis ;")
        out.append(f"  ws4:observedState {_lit(g.observed_state)} ;")
        out.append(f"  ws4:desiredState {_lit(g.desired_state)} ;")
        out.append(f"  ws4:missingTransition {_lit(g.missing_transition)} ;")
        for e in g.evidence_refs:
            out.append(f"  ws4:evidenceRef {_lit(e)} ;")
        out[-1] = out[-1].rstrip(" ;") + " ."
        rid = f"ws4:{r.requirement_id}"
        out.append(f"{rid} a ws4:CapabilityRequirement ;")
        out.append(f"  ws4:gap {gid} ;")
        out.append(f"  ws4:neededTransition {_lit(r.needed_transition)} ;")
        for c in r.preconditions:
            out.append(f"  ws4:precondition {_lit(c)} ;")
        for c in r.postconditions:
            out.append(f"  ws4:postcondition {_lit(c)} ;")
        out.append(f"  ws4:authorityClass {_lit(r.authority_class)} ;")
        out.append(f"  ws4:qualificationStrategy {_lit(r.qualification_strategy)} ;")
        for iri in r.semantic_anchors:
            out.append(f"  ws4:semanticAnchor <{iri}> ;")
        out.append(f"  ws4:boundPack {_lit(r.binding.pack)} ;")
        out.append(f"  ws4:boundTemplate {_lit(r.binding.template)} ;")
        out.append(f"  ws4:boundQuery {_lit(r.binding.query)} ;")
        out.append(f"  ws4:outputFile {_lit(r.binding.output_file)} ;")
        if r.description:
            out.append(f"  rdfs:comment {_lit(r.description)} ;")
        out[-1] = out[-1].rstrip(" ;") + " ."
        out.append("")
    return "\n".join(out)


# --- builder ----------------------------------------------------------------
_FIELD_TARGETS = {
    "requirement_id": "ontology: ws4:<requirement_id> a ws4:CapabilityRequirement",
    "gap": "ontology: ws4:gap -> ws4:GapDiagnosis individual",
    "needed_transition": "ontology: ws4:neededTransition",
    "preconditions": "ontology: ws4:precondition (one triple each)",
    "postconditions": "ontology: ws4:postcondition (one triple each)",
    "authority_class": "ontology: ws4:authorityClass",
    "qualification_strategy": "ontology: ws4:qualificationStrategy",
    "semantic_anchors": "ontology: ws4:semanticAnchor <IRI> + ggen.toml [ontology.prefixes]",
    "binding": "ggen.toml [[generation.rules]] query/template/output_file",
    "description": "ggen.toml [project].description + rdfs:comment",
}


def build_stub(
    reqs: list[CapabilityRequirement],
    registry: dict[str, PackInfo] | None = None,
    project_name: str = "crown2-ws4-stub",
    version: str = "0.1.0",
) -> GGenManifestStub:
    registry = load_registry() if registry is None else registry
    rules: list[dict] = []
    imports: list[str] = []
    unbound: list[dict] = []
    mappings: list[FieldMapping] = []

    for r in reqs:
        pack = registry.get(r.binding.pack)
        if pack is None:
            unbound.append({"requirement": r.requirement_id, "reason": f"pack not admitted: {r.binding.pack}"})
            continue
        if r.binding.template not in pack.templates:
            unbound.append({"requirement": r.requirement_id, "reason": f"template not in pack: {r.binding.template}"})
            continue
        if r.binding.query not in pack.queries:
            unbound.append({"requirement": r.requirement_id, "reason": f"query not in pack: {r.binding.query}"})
            continue
        vendored_ont = f"vendor/{pack.name}/{os.path.basename(pack.ontology)}"
        if vendored_ont not in imports:
            imports.append(vendored_ont)
        rules.append({
            "name": f"{r.requirement_id}--{r.binding.pack}",
            "query": f"vendor/{pack.name}/queries/{r.binding.query}",
            "template": f"vendor/{pack.name}/templates/{r.binding.template}",
            "output_file": r.binding.output_file,
            "mode": "Create",
        })
    # ws4-owned re-projection rule: carries every requirement field through generation
    rules.append({
        "name": "ws4-requirement-projection",
        "query": "queries/ws4-requirement.rq",
        "template": "templates/ws4-requirement.json.tera",
        "output_file": "generated/ws4/requirements.json",
        "mode": "Create",
    })

    for f in ("requirement_id", "gap", "needed_transition", "preconditions", "postconditions",
              "authority_class", "qualification_strategy", "semantic_anchors", "binding",
              "description"):
        mappings.append(FieldMapping(f, "MAPPED", _FIELD_TARGETS[f]))
    if any(r.extra for r in reqs):
        keys = sorted({k for r in reqs for k in r.extra})
        mappings.append(FieldMapping(
            "extra", "UNMAPPED",
            f"free-form bag has no ggen.toml or ws4 ontology property; keys={keys}",
        ))
    # evidence_refs is a gap sub-field; anchors outside declared prefixes cannot be prefixed
    for r in reqs:
        for iri in r.semantic_anchors:
            if not any(iri.startswith(v) for v in PREFIXES.values()):
                mappings.append(FieldMapping(
                    f"semantic_anchors[{iri}]", "UNMAPPED",
                    "IRI prefix not declared in [ontology.prefixes]; emitted as full IRI only",
                ))

    desc = "WS4 gap->manifest stub: " + "; ".join(r.requirement_id for r in reqs)
    return GGenManifestStub(
        project_name=project_name,
        version=version,
        description=desc,
        ontology_source="ontology/requirements.ttl",
        ontology_imports=imports,
        prefixes=dict(PREFIXES),
        output_dir=".",
        rules=rules,
        requirements_ttl=requirements_to_ttl(reqs),
        mappings=mappings,
        unbound=unbound,
    )
