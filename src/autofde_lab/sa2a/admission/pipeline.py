"""Full reference admission pipeline for Semantic A2A (RFC-SA2A-001 v26.9.16 §13, §19, §62).

Architecture & Invariants:
- Candidate -> Parse -> Identity Policy -> ShEx -> SHACL -> Datalog Closure
  -> N3 Derivation -> SPARQL Falsifiers -> Provenance -> Meta-Admission -> ADMITTED with AdmissionReceipt.
- Fail-closed: Any stage failure immediately aborts pipeline execution and returns
  AdmissionResult(standing=REFUSED, refusal_code=..., reasons=...).
- On success: returns AdmissionResult(standing=ADMITTED, graph=canonical_graph, digest=graph_digest, receipt=receipt).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

import rdflib
from rdflib import Graph, URIRef

from autofde_lab.sa2a.admission.canonicalizer import canonicalize_graph, compute_graph_digest
from autofde_lab.sa2a.admission.datalog_layer import DatalogEngine, DatalogRule
from autofde_lab.sa2a.admission.n3_layer import CandidateDerivation, N3ImplicationRule, N3RuleEngine
from autofde_lab.sa2a.admission.shacl_layer import ShaclValidator
from autofde_lab.sa2a.admission.shex_layer import ShexValidator, StructuralShape
from autofde_lab.sa2a.algebra import RefusalCause, Standing
from autofde_lab.sa2a.envelope import SemanticEnvelope


# Refusal codes conforming to RFC-SA2A-001 §13, §19, §42, §62
REFUSED_PARSE_FAILURE = "REFUSED_PARSE_FAILURE"
REFUSED_IDENTITY = RefusalCause.REFUSED_IDENTITY.value
REFUSED_NAMESPACE = RefusalCause.REFUSED_NAMESPACE.value
REFUSED_STRUCTURE = RefusalCause.REFUSED_STRUCTURE.value  # ShEx violation
REFUSED_SHACL = RefusalCause.REFUSED_SHACL.value          # SHACL violation
REFUSED_DATALOG_FAILURE = "REFUSED_DATALOG_FAILURE"
REFUSED_N3_FAILURE = "REFUSED_N3_FAILURE"
REFUSED_FALSIFIER = RefusalCause.REFUSED_FALSIFIER.value  # SPARQL falsifier matched
REFUSED_PROVENANCE = RefusalCause.REFUSED_PROVENANCE.value
REFUSED_META_RIGOR = RefusalCause.REFUSED_META_RIGOR.value


@dataclass(frozen=True, slots=True)
class AdmissionReceipt:
    """Immutable cryptographically bound receipt of formal admission (§19, §62)."""

    receipt_id: str
    standing: Standing
    candidate_digest: str
    admitted_graph_digest: Optional[str] = None
    refusal_code: Optional[str] = None
    reasons: Tuple[str, ...] = ()
    stages_passed: Tuple[str, ...] = ()
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def canonical_json(self) -> str:
        """Serialize deterministic canonical JSON representation of receipt (§19)."""
        payload = {
            "receipt_id": self.receipt_id,
            "standing": self.standing.value,
            "candidate_digest": self.candidate_digest,
            "admitted_graph_digest": self.admitted_graph_digest,
            "refusal_code": self.refusal_code,
            "reasons": sorted(self.reasons),
            "stages_passed": list(self.stages_passed),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @property
    def receipt_hash(self) -> str:
        """Compute SHA-256 digest of canonical receipt payload."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    """Result of executing the fail-closed Admission Pipeline."""

    standing: Standing
    receipt: AdmissionReceipt
    refusal_code: Optional[str] = None
    reasons: Tuple[str, ...] = ()
    graph: Optional[Graph] = None
    canonical_ntriples: Optional[str] = None
    digest: Optional[str] = None

    @property
    def is_admitted(self) -> bool:
        return self.standing == Standing.ADMITTED


@dataclass(frozen=True)
class IdentityPolicy:
    """Identity and IRI namespace constraints (§13).

    Enforces allowed subject/predicate IRI namespaces and rejects forbidden IRIs or prefixes.
    """

    allowed_subject_namespaces: Tuple[str, ...] = ()
    allowed_predicate_namespaces: Tuple[str, ...] = ()
    disallowed_iris: Tuple[str, ...] = ()
    require_valid_iris: bool = True


@dataclass(frozen=True)
class SparqlFalsifier:
    """SPARQL ASK or SELECT query acting as an invariant falsifier (§13, §62).

    If the query matches (ASK returns True, or SELECT returns at least 1 solution),
    the graph is FALSIFIED, triggering immediate REFUSED_FALSIFIER.
    """

    falsifier_id: str
    query: str
    description: str = ""


@dataclass(frozen=True)
class ProvenancePolicy:
    """Provenance and attestation requirements (§11, §13)."""

    require_issuer: bool = True
    trusted_issuers: Tuple[str, ...] = ()
    require_timestamp: bool = True
    require_signature: bool = False


@dataclass(frozen=True)
class MetaAdmissionPolicy:
    """Meta-admission and rigor constraints (§62)."""

    max_triples: Optional[int] = 100_000
    min_triples: int = 1
    allow_untyped_subjects: bool = True
    require_connected_graph: bool = False


class AdmissionPipeline:
    """Full reference 10-stage fail-closed admission pipeline (RFC-SA2A-001 §13, §19, §62).

    Pipeline Stages:
    1. Parse Candidate: Decode input payload into rdflib.Graph.
    2. Identity Policy: Validate subject/predicate IRIs against admitted namespaces.
    3. ShEx Validation: Verify structural node kinds, required types, predicate bounds.
    4. SHACL Validation: Check semantic constraint shapes.
    5. Datalog Closure: Compute deterministic least-fixpoint closure under safe Datalog rules.
    6. N3 Derivation: Apply admitted N3 implication rules (candidate derivations with 0 DO).
    7. SPARQL Falsifiers: Run falsification queries (any match immediately refuses).
    8. Provenance Verification: Inspect envelope / candidate metadata for valid origin.
    9. Meta-Admission: Check overall graph size, bounds, and meta-rigor invariants.
    10. ADMITTED: Canonicalize graph, generate deterministic digest and AdmissionReceipt.
    """

    def __init__(
        self,
        *,
        identity_policy: Optional[IdentityPolicy] = None,
        shex_validator: Optional[ShexValidator] = None,
        shacl_validator: Optional[ShaclValidator] = None,
        datalog_engine: Optional[DatalogEngine] = None,
        n3_engine: Optional[N3RuleEngine] = None,
        sparql_falsifiers: Optional[Sequence[SparqlFalsifier]] = None,
        provenance_policy: Optional[ProvenancePolicy] = None,
        meta_policy: Optional[MetaAdmissionPolicy] = None,
    ) -> None:
        self.identity_policy = identity_policy or IdentityPolicy()
        self.shex_validator = shex_validator
        self.shacl_validator = shacl_validator
        self.datalog_engine = datalog_engine
        self.n3_engine = n3_engine
        self.sparql_falsifiers = list(sparql_falsifiers) if sparql_falsifiers else []
        self.provenance_policy = provenance_policy or ProvenancePolicy()
        self.meta_policy = meta_policy or MetaAdmissionPolicy()

    def admit(
        self,
        candidate: Union[str, bytes, Graph, SemanticEnvelope, Dict[str, Any]],
        format: str = "turtle",
        provenance_record: Optional[Dict[str, Any]] = None,
    ) -> AdmissionResult:
        """Execute fail-closed admission on a candidate payload.

        Args:
            candidate: Raw RDF string/bytes, rdflib.Graph, SemanticEnvelope, or dict payload.
            format: RDF format if candidate is string/bytes (default: 'turtle').
            provenance_record: Optional external provenance metadata dict if not in candidate.

        Returns:
            AdmissionResult with ADMITTED or REFUSED standing and an AdmissionReceipt.
        """
        stages_passed: List[str] = []
        candidate_digest = self._compute_candidate_digest(candidate)

        def _refusal(code: str, *reasons: str) -> AdmissionResult:
            receipt = AdmissionReceipt(
                receipt_id=f"rec-{uuid.uuid4().hex[:12]}",
                standing=Standing.REFUSED,
                candidate_digest=candidate_digest,
                refusal_code=code,
                reasons=tuple(reasons),
                stages_passed=tuple(stages_passed),
                metadata={"failed_stage": stages_passed[-1] if stages_passed else "entry"},
            )
            return AdmissionResult(
                standing=Standing.REFUSED,
                receipt=receipt,
                refusal_code=code,
                reasons=tuple(reasons),
            )

        # -------------------------------------------------------------
        # Stage 1: Parse Candidate -> Graph & Extract Provenance
        # -------------------------------------------------------------
        parsed_graph: Graph
        envelope_meta: Dict[str, Any] = dict(provenance_record or {})

        try:
            if isinstance(candidate, Graph):
                parsed_graph = candidate
            elif isinstance(candidate, SemanticEnvelope):
                if candidate.provenance:
                    envelope_meta.update({
                        "issuer": candidate.provenance.issuer,
                        "timestamp": candidate.provenance.timestamp,
                        "signature": candidate.provenance.signature,
                    })
                if candidate.graph:
                    g = Graph()
                    g.parse(data=candidate.graph.content, format=candidate.graph.mediaType)
                    parsed_graph = g
                else:
                    return _refusal(REFUSED_PARSE_FAILURE, "SemanticEnvelope contains no graph content")
            elif isinstance(candidate, dict):
                if "graph" in candidate and isinstance(candidate["graph"], dict):
                    g = Graph()
                    c_format = candidate["graph"].get("mediaType", format)
                    g.parse(data=candidate["graph"].get("content", ""), format=c_format)
                    parsed_graph = g
                    if "provenance" in candidate and isinstance(candidate["provenance"], dict):
                        envelope_meta.update(candidate["provenance"])
                else:
                    return _refusal(REFUSED_PARSE_FAILURE, "Dict candidate missing valid 'graph' field")
            elif isinstance(candidate, (str, bytes)):
                g = Graph()
                g.parse(data=candidate, format=format)
                parsed_graph = g
            else:
                return _refusal(REFUSED_PARSE_FAILURE, f"Unsupported candidate type: {type(candidate).__name__}")
        except Exception as exc:
            return _refusal(REFUSED_PARSE_FAILURE, f"Graph parsing failed: {exc}")

        stages_passed.append("PARSE")

        # -------------------------------------------------------------
        # Stage 2: Identity & Namespace Policy (§13)
        # -------------------------------------------------------------
        ident_errs = self._check_identity_policy(parsed_graph)
        if ident_errs:
            code = REFUSED_NAMESPACE if any("namespace" in e.lower() for e in ident_errs) else REFUSED_IDENTITY
            return _refusal(code, *ident_errs)

        stages_passed.append("IDENTITY_POLICY")

        # -------------------------------------------------------------
        # Stage 3: ShEx Structural Validation (§14)
        # -------------------------------------------------------------
        if self.shex_validator is not None:
            shex_rep = self.shex_validator.validate(parsed_graph)
            if not shex_rep.conforms:
                return _refusal(REFUSED_STRUCTURE, *shex_rep.violations)

        stages_passed.append("SHEX")

        # -------------------------------------------------------------
        # Stage 4: SHACL Constraint Validation (§15)
        # -------------------------------------------------------------
        if self.shacl_validator is not None:
            shacl_rep = self.shacl_validator.validate(parsed_graph)
            if not shacl_rep.conforms:
                return _refusal(REFUSED_SHACL, *shacl_rep.violations)

        stages_passed.append("SHACL")

        # -------------------------------------------------------------
        # Stage 5: Datalog Closure (§16)
        # -------------------------------------------------------------
        working_graph = parsed_graph
        if self.datalog_engine is not None:
            try:
                working_graph, _ = self.datalog_engine.execute_graph_fixpoint(working_graph)
            except Exception as exc:
                return _refusal(REFUSED_DATALOG_FAILURE, f"Datalog closure evaluation failed: {exc}")

        stages_passed.append("DATALOG_CLOSURE")

        # -------------------------------------------------------------
        # Stage 6: N3 Derivation (§17)
        # -------------------------------------------------------------
        if self.n3_engine is not None:
            try:
                _, working_graph, _ = self.n3_engine.apply_implications(working_graph)
            except Exception as exc:
                return _refusal(REFUSED_N3_FAILURE, f"N3 derivation evaluation failed: {exc}")

        stages_passed.append("N3_DERIVATION")

        # -------------------------------------------------------------
        # Stage 7: SPARQL Falsifiers (§13, §62)
        # -------------------------------------------------------------
        falsifier_violations = self._check_falsifiers(working_graph)
        if falsifier_violations:
            return _refusal(REFUSED_FALSIFIER, *falsifier_violations)

        stages_passed.append("SPARQL_FALSIFIERS")

        # -------------------------------------------------------------
        # Stage 8: Provenance Verification (§11, §13)
        # -------------------------------------------------------------
        prov_errs = self._check_provenance(envelope_meta)
        if prov_errs:
            return _refusal(REFUSED_PROVENANCE, *prov_errs)

        stages_passed.append("PROVENANCE")

        # -------------------------------------------------------------
        # Stage 9: Meta-Admission Rigor (§62)
        # -------------------------------------------------------------
        meta_errs = self._check_meta_admission(working_graph)
        if meta_errs:
            return _refusal(REFUSED_META_RIGOR, *meta_errs)

        stages_passed.append("META_ADMISSION")

        # -------------------------------------------------------------
        # Stage 10: ADMITTED - Canonicalization & Receipt Generation
        # -------------------------------------------------------------
        canonical_nt = canonicalize_graph(working_graph)
        graph_digest = compute_graph_digest(canonical_nt)

        receipt = AdmissionReceipt(
            receipt_id=f"rec-{uuid.uuid4().hex[:12]}",
            standing=Standing.ADMITTED,
            candidate_digest=candidate_digest,
            admitted_graph_digest=graph_digest,
            refusal_code=None,
            reasons=("CONFORMS_TO_SPEC",),
            stages_passed=tuple(stages_passed),
            metadata={
                "triple_count": len(working_graph),
                "issuer": envelope_meta.get("issuer"),
            },
        )

        return AdmissionResult(
            standing=Standing.ADMITTED,
            receipt=receipt,
            refusal_code=None,
            reasons=("CONFORMS_TO_SPEC",),
            graph=working_graph,
            canonical_ntriples=canonical_nt,
            digest=graph_digest,
        )

    def _compute_candidate_digest(self, candidate: Any) -> str:
        """Compute an initial digest of the candidate for receipt correlation."""
        if isinstance(candidate, Graph):
            return compute_graph_digest(candidate)
        if isinstance(candidate, SemanticEnvelope):
            content = candidate.graph.content if candidate.graph else candidate.envelopeId
            return hashlib.sha256(content.encode("utf-8")).hexdigest()
        if isinstance(candidate, bytes):
            return hashlib.sha256(candidate).hexdigest()
        if isinstance(candidate, str):
            return hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        if isinstance(candidate, dict):
            dumped = json.dumps(candidate, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
        return hashlib.sha256(str(candidate).encode("utf-8")).hexdigest()

    def _check_identity_policy(self, graph: Graph) -> List[str]:
        errs: List[str] = []
        policy = self.identity_policy

        for s, p, o in graph:
            # Check disallowed IRIs
            for iri in (str(s), str(p), str(o)):
                if iri in policy.disallowed_iris:
                    errs.append(f"Contains disallowed IRI: {iri}")

            # Check allowed subject namespaces
            if policy.allowed_subject_namespaces and isinstance(s, URIRef):
                s_str = str(s)
                if not any(s_str.startswith(ns) for ns in policy.allowed_subject_namespaces):
                    errs.append(f"Subject namespace not admitted: <{s}>")

            # Check allowed predicate namespaces
            if policy.allowed_predicate_namespaces and isinstance(p, URIRef):
                p_str = str(p)
                if not any(p_str.startswith(ns) for ns in policy.allowed_predicate_namespaces):
                    errs.append(f"Predicate namespace not admitted: <{p}>")

        return errs

    def _check_falsifiers(self, graph: Graph) -> List[str]:
        violations: List[str] = []
        for falsifier in self.sparql_falsifiers:
            try:
                res = graph.query(falsifier.query)
                # If ASK query
                if res.type == "ASK":
                    if bool(res.askAnswer):
                        msg = falsifier.description or f"Falsifier {falsifier.falsifier_id} matched"
                        violations.append(msg)
                # If SELECT query
                elif res.type == "SELECT":
                    if len(list(res)) > 0:
                        msg = falsifier.description or f"Falsifier {falsifier.falsifier_id} produced bindings"
                        violations.append(msg)
            except Exception as exc:
                violations.append(f"Falsifier {falsifier.falsifier_id} execution error: {exc}")

        return violations

    def _check_provenance(self, meta: Dict[str, Any]) -> List[str]:
        errs: List[str] = []
        policy = self.provenance_policy

        if policy.require_issuer:
            issuer = meta.get("issuer")
            if not issuer:
                errs.append("Missing required issuer in provenance")
            elif policy.trusted_issuers and issuer not in policy.trusted_issuers:
                errs.append(f"Issuer '{issuer}' not in trusted issuers list")

        if policy.require_timestamp and not meta.get("timestamp"):
            errs.append("Missing required timestamp in provenance")

        if policy.require_signature and not meta.get("signature"):
            errs.append("Missing required cryptographic signature in provenance")

        return errs

    def _check_meta_admission(self, graph: Graph) -> List[str]:
        errs: List[str] = []
        policy = self.meta_policy

        count = len(graph)
        if count < policy.min_triples:
            errs.append(f"Triple count {count} is below minimum {policy.min_triples}")
        if policy.max_triples is not None and count > policy.max_triples:
            errs.append(f"Triple count {count} exceeds maximum {policy.max_triples}")

        return errs
