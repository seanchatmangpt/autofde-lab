#!/usr/bin/env python3
"""One-shot constructor for the ForwardBench RDF/ggen source surface.

This file is transport only. The bootstrap workflow deletes it after it has
materialized the canonical papers.ttl, ggen project, and bounded SELECT adapter.
"""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import DCTERMS, OWL, SKOS, XSD

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
DATA = Namespace("https://github.com/seanchatmangpt/autofde-lab/data/forwardbench/")
AFB = Namespace("https://github.com/seanchatmangpt/autofde-lab/ns/forwardbench#")
FABIO = Namespace("http://purl.org/spar/fabio/")
BIBO = Namespace("http://purl.org/ontology/bibo/")
CITO = Namespace("http://purl.org/spar/cito/")
DOAP = Namespace("http://usefulinc.com/ns/doap#")
SCHEMA = Namespace("https://schema.org/")
PROV = Namespace("http://www.w3.org/ns/prov#")
PPLAN = Namespace("http://purl.org/net/p-plan#")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
ODRL = Namespace("http://www.w3.org/ns/odrl/2/")

NEW_PAPERS = [
    ("2605.07161", "SREGym: A Live Benchmark for AI SRE Agents with High-Fidelity Failure Scenarios", ["sre", "cloud", "live-gym"]),
    ("2601.20882", "DevOps-Gym", ["devops", "cloud", "gym"]),
    ("2412.17015", "RCAEval", ["root-cause-analysis", "microservices"]),
    ("2506.03828", "AssetOpsBench: Benchmarking AI Agents for Task Automation in Industrial Asset Operations and Maintenance", ["enterprise", "asset-operations", "maintenance"]),
    ("2506.02009", "STRATUS: Autonomous Reliability Engineering of Modern Clouds", ["sre", "cloud", "multi-agent"]),
    ("2407.12165", "AIOpsLab: Design Principles for Autonomous Clouds", ["aiops", "cloud", "agents"]),
    ("2601.11868", "Terminal-Bench", ["terminal", "systems", "benchmark"]),
    ("2412.14161", "TheAgentCompany", ["enterprise", "knowledge-work", "agents"]),
    ("2508.14704", "MCP-Universe", ["mcp", "tools", "benchmark"]),
    ("2509.24002", "MCPMark", ["mcp", "tools", "benchmark"]),
    ("2508.20453", "MCP-Bench: Benchmarking Tool-Using LLM Agents with Complex Real-World Tasks via MCP Servers", ["mcp", "tools", "benchmark"]),
    ("2508.07575", "MCPToolBench++", ["mcp", "tools", "benchmark"]),
    ("2509.26506", "SCUBA", ["computer-use", "agents", "benchmark"]),
    ("2406.13264", "Wonderbread", ["enterprise", "workflow", "benchmark"]),
    ("2504.14064", "DoomArena", ["security", "web", "agents"]),
    ("2606.28480", "TUA-Bench", ["computer-use", "terminal", "agents"]),
    ("2410.09024", "AgentHarm", ["safety", "security", "agents"]),
    ("2606.04460", "CyberGym-E2E", ["cybersecurity", "gym", "end-to-end"]),
    ("2604.19533", "Cyber Defense Benchmark", ["cybersecurity", "defense", "benchmark"]),
    ("2607.20531", "DynamicMCPBench", ["mcp", "dynamic", "effect-scoring"]),
    ("2509.09734", "MCP-AgentBench", ["mcp", "tools", "agents"]),
    ("2508.01780", "LiveMCPBench", ["mcp", "live", "tools"]),
    ("2412.05467", "BrowserGym: A Gym Ecosystem for Web Agent Research", ["browser", "web", "gym"]),
    ("2405.14573", "AndroidWorld", ["android", "computer-use", "agents"]),
]

