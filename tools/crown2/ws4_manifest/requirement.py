#!/usr/bin/env python3
"""requirement.py — WS4 input schema: GapDiagnosis + CapabilityRequirement.

A GapDiagnosis names a transition the current world graph cannot perform.
A CapabilityRequirement is the executable-knowledge form of that gap: the
needed transition, its pre/post conditions, the authority class under which
it may be exercised, how it will be qualified, and the ontology IRIs that
pin its meaning (semantic anchors).

Everything here is plain stdlib dataclasses with JSON round-trip, so a
later run can rebuild a requirement from a file without an LLM.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

AUTHORITY_CLASSES = ("SELECT", "CONSTRUCT", "VERIFY", "ACTUATE")
QUALIFICATION_STRATEGIES = (
    "chicago-real-run",      # real collaborators, state assertions
    "shacl-gate",            # SHACL shape must validate
    "receipt-replay",        # replay a receipt chain and compare digests
    "prediction-compare",    # frozen prediction vs observed outcome
)

# Ontology IRIs that anchor a requirement. `afl:` is the autofde-lab base
# IRI from /Users/sac/crown-2-orthogonal/ggen.toml [ontology.prefixes].
AFL = "urn:autofde-lab:"
KNOWN_ANCHOR_PREFIXES = (
    AFL,
    "https://ggen.dev/ontology/",
    "http://www.w3.org/ns/prov#",
    "urn:skdecide:capability:",
)


@dataclass(frozen=True)
class GapDiagnosis:
    """The observed gap: a transition the world graph could not perform."""

    gap_id: str
    observed_state: str          # WorldState label (OCEL object id or label)
    desired_state: str
    missing_transition: str      # verb-ish name, e.g. "propagate-capability"
    evidence_refs: tuple[str, ...] = ()   # OCEL object/event ids or receipt digests

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TemplateBinding:
    """Binding of a requirement to an admitted pack + template + query, by name."""

    pack: str
    template: str
    query: str
    output_file: str


@dataclass(frozen=True)
class CapabilityRequirement:
    requirement_id: str
    gap: GapDiagnosis
    needed_transition: str
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]
    authority_class: str
    qualification_strategy: str
    semantic_anchors: tuple[str, ...]      # ontology IRIs
    binding: TemplateBinding
    description: str = ""
    extra: dict = field(default_factory=dict)   # deliberately unmapped bag

    def __post_init__(self) -> None:
        if self.authority_class not in AUTHORITY_CLASSES:
            raise ValueError(
                f"authority_class {self.authority_class!r} not in {AUTHORITY_CLASSES}"
            )
        if self.qualification_strategy not in QUALIFICATION_STRATEGIES:
            raise ValueError(
                f"qualification_strategy {self.qualification_strategy!r} "
                f"not in {QUALIFICATION_STRATEGIES}"
            )
        if not self.semantic_anchors:
            raise ValueError("at least one semantic anchor IRI is required")
        for iri in self.semantic_anchors:
            if not iri.startswith(KNOWN_ANCHOR_PREFIXES):
                raise ValueError(f"semantic anchor {iri!r} has unknown prefix")
        if not self.needed_transition == self.gap.missing_transition:
            raise ValueError(
                "needed_transition must equal gap.missing_transition "
                f"({self.needed_transition!r} != {self.gap.missing_transition!r})"
            )

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "CapabilityRequirement":
        gap = GapDiagnosis(**{**d["gap"], "evidence_refs": tuple(d["gap"].get("evidence_refs", ()))})
        binding = TemplateBinding(**d["binding"])
        return cls(
            requirement_id=d["requirement_id"],
            gap=gap,
            needed_transition=d["needed_transition"],
            preconditions=tuple(d["preconditions"]),
            postconditions=tuple(d["postconditions"]),
            authority_class=d["authority_class"],
            qualification_strategy=d["qualification_strategy"],
            semantic_anchors=tuple(d["semantic_anchors"]),
            binding=binding,
            description=d.get("description", ""),
            extra=dict(d.get("extra", {})),
        )

    @classmethod
    def from_json(cls, s: str) -> "CapabilityRequirement":
        return cls.from_dict(json.loads(s))


def fixture_requirements() -> list[CapabilityRequirement]:
    """Two real requirements used by the tests and the CLI demo."""
    r1 = CapabilityRequirement(
        requirement_id="req-propagate-capability",
        gap=GapDiagnosis(
            gap_id="gap-001",
            observed_state="ws:crown2:pr212-qualified",
            desired_state="ws:crown2:pr215-qualified",
            missing_transition="propagate-capability",
            evidence_refs=("receipt:blake3:pr212",),
        ),
        needed_transition="propagate-capability",
        preconditions=("source capability standing == ALIVE", "ancestor proof present"),
        postconditions=("target head carries capability", "semanticDelta == 0"),
        authority_class="CONSTRUCT",
        qualification_strategy="receipt-replay",
        semantic_anchors=(
            AFL + "Capability",
            AFL + "AuthorityEnvelope",
            "https://ggen.dev/ontology/capability-lineage-propagation#PropagationPlan",
        ),
        binding=TemplateBinding(
            pack="capability-lineage-propagation-pack",
            template="propagation-plan.json.tera",
            query="30-clean-plan.rq",
            output_file="generated/ws4/propagation-plan.json",
        ),
        description="Propagate an already-qualified capability along proven lineage.",
        extra={"owner": "crown-2", "priority": 1},
    )
    r2 = CapabilityRequirement(
        requirement_id="req-qualification-court",
        gap=GapDiagnosis(
            gap_id="gap-002",
            observed_state="ws:crown2:plan-unqualified",
            desired_state="ws:crown2:plan-qualified",
            missing_transition="qualify-propagation-plan",
        ),
        needed_transition="qualify-propagation-plan",
        preconditions=("plan.json exists",),
        postconditions=("court verdict recorded", "receipt issued"),
        authority_class="VERIFY",
        qualification_strategy="chicago-real-run",
        semantic_anchors=(
            AFL + "EvidenceWitness",
            "http://www.w3.org/ns/prov#Activity",
        ),
        binding=TemplateBinding(
            pack="capability-lineage-propagation-pack",
            template="propagation-court.py.tera",
            query="30-clean-plan.rq",
            output_file="generated/ws4/qualification_court.py",
        ),
    )
    return [r1, r2]


if __name__ == "__main__":
    for r in fixture_requirements():
        print(r.to_json())
