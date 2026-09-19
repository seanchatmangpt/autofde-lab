"""GALL Semantic Work Fabric surfaces: checkpoint frontier, HDDL projection, MachineExperience
(v26.9.18 GALL SWF PRD §11.1, §15, §39, §43.3).

This module is the semantic frontier representation for GALL checkpoints: a checkpoint
is a repository-scoped semantic position (base SHA + goal + dependencies + standing)
that a planner may reason about but never actuate. Four additive surfaces live here:

* :class:`Checkpoint` -- identity (``urn:gall:checkpoint:<repo>:<id>``), repository,
  base_sha, checkpoint-IRI dependencies, goal, and standing, with a namespaced dict
  round-trip (namespace ``https://semantic-a2a.dev/gall#``).
* :func:`select_frontier` -- PRD §11.1's admissible frontier as a pure, deterministic
  function: a checkpoint is on the frontier iff its standing is ``UNKNOWN`` and every
  dependency's standing is ``ALIVE``. Every other outcome is reported with a typed
  reason, never silently pruned.
* :func:`project_to_hddl` -- PRD §15/§43.3's HDDL-style problem projection. A
  projection only: it executes nothing, decomposes nothing at runtime, and carries
  no SELECT/CONSTRUCT/DO authority.
* :class:`MachineExperienceRecord` -- PRD §39's MachineExperience record
  ``E_t = (S_t, A_t, Admission_t, Execution_t, Observation, S_t1)``, JSON-serializable
  and schema-compatible with the v26.9.17 MachineExperience lifecycle
  (:mod:`autofde_lab.sa2a.experience.types`): the standing vocabulary is the same
  evidence vocabulary, and :meth:`MachineExperienceRecord.to_metadata` produces a
  flat mapping suitable for that class's ``metadata`` field.

Authority ceiling
-----------------
Planner output here is advisory-only. :class:`Recommendation` and
:class:`CandidatePlan` carry no bearer value and expose no ``execute``/``actuate``/
``dispatch`` path; planner output SHALL NOT directly execute repository consequences.
A planner recommends; a broker authorizes; an executor performs; a verifier evaluates.
Nothing in this module's public API dispatches a Recommendation anywhere.

HDDL problem dict shape (PRD §15/§43.3 projection contract)
-----------------------------------------------------------
``project_to_hddl(checkpoints)`` returns a plain JSON-serializable dict::

    {
        "domain": "https://semantic-a2a.dev/gall#checkpoint-domain",
        "problem": "gall-checkpoint-frontier",
        "objects": [<checkpoint IRI>, ...],
        "tasks": [
            {
                "name": "achieve-<checkpoint IRI>",
                "checkpoint": <checkpoint IRI>,
                "goal": <checkpoint goal text>,
            },
            ...
        ],
        "methods": [
            {
                "name": "decompose-<checkpoint IRI>",
                "task": "achieve-<checkpoint IRI>",
                "ordered": True,
                "subtasks": ["achieve-<dependency IRI>", ...],
            },
            ...
        ],
    }

Determinism contract: ``objects`` is the sorted, deduplicated union of all checkpoint
IRIs and all referenced dependency IRIs; ``tasks`` is sorted by checkpoint IRI;
``methods`` appears only for checkpoints with non-empty ``dependencies`` (a checkpoint
decomposes into its dependencies), sorted by checkpoint IRI; ``subtasks`` preserves
the checkpoint's declared dependency order (declared order is part of the checkpoint
data, so the same input always yields the identical dict). The same input collection
-- in any order -- projects to the identical dict, every time.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

__all__ = [
    "CHECKPOINT_URN_PREFIX",
    "GALL",
    "REFUSED_DEPENDENCY",
    "REFUSED_MALFORMED_CHECKPOINT",
    "CandidatePlan",
    "Checkpoint",
    "DependencyBlock",
    "FrontierSelection",
    "GallStanding",
    "MachineExperienceRecord",
    "Recommendation",
    "checkpoint_identity",
    "project_to_hddl",
    "recommend_frontier",
    "select_frontier",
]

#: The GALL namespace. Every serialized term below is a full IRI in this namespace.
GALL = "https://semantic-a2a.dev/gall#"

#: URN prefix of every checkpoint identity: ``urn:gall:checkpoint:<repo>:<id>``.
CHECKPOINT_URN_PREFIX = "urn:gall:checkpoint:"

#: Typed refusal: a frontier candidate is excluded because a named dependency is not
#: ALIVE. The refusal names the exact dependency and its observed standing.
REFUSED_DEPENDENCY = "REFUSED_DEPENDENCY"

#: Typed refusal: a checkpoint or record failed structural validation and was never
#: admitted to the frontier computation at all.
REFUSED_MALFORMED_CHECKPOINT = "REFUSED_MALFORMED_CHECKPOINT"

_IDENTITY_PATTERN = re.compile(r"^urn:gall:checkpoint:(?P<repo>[^:]+):(?P<cid>[^:]+)$")


class GallStanding(str, Enum):
    """Evidence-vocabulary standings a checkpoint may carry.

    Exactly the repository's standing law vocabulary (README "Evidence vocabulary"):
    ``UNKNOWN | PARTIAL_ALIVE | ALIVE | BLOCKED | BUILD_BROKEN | UNSUPPORTED``. The
    same values as :class:`autofde_lab.sa2a.brce.replay.ReplayStanding` plus the
    ``UNKNOWN`` a not-yet-verified checkpoint holds; values match the v26.9.17
    MachineExperience schema's evidence vocabulary so records from both surfaces
    are comparable without translation.
    """

    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"
    BUILD_BROKEN = "BUILD_BROKEN"
    UNSUPPORTED = "UNSUPPORTED"


def checkpoint_identity(repository: str, checkpoint_id: str) -> str:
    """Build a lawful checkpoint identity: ``urn:gall:checkpoint:<repo>:<id>``.

    Raises ``ValueError`` on an empty repository/checkpoint id or on a ``:``
    inside either component -- the URN grammar gives the separator no escape,
    so a colon would make the identity ambiguous rather than merely ugly.
    """

    for label, value in (("repository", repository), ("checkpoint_id", checkpoint_id)):
        if not value or not value.strip():
            raise ValueError(f"{label} must be a non-empty string")
        if ":" in value:
            raise ValueError(
                f"{label} must not contain ':' (would break the "
                f"urn:gall:checkpoint:<repo>:<id> grammar): {value!r}"
            )
    return f"{CHECKPOINT_URN_PREFIX}{repository}:{checkpoint_id}"


def _require(data: Mapping[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f"{REFUSED_MALFORMED_CHECKPOINT}: missing required key {key!r}")
    return data[key]


def _parse_standing(value: Any) -> GallStanding:
    try:
        return GallStanding(value)
    except ValueError:
        lawful = ", ".join(s.value for s in GallStanding)
        raise ValueError(
            f"{REFUSED_MALFORMED_CHECKPOINT}: standing {value!r} is not in the "
            f"lawful vocabulary ({lawful})"
        ) from None


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """A repository-scoped semantic checkpoint (PRD §43.3).

    Immutable by construction, matching every other receipted object in ``sa2a/``.
    ``dependencies`` are checkpoint IRIs this checkpoint depends on; declared order
    is significant for the HDDL projection and preserved exactly. A new checkpoint
    starts at :attr:`GallStanding.UNKNOWN`: standing is earned by observed execution,
    never asserted at construction.
    """

    identity: str
    repository: str
    base_sha: str
    goal: str = ""
    dependencies: tuple[str, ...] = ()
    standing: GallStanding = GallStanding.UNKNOWN

    def __post_init__(self) -> None:
        if not self.base_sha or not self.base_sha.strip():
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: base_sha must be a non-empty string"
            )
        match = _IDENTITY_PATTERN.match(self.identity)
        if not match:
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: identity {self.identity!r} does not "
                "match urn:gall:checkpoint:<repo>:<id>"
            )
        if match.group("repo") != self.repository:
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: identity {self.identity!r} names "
                f"repository {match.group('repo')!r}, but the checkpoint declares "
                f"repository {self.repository!r}"
            )
        for dependency in self.dependencies:
            if not dependency.startswith(CHECKPOINT_URN_PREFIX):
                raise ValueError(
                    f"{REFUSED_MALFORMED_CHECKPOINT}: dependency {dependency!r} is not "
                    f"a checkpoint IRI (must start with {CHECKPOINT_URN_PREFIX!r})"
                )

    @property
    def checkpoint_id(self) -> str:
        """The ``<id>`` component of this checkpoint's identity URN."""

        match = _IDENTITY_PATTERN.match(self.identity)
        assert match is not None  # __post_init__ guarantees the shape
        return match.group("cid")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a GALL-namespaced dict (namespace ``https://semantic-a2a.dev/gall#``)."""

        return {
            "@type": GALL + "Checkpoint",
            GALL + "identity": self.identity,
            GALL + "repository": self.repository,
            GALL + "baseSha": self.base_sha,
            GALL + "goal": self.goal,
            GALL + "dependsOn": list(self.dependencies),
            GALL + "standing": self.standing.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Checkpoint":
        """Parse from a :meth:`to_dict` form, failing closed on any malformed field."""

        graph_type = _require(data, "@type")
        if graph_type != GALL + "Checkpoint":
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: @type {graph_type!r} is not "
                f"{GALL + 'Checkpoint'!r}"
            )
        dependencies = _require(data, GALL + "dependsOn")
        if not isinstance(dependencies, (list, tuple)) or not all(
            isinstance(item, str) for item in dependencies
        ):
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: dependsOn must be a list of IRIs"
            )
        return cls(
            identity=_require(data, GALL + "identity"),
            repository=_require(data, GALL + "repository"),
            base_sha=_require(data, GALL + "baseSha"),
            goal=_require(data, GALL + "goal"),
            dependencies=tuple(dependencies),
            standing=_parse_standing(_require(data, GALL + "standing")),
        )