# slug, repository, adapter family, category, local-safe, requires-live-authority,
# source standing, smoke profile.
VENDORS = [
    ("cube-standard", "https://github.com/The-AI-Alliance/cube-standard.git", "CUBE", "harness", True, False, "CANDIDATE", "core"),
    ("cube-harness", "https://github.com/The-AI-Alliance/cube-harness.git", "CUBE", "harness", True, False, "CANDIDATE", "none"),
    ("harbor", "https://github.com/harbor-framework/harbor.git", "HARBOR", "harness", True, False, "CANDIDATE", "core"),
    ("terminal-bench", "https://github.com/harbor-framework/terminal-bench-2.git", "HARBOR", "terminal", True, False, "CANDIDATE", "none"),
    ("browsergym", "https://github.com/ServiceNow/BrowserGym.git", "BROWSERGYM", "browser", True, False, "CANDIDATE", "core"),
    ("agentlab", "https://github.com/ServiceNow/AgentLab.git", "BROWSERGYM", "browser", True, False, "CANDIDATE", "none"),
    ("workarena", "https://github.com/ServiceNow/WorkArena.git", "BROWSERGYM", "enterprise", False, False, "CANDIDATE", "none"),
    ("webarena", "https://github.com/web-arena-x/webarena.git", "BROWSERGYM", "browser", False, False, "CANDIDATE", "none"),
    ("sregym", "https://github.com/SREGym/SREGym.git", "KUBERNETES", "sre", False, False, "CANDIDATE", "none"),
    ("itbench", "https://github.com/itbench-hub/ITBench.git", "KUBERNETES", "itops", False, False, "CANDIDATE", "none"),
    ("aiopslab", "https://github.com/microsoft/AIOpsLab.git", "KUBERNETES", "aiops", False, False, "CANDIDATE", "none"),
    ("o11y-bench", "https://github.com/grafana/o11y-bench.git", "NATIVE_COMMAND", "observability", True, False, "CANDIDATE", "none"),
    ("rcaeval", "https://github.com/phamquiluan/RCAEval.git", "NATIVE_COMMAND", "root-cause-analysis", True, False, "CANDIDATE", "none"),
    ("assetopsbench", "https://github.com/IBM/AssetOpsBench.git", "NATIVE_COMMAND", "enterprise", True, False, "CANDIDATE", "none"),
    ("devops-gym", "https://github.com/ucsb-mlsec/DevOps-Gym.git", "NATIVE_COMMAND", "devops", False, False, "CANDIDATE", "none"),
    ("swe-bench", "https://github.com/SWE-bench/SWE-bench.git", "HARBOR", "software", True, False, "CANDIDATE", "none"),
    ("r2e-gym", "https://github.com/R2E-Gym/R2E-Gym.git", "NATIVE_COMMAND", "software", True, False, "CANDIDATE", "none"),
    ("osworld", "https://github.com/xlang-ai/OSWorld.git", "CUBE", "computer-use", False, False, "CANDIDATE", "none"),
    ("tua-bench", "https://github.com/facebookresearch/TUA-Bench.git", "NATIVE_COMMAND", "computer-use", True, False, "CANDIDATE", "none"),
    ("terminal-bench-pro", "https://github.com/alibaba/terminal-bench-pro.git", "HARBOR", "terminal", True, False, "CANDIDATE", "none"),
    ("scuba", "https://github.com/SalesforceAIResearch/SCUBA.git", "NATIVE_COMMAND", "computer-use", True, False, "CANDIDATE", "none"),
    ("crmarena", "https://github.com/SalesforceAIResearch/CRMArena.git", "NATIVE_COMMAND", "enterprise", False, False, "CANDIDATE", "none"),
    ("enterprisebench", "https://github.com/ast-fri/EnterpriseBench.git", "NATIVE_COMMAND", "enterprise", False, False, "BLOCKED:DATA_TERMS_OR_ACCESS", "none"),
    ("the-agent-company", "https://github.com/TheAgentCompany/TheAgentCompany.git", "NATIVE_COMMAND", "enterprise", False, False, "CANDIDATE", "none"),
    ("wonderbread", "https://github.com/HazyResearch/wonderbread.git", "NATIVE_COMMAND", "enterprise", True, False, "CANDIDATE", "none"),
    ("toolsandbox", "https://github.com/apple/ToolSandbox.git", "NATIVE_COMMAND", "tools", True, False, "CANDIDATE", "none"),
    ("tau2-bench", "https://github.com/sierra-research/tau2-bench.git", "NATIVE_COMMAND", "tools", True, False, "CANDIDATE", "none"),
    ("mcp-universe", "https://github.com/SalesforceAIResearch/MCP-Universe.git", "MCP", "mcp", False, False, "BLOCKED:EXTERNAL_SERVICES_OR_KEYS", "none"),
    ("mcpmark", "https://github.com/eval-sys/mcpmark.git", "MCP", "mcp", True, False, "CANDIDATE", "none"),
    ("mcp-bench", "https://github.com/Accenture/mcp-bench.git", "MCP", "mcp", False, False, "BLOCKED:EXTERNAL_API_KEYS", "none"),
    ("agentdojo", "https://github.com/ethz-spylab/agentdojo.git", "NATIVE_COMMAND", "security", True, False, "CANDIDATE", "none"),
    ("doomarena", "https://github.com/ServiceNow/DoomArena.git", "BROWSERGYM", "security", False, False, "CANDIDATE", "none"),
    ("st-webagentbench", "https://github.com/segev-shlomov/ST-WebAgentBench.git", "BROWSERGYM", "security", False, False, "CANDIDATE", "none"),
    ("sec-bench", "https://github.com/SEC-bench/SEC-bench.git", "NATIVE_COMMAND", "security", True, False, "CANDIDATE", "none"),
    ("bountytasks", "https://github.com/bountybench/bountytasks.git", "NATIVE_COMMAND", "security", False, False, "PARTIAL_ALIVE", "none"),
    ("cybench", "https://github.com/andyzorigin/cybench.git", "NATIVE_COMMAND", "security", True, False, "CANDIDATE", "none"),
    ("asb", "https://github.com/agiresearch/ASB.git", "NATIVE_COMMAND", "security", True, False, "CANDIDATE", "none"),
    ("inspect-evals", "https://github.com/UKGovernmentBEIS/inspect_evals.git", "NATIVE_COMMAND", "evaluation", True, False, "CANDIDATE", "none"),
    ("qqr", "https://github.com/Alibaba-NLP/qqr.git", "NATIVE_COMMAND", "security", True, False, "PARTIAL_ALIVE", "none"),
    ("cybergym-e2e", "https://github.com/sunblaze-ucb/cybergym-e2e.git", "NATIVE_COMMAND", "security", False, False, "CANDIDATE", "none"),
    ("cloudfoxable", "https://github.com/BishopFox/cloudfoxable.git", "TERRAFORM", "cloud-security", False, True, "BLOCKED:LIVE_CLOUD_AUTHORITY", "none"),
    ("cloudgoat", "https://github.com/RhinoSecurityLabs/cloudgoat.git", "TERRAFORM", "cloud-security", False, True, "BLOCKED:LIVE_CLOUD_AUTHORITY", "none"),
    ("terragoat", "https://github.com/bridgecrewio/terragoat.git", "TERRAFORM", "iac-security", True, False, "CANDIDATE", "none"),
    ("kubernetes-goat", "https://github.com/madhuakula/kubernetes-goat.git", "KUBERNETES", "kubernetes-security", False, False, "CANDIDATE", "none"),
    ("azuregoat", "https://github.com/ine-labs/AzureGoat.git", "TERRAFORM", "cloud-security", False, True, "BLOCKED:LIVE_CLOUD_AUTHORITY", "none"),
    ("gcpgoat", "https://github.com/ine-labs/GCPGoat.git", "TERRAFORM", "cloud-security", False, True, "BLOCKED:LIVE_CLOUD_AUTHORITY", "none"),
    ("sre-bench", "https://github.com/agentkube/SRE-bench.git", "KUBERNETES", "sre", False, False, "CANDIDATE", "none"),
    ("sadservers", "https://github.com/SadServers/sadservers.git", "NATIVE_COMMAND", "sre", False, False, "BLOCKED:SCENARIO_SOURCE_NOT_PUBLIC", "none"),
    ("agentbench", "https://github.com/THUDM/AgentBench.git", "NATIVE_COMMAND", "agents", True, False, "CANDIDATE", "none"),
    ("agentgym", "https://github.com/WooooDyy/AgentGym.git", "GYMNASIUM", "agents", True, False, "CANDIDATE", "none"),
    ("androidworld", "https://github.com/google-research/android_world.git", "NATIVE_COMMAND", "computer-use", False, False, "CANDIDATE", "none"),
    ("general-agentbench", "https://github.com/cxcscmu/General-AgentBench.git", "NATIVE_COMMAND", "agents", True, False, "CANDIDATE", "none"),
]

BROWSERGYM_LOGICAL = [
    ("miniwob", "MiniWoB", "browser"),
    ("webarena", "WebArena", "browser"),
    ("webarena-verified", "WebArenaVerified", "browser"),
    ("visualwebarena", "VisualWebArena", "browser"),
    ("workarena", "WorkArena", "enterprise"),
    ("assistantbench", "AssistantBench", "enterprise"),
    ("weblinx", "WebLINX", "browser"),
    ("openapps", "OpenApps", "enterprise"),
    ("timewarp", "TimeWarp", "browser"),
]

