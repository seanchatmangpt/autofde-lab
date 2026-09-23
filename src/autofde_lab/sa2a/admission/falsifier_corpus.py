"""Real, callable falsifier-corpus runner (v26.9.17 PRD §14 item 27 / ARD §64 item 15,
"zero mandatory falsifiers survive").

Before this module, no crown-level, single certified claim of "zero mandatory
falsifiers survive" existed anywhere in the codebase -- `falsifier_corpus_digest` in
the crown's manifest fixtures (`cli.py`, the release test fixtures) is a hardcoded
literal, never computed from real corpus content. This module closes that gap by
composing (never re-deriving) two already-real, already-tested collaborators:

1. `admission.falsifiers.FalsifierSuite` -- the real SPARQL ASK falsifier engine
   (RFC-SA2A-001 v26.9.16 §18, §61), exercised here against real adversarial RDF
   fixtures for each of its 5 default falsifiers.
2. `composition.resolver.SubjectResolver` -- the real, already-hardened
   (`REFUSED_FLOATING_REPOSITORY_REF`, `REFUSED_CONFLICTING_ARTIFACT_DIGEST`, ...)
   composition-identity fence, exercised here against real deliberately-malformed
   candidate manifests.

"Survived" follows the falsification vocabulary this repo already uses
(`conformance/courts/admission_court.py`'s `FalsificationVerdict`): a mandatory
falsifier SURVIVES an adversarial trial when the trial's attack was NOT caught (the
SPARQL ASK failed to fire on a graph that genuinely contains the bad pattern; the
resolver silently admitted a manifest it should have refused). A falsifier that
correctly caught its trial did NOT survive -- this is the desired outcome, and "zero
mandatory falsifiers survive" means every trial below caught its own adversarial
fixture.

`corpus_digest` is computed from the CORPUS'S OWN CONTENT (the real falsifier ids and
the real SPARQL query text pulled live from `admission.falsifiers`, plus the real
composition-fence check specs below) -- never from a trial's pass/fail outcome, and
never a placeholder literal. It answers "which corpus version is this", the same role
`ExactSubject.composition_digest` plays for subject identity, and is stable across
runs of the same code regardless of what any individual trial's adversarial fixture
happens to observe.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from rdflib import Graph

from autofde_lab.sa2a.admission.falsifiers import FalsifierSuite
from autofde_lab.sa2a.composition.resolver import (
    SubjectResolutionError,
    SubjectResolver,
)

_TTL_PREFIXES = (
    "@prefix afl: <urn:autofde-lab:> .\n@prefix prov: <http://www.w3.org/ns/prov#> .\n"
)

# --- Real adversarial RDF fixtures, one per default SPARQL ASK falsifier in
# `admission.falsifiers.FalsifierSuite`. Each is a genuine, minimal graph that
# CONTAINS the exact bad pattern the corresponding ASK query looks for -- if the
# falsifier is working, `FalsifierSuite.evaluate()` MUST report it triggered
# (caught); if it reports nothing triggered, the falsifier survived the attack.
_SPARQL_FIXTURES: Dict[str, str] = {
    "FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY": (
        _TTL_PREFIXES + 'afl:action-corpus-1 afl:consequenceClass "DESTRUCTIVE" .\n'
    ),
    "FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT": (
        _TTL_PREFIXES + "afl:action-corpus-2 a afl:Actuation .\n"
    ),
    "FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN": (
        _TTL_PREFIXES
        + "afl:plan-corpus-3 a afl:Plan ;\n"
        + "    afl:requiresCapability afl:cap-undeclared-corpus-3 .\n"
    ),
    "FALSIFIER_PROJECTION_AS_CANONICAL": (
        _TTL_PREFIXES
        + "afl:projection-corpus-4 a afl:Projection ;\n"
        + "    afl:isCanonical true .\n"
    ),
    "FALSIFIER_LLM_DIRECT_ADMITTED": (
        _TTL_PREFIXES
        + 'afl:subject-corpus-5 afl:standing "ADMITTED" ;\n'
        + "    prov:wasAttributedTo afl:llm-agent-corpus-5 .\n"
        + "afl:llm-agent-corpus-5 a afl:LLM .\n"
    ),
}

# --- Real deliberately-malformed candidate manifests exercising the composition-
# identity fence (`SubjectResolver`) -- reused directly, never re-derived, per this
# repo's own Reuse Before Construction rule.
_COMPOSITION_FENCE_FIXTURES: Dict[str, Dict[str, Any]] = {
    "FALSIFIER_FLOATING_REPOSITORY_REF": {
        "release_id": "falsifier-corpus-floating-ref",
        "repositories": [{"name": "adversary-repo", "exact_sha": "main"}],
        "artifacts": [],
        "root_manifest_digest": "f" * 64,
    },
    "FALSIFIER_CONFLICTING_ARTIFACT_DIGEST": {
        "release_id": "falsifier-corpus-conflicting-artifact",
        "repositories": [],
        "artifacts": [
            {"artifact_id": "shared-artifact", "digest": "1" * 64},
            {"artifact_id": "shared-artifact", "digest": "2" * 64},
        ],
        "root_manifest_digest": "f" * 64,
    },
}

_MANDATORY_FALSIFIER_IDS: Tuple[str, ...] = (
    *_SPARQL_FIXTURES.keys(),
    *_COMPOSITION_FENCE_FIXTURES.keys(),
)


@dataclass(frozen=True, slots=True)
class FalsifierTrialResult:
    """One mandatory falsifier's real trial outcome."""

    falsifier_id: str
    description: str
    survived: bool
    detail: str