def _index_by_identity(checkpoints: Iterable[Checkpoint]) -> dict[str, Checkpoint]:
    indexed: dict[str, Checkpoint] = {}
    for checkpoint in checkpoints:
        if checkpoint.identity in indexed:
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: duplicate checkpoint identity "
                f"{checkpoint.identity!r} in one frontier computation"
            )
        indexed[checkpoint.identity] = checkpoint
    return indexed


@dataclass(frozen=True, slots=True)
class DependencyBlock:
    """One typed refusal: a checkpoint excluded because a named dependency is not ALIVE."""

    checkpoint_iri: str
    dependency_iri: str
    dependency_standing: GallStanding
    reason: str = REFUSED_DEPENDENCY


@dataclass(frozen=True, slots=True)
class FrontierSelection:
    """PRD §11.1 frontier result. Every excluded checkpoint is reported, never pruned.

    ``frontier`` -- checkpoint IRIs whose standing is UNKNOWN and whose every
    dependency's standing is ALIVE (sorted, deterministic).
    ``refusals`` -- one :class:`DependencyBlock` per (UNKNOWN checkpoint, non-ALIVE
    dependency) pair, naming the exact blocking dependency and its observed standing.
    A dependency absent from the input collection is observed as UNKNOWN (fail-closed:
    no observed ALIVE execution means not ALIVE).
    ``alive`` -- checkpoints already ALIVE; work is done, so they are not on the
    frontier (sorted).
    ``excluded`` -- (IRI, standing) pairs for checkpoints whose own standing is
    neither UNKNOWN nor ALIVE (sorted); recorded so the exclusion is evidence, not
    silent pruning.
    """

    frontier: tuple[str, ...]
    refusals: tuple[DependencyBlock, ...]
    alive: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]