EXTRA_LOGICAL = [
    ("cube-counter", "CUBE canonical counter scenario", "harness", "cube-standard", "CUBE", "CANDIDATE", True, False),
    ("itbench-sre", "ITBench SRE", "sre", "itbench", "KUBERNETES", "CANDIDATE", False, False),
    ("itbench-ciso", "ITBench CISO", "security", "itbench", "KUBERNETES", "CANDIDATE", False, False),
    ("itbench-finops", "ITBench FinOps", "finops", "itbench", "KUBERNETES", "CANDIDATE", False, False),
    ("harbor-catalog", "Harbor third-party benchmark catalog", "harness", "harbor", "HARBOR", "CANDIDATE", True, False),
    ("world-of-workflows", "World of Workflows", "enterprise", None, "NATIVE_COMMAND", "UNKNOWN_REPOSITORY", False, False),
    ("sir-bench", "SIR-Bench", "security", None, "NATIVE_COMMAND", "UNKNOWN_REPOSITORY", False, False),
    ("pm-llm-benchmark", "PM-LLM-Benchmark", "process-mining", None, "NATIVE_COMMAND", "UNKNOWN_REPOSITORY", True, False),
    ("multi-iac-eval", "Multi-IaC-Eval", "iac", None, "NATIVE_COMMAND", "UNKNOWN_REPOSITORY", True, False),
    ("verifier-first-terraform", "Verifier-First Terraform", "iac", None, "TERRAFORM", "UNKNOWN_REPOSITORY", True, False),
    ("security-first-terraform", "Security-First Terraform", "iac-security", None, "TERRAFORM", "UNKNOWN_REPOSITORY", True, False),
    ("arfbench", "ARFBench", "incident", None, "NATIVE_COMMAND", "UNKNOWN_REPOSITORY", True, False),
    ("frontier-eng", "Frontier-Eng", "engineering", None, "NATIVE_COMMAND", "UNKNOWN_REPOSITORY", True, False),
    ("benchbench", "BenchBench", "benchmark-generation", None, "NATIVE_COMMAND", "UNKNOWN_REPOSITORY", True, False),
    ("sciagentarena", "SciAgentArena", "science", None, "NATIVE_COMMAND", "UNKNOWN_REPOSITORY", False, False),
    ("dynamicmcpbench", "DynamicMCPBench", "mcp", None, "MCP", "UNKNOWN_REPOSITORY", False, False),
    ("mcp-agentbench", "MCP-AgentBench", "mcp", None, "MCP", "UNKNOWN_REPOSITORY", False, False),
    ("livemcpbench", "LiveMCPBench", "mcp", None, "MCP", "UNKNOWN_REPOSITORY", False, False),
    ("cyber-defense-benchmark", "Cyber Defense Benchmark", "security", None, "NATIVE_COMMAND", "PARTIAL_ALIVE", False, False),
]

PAPER_TO_BENCH = {
    "2502.05352": "itbench",
    "2501.06706": "aiopslab",
    "2606.29193": "rcaeval",
    "2606.08590": "sre-bench",
    "2604.21199": "arfbench",
    "2509.05303": "multi-iac-eval",
    "2607.20478": "verifier-first-terraform",
    "2608.02672": "security-first-terraform",
    "2604.12040": "sir-bench",
    "2607.26791": "qqr",
    "2601.22130": "world-of-workflows",
    "2407.13244": "pm-llm-benchmark",
    "2603.15798": "cube-standard",
    "2408.04682": "toolsandbox",
    "2403.07718": "workarena",
    "2407.05291": "workarena",
    "2510.27287": "enterprisebench",
    "2505.18878": "crmarena",
    "2404.07972": "osworld",
    "2308.03688": "agentbench",
    "2504.07164": "r2e-gym",
    "2605.07161": "sregym",
    "2601.20882": "devops-gym",
    "2412.17015": "rcaeval",
    "2506.03828": "assetopsbench",
    "2506.02009": "itbench",
    "2407.12165": "aiopslab",
    "2601.11868": "terminal-bench",
    "2412.14161": "the-agent-company",
    "2508.14704": "mcp-universe",
    "2509.24002": "mcpmark",
    "2508.20453": "mcp-bench",
    "2509.26506": "scuba",
    "2406.13264": "wonderbread",
    "2504.14064": "doomarena",
    "2606.28480": "tua-bench",
    "2606.04460": "cybergym-e2e",
    "2604.19533": "cyber-defense-benchmark",
    "2607.20531": "dynamicmcpbench",
    "2509.09734": "mcp-agentbench",
    "2508.01780": "livemcpbench",
    "2412.05467": "browsergym",
    "2405.14573": "androidworld",
}

ADAPTER_PLAN = {
    "CUBE": "plan-cube",
    "HARBOR": "plan-harbor",
    "BROWSERGYM": "plan-browsergym",
    "MCP": "plan-mcp",
    "GYMNASIUM": "plan-gymnasium",
    "TERRAFORM": "plan-terraform",
    "KUBERNETES": "plan-kubernetes",
    "NATIVE_COMMAND": "plan-native",
}


def slug_iri(prefix: str, value: str) -> URIRef:
    return DATA[f"{prefix}-{value}"]


def load_papers() -> list[dict]:
    old = tomllib.loads((ROOT / "manifest.toml").read_text())
    papers = []
    seen = set()
    for p in old.get("paper", []):
        pid = p["id"]
        seen.add(pid)
        papers.append({"id": pid, "title": p["title"], "tags": list(p.get("tags", [])), "priority": p.get("priority", "adjacent")})
    for pid, title, tags in NEW_PAPERS:
        if pid not in seen:
            papers.append({"id": pid, "title": title, "tags": tags, "priority": "core"})
    papers.sort(key=lambda x: x["id"])
    return papers


def build_benchmarks() -> list[dict]:
    rows = []
    vendor_by_slug = {v[0]: v for v in VENDORS}
    for slug, repo, adapter, category, local_safe, requires_auth, standing, smoke in VENDORS:
        rows.append({
            "slug": slug,
            "title": slug.replace("-", " ").title(),
            "category": category,
            "vendor": slug,
            "adapter": adapter,
            "standing": standing,
            "local_safe": local_safe,
            "requires_authority": requires_auth,
        })
    for slug, title, category in BROWSERGYM_LOGICAL:
        rows.append({"slug": f"browsergym-{slug}", "title": title, "category": category, "vendor": "browsergym", "adapter": "BROWSERGYM", "standing": "CANDIDATE", "local_safe": slug == "miniwob", "requires_authority": False})
    for slug, title, category, vendor, adapter, standing, local_safe, requires_auth in EXTRA_LOGICAL:
        rows.append({"slug": slug, "title": title, "category": category, "vendor": vendor, "adapter": adapter, "standing": standing, "local_safe": local_safe, "requires_authority": requires_auth})
    unique = {}
    for row in rows:
        unique.setdefault(row["slug"], row)
    return [unique[k] for k in sorted(unique)]


