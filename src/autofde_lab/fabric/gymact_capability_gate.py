"""Capability allowlist gate for gymact-backed diagnosing pipelines.

Concrete enforcement mechanism for the boundary decision documented in
:mod:`autofde_lab.powl.runner`'s module docstring: when the target
environment is the real, external `gymact` package (`~/gymact`, imported
directly as `import gymact` -- this module is NOT a local wrapper/shadow
package for gymact, it only validates capability names against it),
autofde-lab's diagnosing pipeline may only construct or invoke a gymact
`Capability` whose `binding` name appears in this module's TOML manifest
(``src/autofde_lab/fabric/gymact_capabilities.toml``). Anything else --
including a capability name that does not exist in gymact today -- is
refused with a named, typed :class:`CapabilityRefused` error, never a silent
pass-through.

Note: this repo also has a pre-existing, unrelated `src/autofde_lab/gymact/`
package (`kernel.py` wrapping `gymact.runtime.GymAct`, plus
`api.py`/`cli.py`/`eventlog.py`/`mcp.py`/`models.py`/`process.py`). This
module is deliberately placed under `fabric/`, not added to that package --
see that package's own module docstring for its separate scope.

Why this exists
-----------------
`gymact.gyms.sregym.SregymEnvironment` exposes a real, persistent kubectl-mcp
session and a real submit-diagnosis/submit-mitigation MCP surface. Nothing
in the *current* `SREGYM_CAPABILITIES` tuple reads ground truth or drives
`verify()` (`verify()` is not even wrapped as a `Capability` -- see the
manifest's own comments) but the boundary this module enforces is not "audit
today's five names by hand" -- it is "an allowlist checked at call time,
every time, so a future gymact capability that *does* expose ground truth or
scoring internals is refused by default until this manifest is deliberately
reviewed and updated," per this repo's absence-is-not-evidence rule: absence
of a known problem today is not permission to admit an unreviewed capability
tomorrow.

Real TOML parsing (`tomllib`, stdlib) against a real file on disk; no mocked
manifest, no interaction-based fakes.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "CapabilityGate",
    "CapabilityManifestEntry",
    "CapabilityRefused",
    "DEFAULT_MANIFEST_PATH",
]

DEFAULT_MANIFEST_PATH = Path(__file__).with_name("gymact_capabilities.toml")


class CapabilityRefused(PermissionError):
    """Raised when the diagnosing pipeline attempts to construct or call a
    gymact capability whose binding name is not in the loaded manifest.

    A subclass of :class:`PermissionError` (not a bare `ValueError`) so a
    caller can distinguish "you asked for something you are not allowed to
    have" from an ordinary malformed-input error -- this is a boundary
    refusal, not input validation.
    """

    def __init__(self, binding: str, *, allowed: frozenset[str], environment: str) -> None:
        self.binding = binding
        self.allowed = allowed
        self.environment = environment
        super().__init__(
            f"REFUSED:CAPABILITY_NOT_IN_MANIFEST binding={binding!r} "
            f"environment={environment!r} allowed={sorted(allowed)!r}"
        )


@dataclass(frozen=True)
class CapabilityManifestEntry:
    """One allowed capability, as declared in `capabilities.toml`."""

    name: str
    consequence: str
    reason: str


class CapabilityGate:
    """Loads a TOML capability manifest and enforces it at call time.

    Real collaborators only: a real `Path`, real `tomllib.load` against a
    real file's real bytes. No mocked filesystem, no faked TOML content.
    """

    def __init__(self, entries: tuple[CapabilityManifestEntry, ...], *, environment: str) -> None:
        self._entries = entries
        self._by_name: dict[str, CapabilityManifestEntry] = {e.name: e for e in entries}
        self.environment = environment

    @classmethod
    def from_toml(cls, path: Path | str = DEFAULT_MANIFEST_PATH) -> "CapabilityGate":
        """Parse a real TOML manifest file into a `CapabilityGate`.

        Raises `FileNotFoundError` (unchanged, not wrapped) if `path` does
        not exist -- a missing manifest is a configuration defect, not
        something this loader should paper over by falling back to an
        implicit "allow everything" or "allow nothing" default.
        """
        manifest_path = Path(path)
        with manifest_path.open("rb") as fh:
            data: dict[str, Any] = tomllib.load(fh)

        environment = data.get("gymact", {}).get("environment", "")
        raw_entries = data.get("capability", [])
        if not isinstance(raw_entries, list) or not raw_entries:
            raise ValueError(
                f"REFUSED:EMPTY_CAPABILITY_MANIFEST path={manifest_path} "
                "-- a manifest declaring zero capabilities refuses everything "
                "by construction; if that is intended, this check exists so "
                "it is never an accident."
            )

        entries = tuple(
            CapabilityManifestEntry(
                name=entry["name"],
                consequence=entry.get("consequence", ""),
                reason=entry.get("reason", ""),
            )
            for entry in raw_entries
        )
        return cls(entries, environment=environment)

    @property
    def allowed_names(self) -> frozenset[str]:
        return frozenset(self._by_name)

    def entry(self, binding: str) -> CapabilityManifestEntry:
        """Return the manifest entry for `binding`, or raise
        `CapabilityRefused` if it is not listed."""
        try:
            return self._by_name[binding]
        except KeyError:
            raise CapabilityRefused(
                binding, allowed=self.allowed_names, environment=self.environment
            ) from None

    def check(self, binding: str) -> None:
        """Raise `CapabilityRefused` if `binding` is not in the manifest;
        return `None` (no value) if it is allowed. Named separately from
        `entry()` for callers that only need the refuse/allow decision."""
        self.entry(binding)

    def stale_entries(self, real_names: frozenset[str] | set[str]) -> frozenset[str]:
        """Return the subset of this manifest's allowed names that do not
        appear in `real_names` -- the real capability-name set of the target
        environment (e.g. `{c.binding for c in SREGYM_CAPABILITIES}`).

        A non-empty result means the manifest lists at least one binding
        that does not correspond to any real capability today: a stale or
        typo'd entry that `from_toml` alone cannot detect, since a manifest
        is self-consistent TOML regardless of whether its names mean
        anything to the real environment. This method never mutates the
        gate or the manifest; it is a pure cross-check callers can run at
        startup (or in a test) to catch drift between the allowlist and
        gymact's real capability set.
        """
        return self.allowed_names - frozenset(real_names)

    def guard_capability(self, capability: Any) -> Any:
        """Check a real `gymact.models.Capability`-shaped object's
        `.binding` attribute against the manifest and return it unchanged
        if allowed.

        Accepts anything with a `.binding` attribute (duck-typed, so this
        module never needs an import-time dependency on the real `gymact`
        package -- the TOML-parsing/refusal logic this file exists to test
        does not require gymact to be importable) rather than importing
        `gymact.models.Capability` directly.
        """
        binding = getattr(capability, "binding", None)
        if binding is None:
            raise CapabilityRefused(
                repr(capability), allowed=self.allowed_names, environment=self.environment
            )
        self.check(binding)
        return capability
