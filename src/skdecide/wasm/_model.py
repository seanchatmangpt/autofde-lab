"""Typed identities and request/response values for Chatman Wasm components."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from types import MappingProxyType
from typing import Any, Mapping

from ._abi import REQUEST_SCHEMA, RESPONSE_SCHEMA

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_PYTHON_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_ALIAS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALLOWED_STATES = frozenset(
    {
        "UNKNOWN",
        "PARTIAL_ALIVE",
        "ALIVE",
        "BLOCKED",
        "BUILD_BROKEN",
        "UNSUPPORTED",
        "REFUSED",
    }
)


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON suitable for hashing and guest exchange."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ComponentDescriptor:
    """Exact source and packaged-artifact identity for one ecosystem library."""

    name: str
    python_name: str
    repository: str
    branch: str
    revision: str
    artifact: str
    build_adapter: str = "auto"
    capability_class: str = "library"
    visibility: str = "public"
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _NAME_RE.fullmatch(self.name):
            raise ValueError(f"invalid component name: {self.name!r}")
        if not _PYTHON_NAME_RE.fullmatch(self.python_name):
            raise ValueError(f"invalid Python binding name: {self.python_name!r}")
        if not self.repository.startswith("https://github.com/"):
            raise ValueError(f"repository must be a GitHub HTTPS URL: {self.repository!r}")
        if not _SHA_RE.fullmatch(self.revision):
            raise ValueError(f"revision must be an exact 40-character SHA: {self.revision!r}")
        if not self.artifact.endswith(".wasm") or "/" in self.artifact:
            raise ValueError(f"artifact must be a local .wasm filename: {self.artifact!r}")
        if self.visibility not in {"public", "private"}:
            raise ValueError(f"unsupported visibility: {self.visibility!r}")
        for alias in self.aliases:
            if not _ALIAS_RE.fullmatch(alias):
                raise ValueError(f"invalid alias: {alias!r}")

    @property
    def repository_name(self) -> str:
        return self.repository.removesuffix(".git").rsplit("/", 1)[-1]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "python_name": self.python_name,
            "repository": self.repository,
            "branch": self.branch,
            "revision": self.revision,
            "artifact": self.artifact,
            "build_adapter": self.build_adapter,
            "capability_class": self.capability_class,
            "visibility": self.visibility,
            "aliases": list(self.aliases),
        }


@dataclass(frozen=True, slots=True)
class Invocation:
    component: ComponentDescriptor
    operation: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    authority: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.operation or not isinstance(self.operation, str):
            raise ValueError("operation must be a non-empty string")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))
        object.__setattr__(self, "authority", _freeze_mapping(self.authority))

    def envelope(self) -> dict[str, Any]:
        return {
            "schema": REQUEST_SCHEMA,
            "component": self.component.name,
            "source_revision": self.component.revision,
            "operation": self.operation,
            "payload": dict(self.payload),
            "authority": dict(self.authority),
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.envelope())


@dataclass(frozen=True, slots=True)
class InvocationResult:
    component: ComponentDescriptor
    operation: str
    status: str
    output: Any
    receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.status not in _ALLOWED_STATES:
            raise ValueError(f"unsupported standing state: {self.status!r}")
        object.__setattr__(self, "receipt", _freeze_mapping(self.receipt))

    @classmethod
    def from_bytes(
        cls,
        component: ComponentDescriptor,
        operation: str,
        value: bytes,
    ) -> "InvocationResult":
        try:
            decoded = json.loads(value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("guest returned invalid UTF-8 JSON") from exc
        if not isinstance(decoded, dict):
            raise ValueError("guest response must be a JSON object")
        if decoded.get("schema") != RESPONSE_SCHEMA:
            raise ValueError(f"guest response schema must be {RESPONSE_SCHEMA!r}")
        receipt = decoded.get("receipt")
        if not isinstance(receipt, dict):
            raise ValueError("guest response must include a receipt object")
        subject = receipt.get("subject")
        if not isinstance(subject, dict):
            raise ValueError("receipt must include a subject object")
        if subject.get("component") != component.name:
            raise ValueError("receipt component identity does not match the invoked component")
        if subject.get("source_revision") != component.revision:
            raise ValueError("receipt source revision does not match the registry pin")
        return cls(
            component=component,
            operation=operation,
            status=str(decoded.get("status", "UNKNOWN")),
            output=decoded.get("output"),
            receipt=receipt,
        )