def write_vocab() -> None:
    out = ROOT / "ontology"
    out.mkdir(parents=True, exist_ok=True)
    (out / "forwardbench-vocab.ttl").write_text('''@prefix afb: <https://github.com/seanchatmangpt/autofde-lab/ns/forwardbench#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix doap: <http://usefulinc.com/ns/doap#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix pplan: <http://purl.org/net/p-plan#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <https://schema.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

afb: a owl:Ontology ;
  dct:title "AutoFDE ForwardBench execution vocabulary" ;
  dct:description "Minimal local vocabulary for execution facts not supplied by public scholarly/software/provenance ontologies." ;
  dct:conformsTo <http://purl.org/dc/terms/>, <http://purl.org/spar/fabio/>, <http://purl.org/ontology/bibo/>, <http://purl.org/spar/cito/>, <http://usefulinc.com/ns/doap#>, <http://www.w3.org/ns/prov#>, <http://purl.org/net/p-plan#>, <http://www.w3.org/ns/dcat#>, <http://www.w3.org/2004/02/skos/core#>, <http://www.w3.org/ns/shacl#>, <http://www.w3.org/ns/odrl/2/> .

afb:Benchmark a owl:Class ; rdfs:subClassOf dcat:Dataset, schema:Dataset .
afb:VendorProject a owl:Class ; rdfs:subClassOf doap:Project, schema:SoftwareSourceCode .
afb:ExecutionPlan a owl:Class ; rdfs:subClassOf prov:Plan, pplan:Plan .
afb:slug a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:adapterFamily a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:sourceStanding a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:resolutionStanding a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:smokeStanding a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:retrievalStanding a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:vendorPath a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:repositoryUrl a owl:DatatypeProperty ; rdfs:range xsd:anyURI .
afb:requestedRef a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:pinnedRevision a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:smokeProfile a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:localSafe a owl:DatatypeProperty ; rdfs:range xsd:boolean .
afb:requiresAuthority a owl:DatatypeProperty ; rdfs:range xsd:boolean .
afb:arxivId a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:sha256 a owl:DatatypeProperty ; rdfs:range xsd:string .
afb:vendorProject a owl:ObjectProperty ; rdfs:range afb:VendorProject .
afb:usesPlan a owl:ObjectProperty ; rdfs:range afb:ExecutionPlan .
''')
    (out / "papers-shapes.ttl").write_text('''@prefix afb: <https://github.com/seanchatmangpt/autofde-lab/ns/forwardbench#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

afb:BenchmarkShape a sh:NodeShape ;
  sh:targetClass afb:Benchmark ;
  sh:property [ sh:path afb:slug ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path dct:title ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path afb:adapterFamily ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path afb:sourceStanding ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path afb:localSafe ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:boolean ] ;
  sh:property [ sh:path afb:requiresAuthority ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:boolean ] .

afb:VendorShape a sh:NodeShape ;
  sh:targetClass afb:VendorProject ;
  sh:property [ sh:path afb:slug ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path afb:repositoryUrl ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path afb:vendorPath ; sh:minCount 1 ; sh:maxCount 1 ] .
''')


