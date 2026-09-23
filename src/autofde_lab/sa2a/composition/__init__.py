"""ExactSubject fence: resolve and validate an exact, immutable release composition.

v26.9.17 PRD §6.1-6.2, ARD §5.1, §6-7. Scoped to this repo's own boundary
(`.claude/rules/ecosystem-boundary.md`: "this repo is the search graph, nothing
more"): `SubjectResolver` performs structural/format validation of a DECLARED
composition manifest (well-formed SHAs, present digests, no ambiguous/conflicting
identity) -- it never fetches, clones, or actuates a remote repository. Resolving
THIS repo's own exact git identity (`resolve_self()`) uses real, local, read-only
`git` subprocess calls; resolving a sibling repository's identity means validating
the SHA/digest the caller declares, not independently verifying it over the network.
"""

from __future__ import annotations

from autofde_lab.sa2a.composition.exact_subject import (
    ArtifactRef,
    ExactSubject,
    RepositoryRef,
)
from autofde_lab.sa2a.composition.resolver import (
    SubjectResolutionError,
    SubjectResolver,
)

__all__ = [
    "ArtifactRef",
    "ExactSubject",
    "RepositoryRef",
    "SubjectResolutionError",
    "SubjectResolver",
]