def select_frontier(checkpoints: Iterable[Checkpoint]) -> FrontierSelection:
    """Select the admissible frontier (PRD §11.1). Pure and deterministic.

    A checkpoint is on the frontier iff its standing is UNKNOWN and every declared
    dependency's standing is ALIVE. Output order depends only on checkpoint content
    (IRIs), never on input collection order.
    """

    indexed = _index_by_identity(checkpoints)
    standings = {iri: cp.standing for iri, cp in indexed.items()}

    frontier: list[str] = []
    refusals: list[DependencyBlock] = []
    alive: list[str] = []
    excluded: list[tuple[str, str]] = []

    for iri in sorted(indexed):
        checkpoint = indexed[iri]
        if checkpoint.standing == GallStanding.ALIVE:
            alive.append(iri)
            continue
        if checkpoint.standing != GallStanding.UNKNOWN:
            excluded.append((iri, checkpoint.standing.value))
            continue
        blocked = False
        for dependency in checkpoint.dependencies:
            observed = standings.get(dependency, GallStanding.UNKNOWN)
            if observed != GallStanding.ALIVE:
                refusals.append(
                    DependencyBlock(
                        checkpoint_iri=iri,
                        dependency_iri=dependency,
                        dependency_standing=observed,
                    )
                )
                blocked = True
        if not blocked:
            frontier.append(iri)

    return FrontierSelection(
        frontier=tuple(frontier),
        refusals=tuple(refusals),
        alive=tuple(alive),
        excluded=tuple(excluded),
    )