def write_graph(papers: list[dict], benchmarks: list[dict]) -> int:
    g = Graph()
    for prefix, ns in [("afb", AFB), ("data", DATA), ("dct", DCTERMS), ("fabio", FABIO), ("bibo", BIBO), ("cito", CITO), ("doap", DOAP), ("schema", SCHEMA), ("prov", PROV), ("pplan", PPLAN), ("dcat", DCAT), ("skos", SKOS), ("odrl", ODRL)]:
        g.bind(prefix, ns)
    root = DATA["corpus"]
    g.add((root, RDF.type, DCAT.Catalog))
    g.add((root, DCTERMS.title, Literal("ForwardBench / AutoFDE research and gym corpus")))
    for iri in [URIRef("http://purl.org/dc/terms/"), URIRef("http://purl.org/spar/fabio/"), URIRef("http://purl.org/ontology/bibo/"), URIRef("http://purl.org/spar/cito/"), URIRef("http://usefulinc.com/ns/doap#"), URIRef("http://www.w3.org/ns/prov#"), URIRef("http://purl.org/net/p-plan#"), URIRef("http://www.w3.org/ns/dcat#"), URIRef("http://www.w3.org/2004/02/skos/core#"), URIRef("http://www.w3.org/ns/shacl#"), URIRef("http://www.w3.org/ns/odrl/2/")]:
        g.add((root, DCTERMS.conformsTo, iri))

    category_nodes = {}
    for row in benchmarks:
        cat = row["category"]
        if cat not in category_nodes:
            c = slug_iri("category", re.sub(r"[^a-z0-9]+", "-", cat.lower()).strip("-"))
            category_nodes[cat] = c
            g.add((c, RDF.type, SKOS.Concept))
            g.add((c, SKOS.prefLabel, Literal(cat)))

    vendor_nodes = {}
    for slug, repo, adapter, category, local_safe, requires_auth, standing, smoke in VENDORS:
        v = slug_iri("vendor", slug)
        vendor_nodes[slug] = v
        g.add((v, RDF.type, AFB.VendorProject))
        g.add((v, AFB.slug, Literal(slug)))
        g.add((v, DCTERMS.title, Literal(slug.replace("-", " ").title())))
        g.add((v, AFB.repositoryUrl, Literal(repo, datatype=XSD.anyURI)))
        g.add((v, SCHEMA.codeRepository, URIRef(repo.removesuffix(".git"))))
        g.add((v, AFB.vendorPath, Literal(f"vendor/gyms/{slug}")))
        g.add((v, AFB.requestedRef, Literal("HEAD")))
        g.add((v, AFB.adapterFamily, Literal(adapter)))
        g.add((v, AFB.sourceStanding, Literal(standing)))
        g.add((v, AFB.smokeProfile, Literal(smoke)))
        g.add((v, AFB.localSafe, Literal(local_safe)))
        g.add((v, AFB.requiresAuthority, Literal(requires_auth)))

    plan_nodes = {}
    for family, name in ADAPTER_PLAN.items():
        p = slug_iri("plan", name.removeprefix("plan-"))
        plan_nodes[family] = p
        g.add((p, RDF.type, AFB.ExecutionPlan))
        g.add((p, DCTERMS.title, Literal(f"{family} ForwardBench bounded execution plan")))
        g.add((p, AFB.adapterFamily, Literal(family)))
        previous = None
        for order, step_name in enumerate(["Observe", "SelectAdapter", "PrepareSandbox", "RunScenario", "VerifyEffect", "ReceiptTrajectory"], start=1):
            s = slug_iri("step", f"{name.removeprefix('plan-')}-{order}-{step_name.lower()}")
            g.add((s, RDF.type, PPLAN.Step))
            g.add((s, DCTERMS.title, Literal(step_name)))
            g.add((p, PPLAN.isDecomposedAsPlan, p)) if False else None
            if previous is not None:
                g.add((s, PPLAN.isPrecededBy, previous))
            previous = s
        g.add((p, PROV.value, Literal("SELECT/CONSTRUCT only until explicit environment authority is present")))

    bench_nodes = {}
    for row in benchmarks:
        b = slug_iri("benchmark", row["slug"])
        bench_nodes[row["slug"]] = b
        g.add((b, RDF.type, AFB.Benchmark))
        g.add((b, AFB.slug, Literal(row["slug"])))
        g.add((b, DCTERMS.title, Literal(row["title"])))
        g.add((b, DCTERMS.subject, category_nodes[row["category"]]))
        g.add((b, AFB.adapterFamily, Literal(row["adapter"])))
        g.add((b, AFB.sourceStanding, Literal(row["standing"])))
        g.add((b, AFB.localSafe, Literal(row["local_safe"])))
        g.add((b, AFB.requiresAuthority, Literal(row["requires_authority"])))
        g.add((b, AFB.usesPlan, plan_nodes[row["adapter"]]))
        if row["vendor"]:
            g.add((b, AFB.vendorProject, vendor_nodes[row["vendor"]]))
            g.add((b, DCTERMS.source, vendor_nodes[row["vendor"]]))
        g.add((root, DCAT.dataset, b))

    for paper in papers:
        pid = paper["id"]
        p = slug_iri("paper", pid.replace(".", "-"))
        g.add((p, RDF.type, FABIO.ResearchPaper))
        g.add((p, RDF.type, BIBO.AcademicArticle))
        g.add((p, RDF.type, SCHEMA.ScholarlyArticle))
        g.add((p, AFB.arxivId, Literal(pid)))
        g.add((p, DCTERMS.identifier, Literal(f"arXiv:{pid}")))
        g.add((p, DCTERMS.title, Literal(paper["title"])))
        g.add((p, SCHEMA.url, URIRef(f"https://arxiv.org/abs/{pid}")))
        g.add((p, AFB.retrievalStanding, Literal("PDF_FETCHED_SHA256_VERIFIED|NOT_REPRODUCED" if (ROOT / "pdf" / f"{pid}.pdf").exists() else "PDF_PENDING|NOT_REPRODUCED")))
        for tag in paper["tags"]:
            g.add((p, DCTERMS.subject, Literal(tag)))
        dist = slug_iri("distribution", f"paper-{pid.replace('.', '-')}-pdf")
        g.add((dist, RDF.type, DCAT.Distribution))
        g.add((dist, DCTERMS.format, Literal("application/pdf")))
        g.add((dist, DCAT.downloadURL, URIRef(f"https://arxiv.org/pdf/{pid}")))
        g.add((p, DCAT.distribution, dist))
        bench_slug = PAPER_TO_BENCH.get(pid)
        if bench_slug and bench_slug in bench_nodes:
            g.add((p, SCHEMA.about, bench_nodes[bench_slug]))
            g.add((p, DCTERMS.relation, bench_nodes[bench_slug]))
            g.add((p, CITO.providesBackgroundFor, bench_nodes[bench_slug]))
            g.add((bench_nodes[bench_slug], PROV.wasDerivedFrom, p))

        capsule = ROOT / f"{pid}.md"
        if not capsule.exists():
            capsule.write_text(f"# {paper['title']}\n\n- arXiv: `{pid}`\n- Canonical record: https://arxiv.org/abs/{pid}\n- Canonical PDF: https://arxiv.org/pdf/{pid}\n- Standing: `PAPER_ID_ADMITTED|PDF_FETCH_PENDING|NOT_REPRODUCED`\n- ForwardBench tags: {', '.join(paper['tags'])}\n\nInclusion is an EXPLORE literature input; it is not evidence that AutoFDE reproduces the paper's reported result.\n")

    policy = DATA["policy-live-authority"]
    g.add((policy, RDF.type, ODRL.Policy))
    g.add((policy, DCTERMS.title, Literal("Live provider gyms require explicit authority")))
    g.add((root, DCTERMS.accessRights, policy))

    text = g.serialize(format="turtle")
    (ROOT / "papers.ttl").write_text(text)
    check = Graph().parse(ROOT / "papers.ttl", format="turtle")
    return len(check)


