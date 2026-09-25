"""Authority-safe federation adapter for the existing ggen-create product.

autofde-lab must not duplicate ggen-create's admitted exemplar reverse compiler.
This adapter constructs invocation intents and normalizes supplied
machine-readable output. It never starts a subprocess itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .model import RepositorySubject, digest


@dataclass(frozen=True, slots=True)
class InvocationIntent:
    executable_identity: str
    executable_revision: str
    argv: tuple[str, ...]
    cwd_subject_id: str
    purpose: str
    authority: str = "NONE"

    def __post_init__(self) -> None:
        if self.authority != "NONE":
            raise ValueError("IEC invocation intents carry no execution authority")
        if not self.argv:
            raise ValueError("argv must be non-empty")

    @property
    def intent_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class GgenCreateCapturePlan:
    source_subject_id: str
    generator_name: str
    included_paths: tuple[str, ...]
    intents: tuple[InvocationIntent, ...]

    @property
    def plan_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class GgenCreateStatus:
    source_subject_id: str
    package_identity: str | None
    standing: str
    blockers: tuple[str, ...]
    raw_digest: str


class GgenCreateAdapter:
    """Construct and parse the ggen-create seam without reimplementing it."""

    def __init__(
        self,
        *,
        executable_identity: str = "ggen-create",
        executable_revision: str,
    ) -> None:
        if not executable_revision.strip():
            raise ValueError("ggen-create revision must be pinned")
        self.executable_identity = executable_identity
        self.executable_revision = executable_revision

    def plan_capture(
        self,
        subject: RepositorySubject,
        *,
        generator_name: str,
        included_paths: Sequence[str],
        project_file: str = "ggen-create.json",
    ) -> GgenCreateCapturePlan:
        paths = tuple(sorted(set(included_paths)))
        if not generator_name.strip() or not paths:
            raise ValueError(
                "generator_name and at least one included path are required"
            )
        base = ("--project", project_file, "--json")
        commands = [
            ("capture-init", ("capture", "init", generator_name)),
            ("capture-include", ("capture", "include", *paths)),
            ("capture-status", ("status",)),
            ("package-build", ("package", "build")),
        ]
        intents = tuple(
            InvocationIntent(
                executable_identity=self.executable_identity,
                executable_revision=self.executable_revision,
                argv=(self.executable_identity, *base, *argv),
                cwd_subject_id=subject.subject_id,
                purpose=purpose,
            )
            for purpose, argv in commands
        )
        return GgenCreateCapturePlan(
            source_subject_id=subject.subject_id,
            generator_name=generator_name,
            included_paths=paths,
            intents=intents,
        )

    def parse_status(
        self,
        subject: RepositorySubject,
        payload: Mapping[str, Any],
    ) -> GgenCreateStatus:
        """Normalize already-observed JSON output; never infer execution."""

        standing = str(payload.get("standing", "UNKNOWN"))
        blockers = tuple(sorted(str(x) for x in payload.get("blockers", ())))
        package_identity = payload.get("package_identity")
        if package_identity is not None:
            package_identity = str(package_identity)
        return GgenCreateStatus(
            source_subject_id=subject.subject_id,
            package_identity=package_identity,
            standing=standing,
            blockers=blockers,
            raw_digest=digest(payload),
        )
