"""No-network demonstration of O -> Candidate(O*) -> admission -> receipt."""

from autofde_lab.semantic_models import (
    AdmissionStanding,
    CandidateGraphDelta,
    SemanticAdmissionCourt,
    SemanticModelPipeline,
    SemanticTriple,
)

PREDICATE = "urn:example:usesFormalism"


def producer(observation: str, ontology_context: str, provenance_context: str):
    del observation, ontology_context
    return CandidateGraphDelta(
        observation_id="urn:observation:fond-hddl",
        triples=(
            SemanticTriple(
                subject="urn:system:autofde",
                predicate=PREDICATE,
                object="urn:formalism:FOND",
            ),
            SemanticTriple(
                subject="urn:system:autofde",
                predicate=PREDICATE,
                object="urn:formalism:HDDL",
            ),
        ),
        source_iris=(provenance_context,),
        generator_id="deterministic-example",
        generator_revision="v1",
    )


court = SemanticAdmissionCourt(known_predicates={PREDICATE})
pipeline = SemanticModelPipeline(producer=producer, admission_court=court)
result = pipeline.run(
    observation="AutoFDE composes FOND and HDDL.",
    ontology_context="urn:example:formalism-ontology",
    provenance_context="urn:source:example",
)

assert result.receipt.standing is AdmissionStanding.ADMITTED
print(result.receipt.model_dump_json(indent=2))
print(result.canonical_ntriples)