def write_queries() -> None:
    q = ROOT / "queries"
    q.mkdir(exist_ok=True)
    (q / "vendors.rq").write_text('''PREFIX afb: <https://github.com/seanchatmangpt/autofde-lab/ns/forwardbench#>
SELECT ?slug ?repo ?path ?requested_ref ?adapter ?smoke ?local_safe ?requires_authority
       (COALESCE(?pin, "") AS ?pinned_revision)
       (COALESCE(?resolution, "UNRESOLVED") AS ?resolution_standing)
       (COALESCE(?smoke_standing, "NOT_RUN") AS ?smoke_standing)
WHERE {
  ?v a afb:VendorProject ; afb:slug ?slug ; afb:repositoryUrl ?repo ;
     afb:vendorPath ?path ; afb:requestedRef ?requested_ref ;
     afb:adapterFamily ?adapter ; afb:smokeProfile ?smoke ;
     afb:localSafe ?local_safe ; afb:requiresAuthority ?requires_authority .
  OPTIONAL { ?v afb:pinnedRevision ?pin . }
  OPTIONAL { ?v afb:resolutionStanding ?resolution . }
  OPTIONAL { ?v afb:smokeStanding ?smoke_standing . }
}
ORDER BY ?slug
''')
    (q / "benchmarks.rq").write_text('''PREFIX afb: <https://github.com/seanchatmangpt/autofde-lab/ns/forwardbench#>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?slug ?title ?adapter ?source_standing ?local_safe ?requires_authority
       (COALESCE(?vendor_slug, "") AS ?vendor_slug)
       (COALESCE(?repo, "") AS ?repo)
       (COALESCE(?path, "") AS ?path)
       (COALESCE(?pin, "") AS ?pinned_revision)
       (COALESCE(?resolution, "UNRESOLVED") AS ?resolution_standing)
       (COALESCE(?smoke_standing, "NOT_RUN") AS ?smoke_standing)
WHERE {
  ?b a afb:Benchmark ; afb:slug ?slug ; dct:title ?title ;
     afb:adapterFamily ?adapter ; afb:sourceStanding ?source_standing ;
     afb:localSafe ?local_safe ; afb:requiresAuthority ?requires_authority .
  OPTIONAL {
    ?b afb:vendorProject ?v .
    ?v afb:slug ?vendor_slug ; afb:repositoryUrl ?repo ; afb:vendorPath ?path .
    OPTIONAL { ?v afb:pinnedRevision ?pin . }
    OPTIONAL { ?v afb:resolutionStanding ?resolution . }
    OPTIONAL { ?v afb:smokeStanding ?smoke_standing . }
  }
}
ORDER BY ?slug
''')
    (q / "papers.rq").write_text('''PREFIX afb: <https://github.com/seanchatmangpt/autofde-lab/ns/forwardbench#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX fabio: <http://purl.org/spar/fabio/>
SELECT ?id ?title ?retrieval (COALESCE(?sha, "") AS ?sha256)
WHERE {
  ?p a fabio:ResearchPaper ; afb:arxivId ?id ; dct:title ?title ; afb:retrievalStanding ?retrieval .
  OPTIONAL { ?p afb:sha256 ?sha . }
}
ORDER BY ?id
''')
    (q / "plans.rq").write_text('''PREFIX afb: <https://github.com/seanchatmangpt/autofde-lab/ns/forwardbench#>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?adapter ?title
WHERE { ?p a afb:ExecutionPlan ; afb:adapterFamily ?adapter ; dct:title ?title . }
ORDER BY ?adapter
''')


def write_templates() -> None:
    t = ROOT / "templates"
    t.mkdir(exist_ok=True)
    (t / "vendors.tsv.tera").write_text('''# slug\trepository\tpath\trequested_ref\tadapter\tsmoke\tlocal_safe\trequires_authority\tpin\tresolution\tsmoke_standing
{%- for row in sparql_results %}
{{ row.slug }}\t{{ row.repo }}\t{{ row.path }}\t{{ row.requested_ref }}\t{{ row.adapter }}\t{{ row.smoke }}\t{{ row.local_safe }}\t{{ row.requires_authority }}\t{{ row.pinned_revision }}\t{{ row.resolution_standing }}\t{{ row.smoke_standing }}
{%- endfor %}
''')
    (t / "registry.json.tera").write_text('''{"schema_version":1,"authority":"SELECT_ONLY","benchmarks":[{%- for row in sparql_results %}{"slug":{{ row.slug | json_encode() }},"title":{{ row.title | json_encode() }},"adapter":{{ row.adapter | json_encode() }},"source_standing":{{ row.source_standing | json_encode() }},"vendor_slug":{{ row.vendor_slug | json_encode() }},"repository":{{ row.repo | json_encode() }},"path":{{ row.path | json_encode() }},"pinned_revision":{{ row.pinned_revision | json_encode() }},"resolution_standing":{{ row.resolution_standing | json_encode() }},"smoke_standing":{{ row.smoke_standing | json_encode() }},"local_safe":{% if row.local_safe == "true" %}true{% else %}false{% endif %},"requires_authority":{% if row.requires_authority == "true" %}true{% else %}false{% endif %}}{% if not loop.last %},{% endif %}{%- endfor %}]}
''')
    (t / "papers.json.tera").write_text('''{"schema_version":1,"papers":[{%- for row in sparql_results %}{"arxiv_id":{{ row.id | json_encode() }},"title":{{ row.title | json_encode() }},"retrieval_standing":{{ row.retrieval | json_encode() }},"sha256":{{ row.sha256 | json_encode() }}}{% if not loop.last %},{% endif %}{%- endfor %}]}
''')
    (t / "paper-ids.txt.tera").write_text('''{%- for row in sparql_results %}{{ row.id }}\n{%- endfor %}''')
    (t / "matrix.md.tera").write_text('''# ForwardBench benchmark matrix

Generated by ggen from `papers.ttl`; do not hand-edit.

| Benchmark | Adapter | Source | Pin | Resolution | Smoke | Local safe | Authority |
|---|---|---|---|---|---|---|---|
{%- for row in sparql_results %}
| `{{ row.slug }}` | {{ row.adapter }} | {{ row.source_standing }} | `{{ row.pinned_revision }}` | {{ row.resolution_standing }} | {{ row.smoke_standing }} | {{ row.local_safe }} | {{ row.requires_authority }} |
{%- endfor %}
''')
    (t / "mcp-tools.json.tera").write_text('''{"schema_version":1,"authority":"SELECT_ONLY","tools":[{"name":"forwardbench.list","effect":"INSPECT"},{"name":"forwardbench.plan","effect":"SELECT"},{"name":"forwardbench.sync_request","effect":"CONSTRUCT_INTENT"}],"benchmark_count":{{ sparql_results | length }}}
''')
    (t / "plans.json.tera").write_text('''{"schema_version":1,"plans":[{%- for row in sparql_results %}{"adapter":{{ row.adapter | json_encode() }},"title":{{ row.title | json_encode() }},"steps":["Observe","SelectAdapter","PrepareSandbox","RunScenario","VerifyEffect","ReceiptTrajectory"]}{% if not loop.last %},{% endif %}{%- endfor %}]}
''')
    (t / "sync-gyms.sh.tera").write_text('''#!/usr/bin/env bash
set -euo pipefail
slug="${1:?usage: sync-gyms.sh <vendor-slug>}"
case "$slug" in
{%- for row in sparql_results %}
  {{ row.slug }})
    git -c submodule.forwardbench-{{ row.slug }}.update=checkout submodule update --init --depth 1 -- {{ row.path | json_encode() }}
    ;;
{%- endfor %}
  *) echo "REFUSED:UNKNOWN_FORWARD_BENCH_VENDOR:$slug" >&2; exit 64 ;;
esac
''')
    (t / "probe-gyms.sh.tera").write_text('''#!/usr/bin/env bash
set -euo pipefail
slug="${1:?usage: probe-gyms.sh <vendor-slug>}"
case "$slug" in
{%- for row in sparql_results %}
  {{ row.slug }})
    test -d {{ row.path | json_encode() }}
    actual="$(git -C {{ row.path | json_encode() }} rev-parse HEAD)"
    expected={{ row.pinned_revision | json_encode() }}
    if [[ -n "$expected" && "$actual" != "$expected" ]]; then echo "REFUSED:GITLINK_DRIFT:$slug:$actual:$expected" >&2; exit 65; fi
    echo "PINNED:$slug:$actual"
    ;;
{%- endfor %}
  *) echo "REFUSED:UNKNOWN_FORWARD_BENCH_VENDOR:$slug" >&2; exit 64 ;;
esac
''')


