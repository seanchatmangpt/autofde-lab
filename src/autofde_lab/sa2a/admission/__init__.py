"""Admission layer package for SA2A (RFC-SA2A-001 v26.9.16).

Provides:
- AdmissionPipeline: Full reference 10-stage admission pipeline (§13, §19, §62).
- AdmissionResult, AdmissionReceipt: Formal admission outcome and cryptographically bound receipt.
- Canonicalizer, SHACL, ShEx, Datalog, and N3 layers.
"""

from autofde_lab.sa2a.admission.canonicalizer import (
    canonicalize_graph,
    compute_graph_digest,
)
from autofde_lab.sa2a.admission.datalog_layer import (
    DatalogAtom,
    DatalogEngine,
    DatalogRule,
)
from autofde_lab.sa2a.admission.n3_layer import (
    CandidateDerivation,
    N3ImplicationRule,
    N3RuleEngine,
)
from autofde_lab.sa2a.admission.pipeline import (
    REFUSED_DATALOG_FAILURE,
    REFUSED_FALSIFIER,
    REFUSED_IDENTITY,
    REFUSED_META_RIGOR,
    REFUSED_N3_FAILURE,
    REFUSED_NAMESPACE,
    REFUSED_PARSE_FAILURE,
    REFUSED_PROVENANCE,
    REFUSED_SHACL,
    REFUSED_STRUCTURE,
    AdmissionPipeline,
    AdmissionReceipt,
    AdmissionResult,
    IdentityPolicy,
    MetaAdmissionPolicy,
    ProvenancePolicy,
    SparqlFalsifier,
)
from autofde_lab.sa2a.admission.shacl_layer import (
    ShaclValidationReport,
    ShaclValidator,
)
from autofde_lab.sa2a.admission.shex_layer import (
    NodeKind,
    PredicateConstraint,
    ShexValidationReport,
    ShexValidator,
    StructuralShape,
)

__all__ = [
    "AdmissionPipeline",
    "AdmissionResult",
    "AdmissionReceipt",
    "IdentityPolicy",
    "ProvenancePolicy",
    "MetaAdmissionPolicy",
    "SparqlFalsifier",
    "canonicalize_graph",
    "compute_graph_digest",
    "ShaclValidator",
    "ShaclValidationReport",
    "ShexValidator",
    "ShexValidationReport",
    "StructuralShape",
    "PredicateConstraint",
    "NodeKind",
    "DatalogAtom",
    "DatalogRule",
    "DatalogEngine",
    "CandidateDerivation",
    "N3ImplicationRule",
    "N3RuleEngine",
    "REFUSED_PARSE_FAILURE",
    "REFUSED_IDENTITY",
    "REFUSED_NAMESPACE",
    "REFUSED_STRUCTURE",
    "REFUSED_SHACL",
    "REFUSED_DATALOG_FAILURE",
    "REFUSED_N3_FAILURE",
    "REFUSED_FALSIFIER",
    "REFUSED_PROVENANCE",
    "REFUSED_META_RIGOR",
]