def project_to_hddl(checkpoints: Iterable[Checkpoint]) -> dict[str, Any]:
    """Project checkpoints into an HDDL-style problem dict (PRD §15/§43.3).

    See the module docstring for the exact, deterministic shape. This is a
    projection only: it executes nothing, satisfies nothing, and carries no
    SELECT/CONSTRUCT/DO authority. Decomposition edges mirror the checkpoints'
    own ``dependsOn`` data; no hierarchy is inferred, flattened, or solved.
    """

    indexed = _index_by_identity(checkpoints)

    objects = sorted(
        {iri for iri in indexed} | {dep for cp in indexed.values() for dep in cp.dependencies}
    )
    tasks = [
        {
            "name": f"achieve-{iri}",
            "checkpoint": iri,
            "goal": indexed[iri].goal,
        }
        for iri in sorted(indexed)
    ]
    methods = [
        {
            "name": f"decompose-{iri}",
            "task": f"achieve-{iri}",
            "ordered": True,
            "subtasks": [f"achieve-{dep}" for dep in indexed[iri].dependencies],
        }
        for iri in sorted(indexed)
        if indexed[iri].dependencies
    ]

    return {
        "domain": GALL + "checkpoint-domain",
        "problem": "gall-checkpoint-frontier",
        "objects": objects,
        "tasks": tasks,
        "methods": methods,
    }


@dataclass(frozen=True, slots=True)
class MachineExperienceRecord:
    """PRD §39 MachineExperience record ``E_t`` (JSON-serializable).

    ``s_t`` -- the prior semantic state (a state descriptor or digest).
    ``a_t`` -- available action identities at t.
    ``admission_t`` -- the admitted/legal subset of ``a_t`` (enforced: a record
    whose admission names an unavailable action is malformed, fail-closed).
    ``execution_t`` -- the selected construction reference (identity/digest of what
    was selected for construction; presence is a reference, never an execution
    witness -- evidence lives in ``observation``).
    ``observation`` -- process/verifier evidence reference (digest/receipt identity).
    ``s_t1`` -- the resulting standing.

    Schema compatibility: this refines (not replaces) the v26.9.17 MachineExperience
    lifecycle in :mod:`autofde_lab.sa2a.experience.types`. ``s_t1`` uses the same
    evidence standing vocabulary as checkpoints, and :meth:`to_metadata` renders the
    record as a flat namespaced mapping accepted by that class's ``metadata`` field.
    """

    s_t: str
    a_t: tuple[str, ...]
    admission_t: tuple[str, ...]
    execution_t: str
    observation: str
    s_t1: GallStanding

    def __post_init__(self) -> None:
        if len(set(self.a_t)) != len(self.a_t):
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: duplicate entries in a_t"
            )
        unavailable = [a for a in self.admission_t if a not in self.a_t]
        if unavailable:
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: admission_t names actions not in "
                f"a_t: {unavailable!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a GALL-namespaced dict (namespace ``https://semantic-a2a.dev/gall#``)."""

        return {
            "@type": GALL + "MachineExperience",
            GALL + "S_t": self.s_t,
            GALL + "A_t": list(self.a_t),
            GALL + "Admission_t": list(self.admission_t),
            GALL + "Execution_t": self.execution_t,
            GALL + "Observation": self.observation,
            GALL + "S_t1": self.s_t1.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MachineExperienceRecord":
        """Parse from a :meth:`to_dict` form, failing closed on any malformed field."""

        graph_type = _require(data, "@type")
        if graph_type != GALL + "MachineExperience":
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: @type {graph_type!r} is not "
                f"{GALL + 'MachineExperience'!r}"
            )
        a_t = _require(data, GALL + "A_t")
        admission_t = _require(data, GALL + "Admission_t")
        if not isinstance(a_t, (list, tuple)) or not all(
            isinstance(item, str) for item in a_t
        ):
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: A_t must be a list of action identities"
            )
        if not isinstance(admission_t, (list, tuple)) or not all(
            isinstance(item, str) for item in admission_t
        ):
            raise ValueError(
                f"{REFUSED_MALFORMED_CHECKPOINT}: Admission_t must be a list of action identities"
            )
        return cls(
            s_t=_require(data, GALL + "S_t"),
            a_t=tuple(a_t),
            admission_t=tuple(admission_t),
            execution_t=_require(data, GALL + "Execution_t"),
            observation=_require(data, GALL + "Observation"),
            s_t1=_parse_standing(_require(data, GALL + "S_t1")),
        )

    def to_metadata(self) -> dict[str, Any]:
        """Render as a flat namespaced mapping for the v26.9.17 MachineExperience
        ``metadata`` field (:class:`autofde_lab.sa2a.experience.types.MachineExperience`).

        Compatibility, not conversion: this produces the metadata payload only. It
        never constructs a lifecycle MachineExperience -- lifecycle state transitions
        are owned by that class's own lawful-transition gate.
        """

        return {
            GALL + "S_t": self.s_t,
            GALL + "A_t": list(self.a_t),
            GALL + "Admission_t": list(self.admission_t),
            GALL + "Execution_t": self.execution_t,
            GALL + "Observation": self.observation,
            GALL + "S_t1": self.s_t1.value,
        }