def write_ggen() -> None:
    (ROOT / "ggen.toml").write_text('''[project]
name = "autofde-forwardbench-corpus"
version = "0.1.0"
description = "RDF-first ForwardBench paper/gym registry and generated AutoFDE integration surfaces."
authors = ["AutoFDE Lab"]
license = "MIT"

[ontology]
source = "papers.ttl"
imports = ["ontology/forwardbench-vocab.ttl", "gym-lock.ttl", "paper-lock.ttl", "smoke-lock.ttl"]
base_iri = "https://github.com/seanchatmangpt/autofde-lab/data/forwardbench/"

[ontology.prefixes]
afb = "https://github.com/seanchatmangpt/autofde-lab/ns/forwardbench#"
dct = "http://purl.org/dc/terms/"
fabio = "http://purl.org/spar/fabio/"
bibo = "http://purl.org/ontology/bibo/"
cito = "http://purl.org/spar/cito/"
doap = "http://usefulinc.com/ns/doap#"
prov = "http://www.w3.org/ns/prov#"
pplan = "http://purl.org/net/p-plan#"
dcat = "http://www.w3.org/ns/dcat#"
skos = "http://www.w3.org/2004/02/skos/core#"
schema = "https://schema.org/"

[generation]
output_dir = "generated/forwardbench/"

[[generation.rules]]
name = "vendors-tsv"
query = { file = "queries/vendors.rq" }
template = { file = "templates/vendors.tsv.tera" }
output_file = "vendors.tsv"
mode = "Overwrite"

[[generation.rules]]
name = "registry-json"
query = { file = "queries/benchmarks.rq" }
template = { file = "templates/registry.json.tera" }
output_file = "registry.json"
mode = "Overwrite"

[[generation.rules]]
name = "papers-json"
query = { file = "queries/papers.rq" }
template = { file = "templates/papers.json.tera" }
output_file = "papers.json"
mode = "Overwrite"

[[generation.rules]]
name = "paper-ids"
query = { file = "queries/papers.rq" }
template = { file = "templates/paper-ids.txt.tera" }
output_file = "paper-ids.txt"
mode = "Overwrite"

[[generation.rules]]
name = "benchmark-matrix"
query = { file = "queries/benchmarks.rq" }
template = { file = "templates/matrix.md.tera" }
output_file = "BENCHMARK_MATRIX.md"
mode = "Overwrite"

[[generation.rules]]
name = "mcp-tools"
query = { file = "queries/benchmarks.rq" }
template = { file = "templates/mcp-tools.json.tera" }
output_file = "mcp-tools.json"
mode = "Overwrite"

[[generation.rules]]
name = "plans"
query = { file = "queries/plans.rq" }
template = { file = "templates/plans.json.tera" }
output_file = "plans.json"
mode = "Overwrite"

[[generation.rules]]
name = "sync-gyms"
query = { file = "queries/vendors.rq" }
template = { file = "templates/sync-gyms.sh.tera" }
output_file = "sync-gyms.sh"
mode = "Overwrite"

[[generation.rules]]
name = "probe-gyms"
query = { file = "queries/vendors.rq" }
template = { file = "templates/probe-gyms.sh.tera" }
output_file = "probe-gyms.sh"
mode = "Overwrite"

[validation]
shacl = ["ontology/papers-shapes.ttl"]
strict_mode = true

[sync]
enabled = true
on_change = "manual"
validate_after = true
conflict_mode = "fail"

[rdf]
formats = ["turtle"]
default_format = "turtle"
strict_validation = false

[templates]
enable_caching = true
auto_reload = true
''')
    for lock in ["gym-lock.ttl", "paper-lock.ttl", "smoke-lock.ttl"]:
        p = ROOT / lock
        if not p.exists():
            p.write_text('@prefix afb: <https://github.com/seanchatmangpt/autofde-lab/ns/forwardbench#> .\n')


def write_adapter() -> None:
    pkg = REPO / "src" / "autofde_lab" / "forwardbench"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text('''"""Bounded SELECT-only ForwardBench integration."""
from .registry import CandidatePlan, ForwardBenchRegistry, Subject
__all__ = ["CandidatePlan", "ForwardBenchRegistry", "Subject"]
''')
    (pkg / "registry.py").write_text('''from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Subject:
    slug: str
    title: str
    adapter: str
    source_standing: str
    vendor_slug: str
    repository: str
    path: str
    pinned_revision: str
    resolution_standing: str
    smoke_standing: str
    local_safe: bool
    requires_authority: bool

    @property
    def observed_standing(self) -> str:
        if self.smoke_standing != "NOT_RUN":
            return self.smoke_standing
        if self.resolution_standing == "PINNED":
            return "PINNED"
        return self.source_standing


@dataclass(frozen=True)
class CandidatePlan:
    status: str
    reason: str
    subject: str
    adapter: str = ""
    commands: tuple[str, ...] = ()
    standing: str = "UNKNOWN"


class ForwardBenchRegistry:
    """Reads a ggen-manufactured registry and returns candidate plans only.

    No method in this class executes a subprocess, cloud API, Terraform,
    Kubernetes, MCP server, or benchmark. It is deliberately SELECT-only.
    """

    def __init__(self, registry_path: str | Path):
        payload = json.loads(Path(registry_path).read_text())
        if payload.get("authority") != "SELECT_ONLY":
            raise ValueError("REFUSED:FORWARDBENCH_REGISTRY_AUTHORITY_DRIFT")
        self._subjects = {row["slug"]: Subject(**row) for row in payload["benchmarks"]}

    def list(self) -> list[Subject]:
        return [self._subjects[k] for k in sorted(self._subjects)]

    def resolve(self, query: str) -> Subject | None:
        key = query.strip().lower()
        if key in self._subjects:
            return self._subjects[key]
        matches = [s for s in self.list() if key and (key in s.slug.lower() or key in s.title.lower())]
        return matches[0] if len(matches) == 1 else None

    def plan(self, query: str) -> CandidatePlan:
        subject = self.resolve(query)
        if subject is None:
            return CandidatePlan("REFUSED", "REFUSED:UNKNOWN_OR_AMBIGUOUS_FORWARD_BENCH", query)
        if not subject.vendor_slug or not subject.repository:
            return CandidatePlan("REFUSED", "REFUSED:UNKNOWN_REPOSITORY", subject.slug, subject.adapter, standing=subject.observed_standing)
        if subject.requires_authority:
            return CandidatePlan("REFUSED", "REFUSED:LIVE_AUTHORITY_REQUIRED", subject.slug, subject.adapter, standing=subject.observed_standing)
        sync = f"bash docs/papers/generated/forwardbench/sync-gyms.sh {subject.vendor_slug}"
        probe = f"bash docs/papers/generated/forwardbench/probe-gyms.sh {subject.vendor_slug}"
        return CandidatePlan(
            "CANDIDATE",
            "SELECT_ONLY:NO_ACTUATION",
            subject.slug,
            subject.adapter,
            (sync, probe),
            subject.observed_standing,
        )
''')
    scripts = REPO / "scripts"
    scripts.mkdir(exist_ok=True)
    (scripts / "forwardbench.py").write_text('''#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from autofde_lab.forwardbench import ForwardBenchRegistry

p = argparse.ArgumentParser()
p.add_argument("--registry", default="docs/papers/generated/forwardbench/registry.json")
sub = p.add_subparsers(dest="cmd", required=True)
sub.add_parser("list")
plan = sub.add_parser("plan")
plan.add_argument("subject")
a = p.parse_args()
r = ForwardBenchRegistry(a.registry)
if a.cmd == "list":
    print(json.dumps([s.__dict__ | {"observed_standing": s.observed_standing} for s in r.list()], indent=2, sort_keys=True))
else:
    print(json.dumps(r.plan(a.subject).__dict__, indent=2, sort_keys=True))
''')
    tests = REPO / "tests" / "forwardbench"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_registry.py").write_text('''import json
