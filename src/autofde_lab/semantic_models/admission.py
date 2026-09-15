"""Fail-closed admission from Candidate(O*) into admitted O*.

Statistical scores are deliberately absent from this module.  A classifier, DSPy program,
or TPOT pipeline can prioritize a candidate; none can override ontology/provenance/SHACL
constraints.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from .contracts import AdmissionReceipt, AdmissionStanding, CandidateGraphDelta


@dataclass(frozen=True)
class AdmissionDecision:
    receipt: AdmissionReceipt
    canonical_ntriples: str | None


class SemanticAdmissionCourt:
    """Admit candidate triples only when formal constraints close."""

    def __init__(
        self,
        *,
        known_predicates: Iterable[str],
        shapes_turtle: str | None = None,
    ) -> None:
        self._known_predicates = frozenset(known_predicates)
        self._shapes_turtle = shapes_turtle
        if not self._known_predicates:
            raise ValueError(
                "known_predicates must be non-empty; admission may not be open-world"
            )

    def decide(self, candidate: CandidateGraphDelta) -> AdmissionDecision:
        reasons: list[str] = []
        unknown = sorted(
            {triple.predicate for triple in candidate.triples} - self._known_predicates
        )
        if unknown:
            reasons.append("UNSUPPORTED_PREDICATE:" + ",".join(unknown))
        if not candidate.source_iris:
            reasons.append("MISSING_PROVENANCE")

        graph = None
        canonical = None
        shacl_conforms: bool | None = None
        if not reasons:
            graph = self._to_graph(candidate)
            canonical = self._canonical_ntriples(graph)
            if self._shapes_turtle is not None:
                shacl_conforms, report = self._validate_shacl(graph)
                if not shacl_conforms:
                    reasons.append("SHACL_VIOLATION:" + report)

        standing = AdmissionStanding.REFUSED if reasons else AdmissionStanding.ADMITTED
        graph_hash = (
            hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if canonical is not None and standing is AdmissionStanding.ADMITTED
            else None
        )
        receipt_payload = {
            "standing": standing.value,
            "candidate_hash": candidate.candidate_hash,
            "graph_hash": graph_hash,
            "shacl_conforms": shacl_conforms,
            "reasons": sorted(reasons),
            "source_iris": sorted(set(candidate.source_iris)),
            "admitted_triple_count": len(candidate.triples)
            if standing is AdmissionStanding.ADMITTED
            else 0,
        }
        receipt_id = hashlib.sha256(
            json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        receipt = AdmissionReceipt(receipt_id=receipt_id, **receipt_payload)
        return AdmissionDecision(
            receipt=receipt,
            canonical_ntriples=canonical
            if standing is AdmissionStanding.ADMITTED
            else None,
        )

    @staticmethod
    def _to_graph(candidate: CandidateGraphDelta):
        try:
            from rdflib import Graph, Literal, URIRef
        except ImportError as exc:  # pragma: no cover - dependency boundary
            raise RuntimeError(
                "semantic admission requires the 'ofmf' extra (rdflib)"
            ) from exc

        graph = Graph()
        for triple in candidate.triples:
            subject = URIRef(triple.subject)
            predicate = URIRef(triple.predicate)
            if triple.object_kind == "iri":
                obj = URIRef(triple.object)
            else:
                datatype = URIRef(triple.datatype) if triple.datatype else None
                obj = Literal(triple.object, datatype=datatype, lang=triple.language)
            graph.add((subject, predicate, obj))
        return graph

    @staticmethod
    def _canonical_ntriples(graph) -> str:
        raw = graph.serialize(format="nt")
        lines = sorted(line.strip() for line in raw.splitlines() if line.strip())
        return "\n".join(lines) + ("\n" if lines else "")

    def _validate_shacl(self, graph) -> tuple[bool, str]:
        try:
            from pyshacl import validate
            from rdflib import Graph
        except ImportError as exc:  # pragma: no cover - dependency boundary
            raise RuntimeError(
                "SHACL admission requires the 'ofmf' extra (pyshacl, rdflib)"
            ) from exc

        shapes = Graph().parse(data=self._shapes_turtle, format="turtle")
        conforms, _, report_text = validate(
            graph,
            shacl_graph=shapes,
            inference="none",
            abort_on_first=False,
            allow_infos=False,
            allow_warnings=False,
        )
        report = " ".join(str(report_text).split())
        return bool(conforms), report