@dataclass(frozen=True, slots=True)
class CandidatePlan:
    """An advisory candidate plan over a frontier. Not authorization, never executed.

    ``plan_id`` is content-addressed (digest of the sorted frontier IRIs) so two
    plans over the same frontier are recognizably the same plan.
    """

    plan_id: str
    frontier: tuple[str, ...]
    rationale: str = ""
    advisory: bool = True


@dataclass(frozen=True, slots=True)
class Recommendation:
    """The planner's advisory recommendation. Not authority, and not convertible to it.

    Planner output SHALL NOT directly execute repository consequences. There is
    deliberately no bearer value on this object -- no token, no signature, no
    authority grant -- and deliberately no ``execute``/``actuate``/``dispatch``
    method: actuation requires a separate brokered, receipt-bearing authorization
    path outside this module (a planner recommends; a broker authorizes; an
    executor performs; a verifier evaluates). ``__bool__`` raises so an advisory
    allow cannot be silently truth-tested into a decision.
    """

    recommendation_id: str
    plan: CandidatePlan
    rationale: str = ""
    advisory: bool = True

    def __bool__(self) -> None:  # always raises; see the test that falsifies truthiness
        raise TypeError(
            "Recommendation is advisory and must not be used as a truth value; "
            "a recommendation is not authorization and grants no authority"
        )


def recommend_frontier(checkpoints: Iterable[Checkpoint]) -> Recommendation:
    """The planner's public entry: select the frontier and recommend it. Advisory-only.

    Returns a :class:`Recommendation` wrapping a content-addressed
    :class:`CandidatePlan`. This function computes; it never dispatches, executes,
    or actuates anything -- see the :class:`Recommendation` docstring for the
    authority ceiling.
    """

    selection = select_frontier(checkpoints)
    digest = hashlib.sha256("\n".join(selection.frontier).encode("utf-8")).hexdigest()
    plan = CandidatePlan(
        plan_id=f"gall-plan-{digest[:16]}",
        frontier=selection.frontier,
        rationale=(
            "UNKNOWN-standing checkpoints whose every dependency is ALIVE "
            "(PRD §11.1 admissible frontier)"
        ),
    )
    return Recommendation(
        recommendation_id=f"gall-rec-{digest[:16]}",
        plan=plan,
    )