from pathlib import Path

from autofde_lab.forwardbench import ForwardBenchRegistry

REGISTRY = Path("docs/papers/generated/forwardbench/registry.json")


def test_registry_is_broad_and_unique():
    data = json.loads(REGISTRY.read_text())
    rows = data["benchmarks"]
    assert data["authority"] == "SELECT_ONLY"
    assert len(rows) >= 60
    assert len({r["slug"] for r in rows}) == len(rows)


def test_cube_returns_candidate_not_execution():
    plan = ForwardBenchRegistry(REGISTRY).plan("cube")
    assert plan.status == "CANDIDATE"
    assert plan.reason == "SELECT_ONLY:NO_ACTUATION"
    assert plan.commands


def test_live_cloud_goat_requires_authority():
    plan = ForwardBenchRegistry(REGISTRY).plan("cloudgoat")
    assert plan.status == "REFUSED"
    assert plan.reason == "REFUSED:LIVE_AUTHORITY_REQUIRED"


def test_unknown_subject_is_typed_refusal():
    plan = ForwardBenchRegistry(REGISTRY).plan("definitely-not-a-benchmark")
    assert plan.status == "REFUSED"
    assert plan.reason.startswith("REFUSED:")
''')


def write_docs(papers: list[dict], benchmarks: list[dict]) -> None:
    (ROOT / "README.md").write_text(f'''# ForwardBench / AutoFDE research corpus

This directory is an **EXPLORE** source surface for papers, executable agent/cloud gyms, and ggen-manufactured ForwardBench integration.

## Canonical source

`papers.ttl` is the semantic source of truth. It currently describes **{len(papers)} papers**, **{len(benchmarks)} logical benchmark subjects**, and **{len(VENDORS)} physical vendor projects**. Public vocabularies carry scholarly/software/provenance semantics; the small `afb:` vocabulary is limited to execution metadata that those standards do not define.

`ggen sync run` projects the graph into `generated/forwardbench/`: registry, plans, MCP tool declarations, benchmark matrix, paper manifest, and lazy submodule sync/probe helpers. Do not manually fork those projections.

Observed facts do not get written back into the declaration graph. Exact git pins, PDF hashes, and executed smoke standing live in `gym-lock.ttl`, `paper-lock.ttl`, and `smoke-lock.ttl` respectively and are imported by ggen.

## Authority

The generated AutoFDE adapter is SELECT-only. Cloud-security labs that require AWS/Azure/GCP authority remain `REFUSED:LIVE_AUTHORITY_REQUIRED` until a named allowlisted environment is explicitly authorized. Vendoring a repository is not permission to deploy it.

## Standing ladder

`UNKNOWN_REPOSITORY -> PINNED -> BOOTSTRAPS -> SCENARIO_RUNS -> AUTOFDE_ADAPTER_ALIVE`.

A higher standing is recorded only from exact execution evidence. Paper retrieval and paper-result reproduction are separate: a vendored PDF remains `NOT_REPRODUCED` until its reported result is actually reproduced.
''')
    (ROOT / "FORWARDBENCH.md").write_text('''# ForwardBench manufacturing contract

`papers.ttl` models papers, benchmark subjects, official software projects, adapter families, and generic P-PLAN/PROV execution plans. ggen performs CONSTRUCT/SELECT/Tera manufacture; AutoFDE Lab selects candidate interactions; no generated MCP or registry surface owns DO authority.

Preferred interoperability order: **CUBE -> Harbor -> BrowserGym -> MCP -> bounded native adapter**. CUBE is preferred because it standardizes Tool/Task/Benchmark/Observation/Action. Harbor collapses terminal/container benchmarks behind one harness. BrowserGym collapses web/enterprise browser benchmarks behind Gymnasium-compatible environments.

The design intentionally keeps all benchmark submodules lazy (`update = none`) so ordinary recursive project checkout does not download the entire corpus. `generated/forwardbench/sync-gyms.sh <vendor>` materializes only a requested subject.
''')


def main() -> None:
    papers = load_papers()
    benchmarks = build_benchmarks()
    assert len(papers) >= 50, len(papers)
    assert len(benchmarks) >= 60, len(benchmarks)
    assert len(VENDORS) >= 40, len(VENDORS)
    write_vocab()
    write_queries()
    write_templates()
    write_ggen()
    triples = write_graph(papers, benchmarks)
    write_adapter()
    write_docs(papers, benchmarks)
    assert triples > 2000, triples
    print(f"PAPERS_TTL_ALIVE triples={triples} papers={len(papers)} benchmarks={len(benchmarks)} vendors={len(VENDORS)}")


if __name__ == "__main__":
    main()