@dataclass(frozen=True, slots=True)
class FalsifierCorpusVerdict:
    """Typed verdict naming exactly which falsifiers ran, which survived (a real
    finding -- an adversarial trial that got through uncaught), and which did not
    (correctly caught)."""

    corpus_digest: str
    trials: Tuple[FalsifierTrialResult, ...]

    @property
    def all_mandatory_caught(self) -> bool:
        """True iff zero mandatory falsifiers survived (PRD §14 item 27)."""
        return not any(t.survived for t in self.trials)

    @property
    def survived_falsifier_ids(self) -> Tuple[str, ...]:
        return tuple(t.falsifier_id for t in self.trials if t.survived)

    @property
    def caught_falsifier_ids(self) -> Tuple[str, ...]:
        return tuple(t.falsifier_id for t in self.trials if not t.survived)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "corpus_digest": self.corpus_digest,
            "all_mandatory_caught": self.all_mandatory_caught,
            "survived_falsifier_ids": list(self.survived_falsifier_ids),
            "caught_falsifier_ids": list(self.caught_falsifier_ids),
            "trials": [
                {
                    "falsifier_id": t.falsifier_id,
                    "description": t.description,
                    "survived": t.survived,
                    "detail": t.detail,
                }
                for t in self.trials
            ],
        }


def _corpus_content_spec() -> Tuple[Tuple[str, str], ...]:
    """Real corpus content (falsifier id, the exact check specification text) pulled
    live from the real collaborators -- SPARQL query text from `FalsifierSuite`'s own
    registered definitions, and the composition-fence check names/manifests for the
    two resolver-based trials. Used ONLY to compute `corpus_digest`; never influenced
    by any trial's pass/fail outcome.
    """
    suite = FalsifierSuite(include_defaults=True)
    entries: list[Tuple[str, str]] = []
    for name in _SPARQL_FIXTURES:
        fdef = suite.get_falsifier(name)
        assert fdef is not None, f"corpus references unknown default falsifier {name!r}"
        entries.append((name, fdef.query))
    for name, manifest in _COMPOSITION_FENCE_FIXTURES.items():
        entries.append(
            (name, json.dumps(manifest, sort_keys=True, separators=(",", ":")))
        )
    return tuple(sorted(entries))


def compute_falsifier_corpus_digest() -> str:
    """Real, deterministic digest over the corpus's own content (never a placeholder;
    never a run outcome). Stable across runs of the same code, changes whenever a
    falsifier query or fence fixture actually changes."""
    payload = {"entries": _corpus_content_spec()}
    dumped = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def _run_sparql_trial(falsifier_id: str, fixture_ttl: str) -> FalsifierTrialResult:
    """Run exactly one default SPARQL ASK falsifier against its own real adversarial
    fixture, isolated from the other 4 (a merged graph risks cross-contamination
    across `FILTER NOT EXISTS` clauses that reference unrelated triples)."""
    suite = FalsifierSuite(include_defaults=False)
    defaults = FalsifierSuite(include_defaults=True)
    fdef = defaults.get_falsifier(falsifier_id)
    assert fdef is not None
    suite.register(
        name=fdef.name,
        query=fdef.query,
        description=fdef.description,
        falsifier_id=fdef.falsifier_id,
    )

    graph = Graph()
    graph.parse(data=fixture_ttl, format="turtle")
    triggered = suite.evaluate(graph)

    caught = len(triggered) > 0
    return FalsifierTrialResult(
        falsifier_id=falsifier_id,
        description=fdef.description,
        survived=not caught,
        detail=(
            f"SPARQL ASK falsifier {'fired on' if caught else 'FAILED TO FIRE on'} "
            f"its real adversarial fixture (triggered_count={len(triggered)})"
        ),
    )


def _run_composition_fence_trial(
    falsifier_id: str, bad_manifest: Dict[str, Any]
) -> FalsifierTrialResult:
    """Run exactly one composition-identity-fence trial: a deliberately malformed
    candidate manifest MUST be refused by the real `SubjectResolver` -- reused
    directly, never re-derived."""
    try:
        SubjectResolver().resolve(bad_manifest)
    except SubjectResolutionError as exc:
        return FalsifierTrialResult(
            falsifier_id=falsifier_id,
            description=f"SubjectResolver must refuse {falsifier_id}",
            survived=False,
            detail=f"correctly refused: {exc.code}",
        )
    return FalsifierTrialResult(
        falsifier_id=falsifier_id,
        description=f"SubjectResolver must refuse {falsifier_id}",
        survived=True,
        detail="SubjectResolver.resolve() did NOT raise SubjectResolutionError -- malformed manifest was silently admitted",
    )


def run_falsifier_corpus() -> FalsifierCorpusVerdict:
    """Actually RUN every mandatory falsifier against a real fixture and return a
    typed verdict. Callable, deterministic-content corpus digest, real trial
    execution -- never a hardcoded placeholder standing in for having run anything.
    """
    trials: list[FalsifierTrialResult] = []
    for falsifier_id, fixture_ttl in _SPARQL_FIXTURES.items():
        trials.append(_run_sparql_trial(falsifier_id, fixture_ttl))
    for falsifier_id, bad_manifest in _COMPOSITION_FENCE_FIXTURES.items():
        trials.append(_run_composition_fence_trial(falsifier_id, bad_manifest))

    return FalsifierCorpusVerdict(
        corpus_digest=compute_falsifier_corpus_digest(),
        trials=tuple(trials),
    )
