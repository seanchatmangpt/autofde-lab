"""Content-Addressed Semantic Exchange Package for cross-runtime interoperation.

RFC-SA2A-001 v26.9.16 §11, §12, §21, §26.
Binds canonical graph state, GraphLaw WASM component, SHACL shapes, Datalog rules,
transition events, and authority contracts into an immutable content-addressed package.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class WasmComponentRef:
    engine: str = "praxis-graphlaw-wasm"
    version: str = "26.7.5"
    artifact_sha256: str = ""


@dataclass(frozen=True)
class AuthorityContract:
    grant_id: str
    actor_id: str
    action_iri: str
    consequence_class: str
    constraints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticExchangePackage:
    spec_version: str = "SA2A-PROFILE-v26.9.16"
    package_id: str = ""
    wasm_component: WasmComponentRef = field(default_factory=WasmComponentRef)
    canonical_graph_ttl: str = ""
    profile_ttl: str = ""
    shacl_shapes: str = ""
    shex_schema: str = ""
    shex_shape_map: str = ""
    transition_event_ttl: str = ""
    authority_contract: AuthorityContract = field(
        default_factory=lambda: AuthorityContract(
            grant_id="grant-default",
            actor_id="actor-cross-runtime",
            action_iri="urn:action:transition",
            consequence_class="ConsequenceClass_bounded_local",
        )
    )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "spec_version": self.spec_version,
            "package_id": self.package_id,
            "wasm_component": {
                "engine": self.wasm_component.engine,
                "version": self.wasm_component.version,
                "artifact_sha256": self.wasm_component.artifact_sha256,
            },
            "canonical_graph_ttl": self.canonical_graph_ttl.strip(),
            "profile_ttl": self.profile_ttl.strip(),
            "shacl_shapes": self.shacl_shapes.strip(),
            "shex_schema": self.shex_schema.strip(),
            "shex_shape_map": self.shex_shape_map.strip(),
            "transition_event_ttl": self.transition_event_ttl.strip(),
            "authority_contract": {
                "grant_id": self.authority_contract.grant_id,
                "actor_id": self.authority_contract.actor_id,
                "action_iri": self.authority_contract.action_iri,
                "consequence_class": self.authority_contract.consequence_class,
                "constraints": dict(self.authority_contract.constraints),
            },
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        )

    @property
    def package_digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, data_str: str) -> SemanticExchangePackage:
        raw = json.loads(data_str)
        wasm_ref = WasmComponentRef(**raw.get("wasm_component", {}))
        auth = AuthorityContract(**raw.get("authority_contract", {}))
        return cls(
            spec_version=raw.get("spec_version", "SA2A-PROFILE-v26.9.16"),
            package_id=raw.get("package_id", ""),
            wasm_component=wasm_ref,
            canonical_graph_ttl=raw.get("canonical_graph_ttl", ""),
            profile_ttl=raw.get("profile_ttl", ""),
            shacl_shapes=raw.get("shacl_shapes", ""),
            shex_schema=raw.get("shex_schema", ""),
            shex_shape_map=raw.get("shex_shape_map", ""),
            transition_event_ttl=raw.get("transition_event_ttl", ""),
            authority_contract=auth,
        )
