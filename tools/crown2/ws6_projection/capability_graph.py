#!/usr/bin/env python3
"""
capability_graph.py — WS6 Domain Regeneration.

Canonical, content-addressed CapabilityGraph plus two pure functions:

    add_qualified(graph, receipt) -> (new_graph, digest)
        Returns a NEW graph. The input graph is never mutated.

    project_domain(graph, world_state, authority) -> Domain
        Domain = {"actions": [...], "preconditions": {...}, "digest": str}
        Same inputs => same digest, independent of dict key insertion order.

Invariants (each has a falsifier in test_ws6_projection.py):
  I1  digest(g) == digest(canonical(g)) for any key order of g.
  I2  add_qualified never mutates its input (input digest unchanged after call).
  I3  project_domain is referentially transparent: repeated/shuffled-key calls
      yield byte-identical canonical JSON and identical digest.
  I4  The domain is constructed, never accumulated: no list-append call on
      any action list anywhere in this package (grep-enforced in tests).
  I5  store: file name == sha256(canonical bytes); load re-verifies.

Schema (all keys sorted on canonicalization):

  CapabilityGraph = {
    "schema": "ws6.capability_graph/1",
    "capabilities": {
       <capability_id>: {
          "action": str,                # action name exposed in the domain
          "preconditions": [str,...],   # facts required in world_state.facts
          "effects": [str,...],         # facts asserted after the action
          "scopes": [str,...],          # authority scopes required
          "qualification_run_id": str,  # provenance: the QualificationRun
          "evidence_digest": str        # provenance: digest of the evidence
       }
    }
  }

  WorldState = {"facts": [str,...]}          (extra keys ignored, but hashed)
  Authority  = {"scopes": [str,...]}         (extra keys ignored, but hashed)

Stdlib only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "ws6.capability_graph/1"
DOMAIN_SCHEMA = "ws6.domain_projection/1"


# ---------------------------------------------------------------------------
# Canonicalization / content addressing
# ---------------------------------------------------------------------------


def canonical_bytes(obj: Any) -> bytes:
    """RFC-8785-style canonical JSON: sorted keys, no whitespace, ASCII."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def digest_of(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(obj)).hexdigest()


# ---------------------------------------------------------------------------
# CapabilityGraph
# ---------------------------------------------------------------------------


def empty_graph() -> dict[str, Any]:
    return {"schema": SCHEMA, "capabilities": {}}


def graph_digest(graph: dict[str, Any]) -> str:
    _check_graph(graph)
    return digest_of(graph)


def _check_graph(graph: dict[str, Any]) -> None:
    if graph.get("schema") != SCHEMA:
        raise ValueError(f"graph schema must be {SCHEMA!r}, got {graph.get('schema')!r}")
    caps = graph.get("capabilities")
    if not isinstance(caps, dict):
        raise ValueError("graph.capabilities must be an object keyed by capability_id")
    for cid, cap in caps.items():
        for key in ("action", "preconditions", "effects", "scopes",
                    "qualification_run_id", "evidence_digest"):
            if key not in cap:
                raise ValueError(f"capability {cid!r} missing {key!r}")


@dataclass(frozen=True)
class QualifiedCapabilityReceipt:
    """Provenance-bearing claim that a capability passed qualification."""

    capability_id: str
    action: str
    qualification_run_id: str
    evidence_digest: str
    preconditions: tuple[str, ...] = field(default_factory=tuple)
    effects: tuple[str, ...] = field(default_factory=tuple)
    scopes: tuple[str, ...] = field(default_factory=tuple)

    def to_capability(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "preconditions": sorted(set(self.preconditions)),
            "effects": sorted(set(self.effects)),
            "scopes": sorted(set(self.scopes)),
            "qualification_run_id": self.qualification_run_id,
            "evidence_digest": self.evidence_digest,
        }


def add_qualified(
    graph: dict[str, Any], receipt: QualifiedCapabilityReceipt
) -> tuple[dict[str, Any], str]:
    """Return (new_graph, new_digest). `graph` is left untouched."""
    _check_graph(graph)
    if not receipt.capability_id:
        raise ValueError("receipt.capability_id must be non-empty")
    if receipt.capability_id in graph["capabilities"]:
        raise ValueError(
            f"capability {receipt.capability_id!r} already present; graph is append-only "
            "by new id (re-qualification must use a new capability_id)"
        )
    new_caps = dict(copy.deepcopy(graph["capabilities"]))
    new_caps[receipt.capability_id] = receipt.to_capability()
    new_graph = {"schema": SCHEMA, "capabilities": new_caps}
    return new_graph, digest_of(new_graph)


# ---------------------------------------------------------------------------
# Content-addressed store (JSON on disk)
# ---------------------------------------------------------------------------


def save_graph(store_dir: str, graph: dict[str, Any]) -> str:
    """Write graph as <store_dir>/<sha256hex>.json; return the path."""
    d = graph_digest(graph)
    os.makedirs(store_dir, exist_ok=True)
    path = os.path.join(store_dir, d.split(":", 1)[1] + ".json")
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(canonical_bytes(graph))
        f.write(b"\n")
    os.replace(tmp, path)
    return path


def load_graph(path: str) -> dict[str, Any]:
    """Load a graph and verify the file name matches its content digest."""
    with open(path, "rb") as f:
        graph = json.loads(f.read())
    expected = os.path.basename(path)[: -len(".json")]
    actual = graph_digest(graph).split(":", 1)[1]
    if expected != actual:
        raise ValueError(f"content-address mismatch: file {expected} != content {actual}")
    return graph


# ---------------------------------------------------------------------------
# Domain projection (pure)
# ---------------------------------------------------------------------------


def project_domain(
    graph: dict[str, Any], world_state: dict[str, Any], authority: dict[str, Any]
) -> dict[str, Any]:
    """
    Pure projection: Domain = f(graph, world_state, authority).

    An action is admitted iff
      - every required scope is granted by `authority.scopes`, and
      - every precondition is a fact present in `world_state.facts`.
    Preconditions of admitted actions are exposed under `preconditions`
    (keyed by action name) so the consumer can re-check them at act time.

    The returned dict is built in one expression from sorted views; there is
    no accumulation, no `.append`, and the digest covers the full inputs so
    that a different world_state or authority always yields a different
    domain digest even when the admitted action set happens to coincide.
    """
    _check_graph(graph)
    facts = frozenset(world_state.get("facts", ()))
    scopes = frozenset(authority.get("scopes", ()))

    admitted = {
        cap["action"]: sorted(cap["preconditions"])
        for _cid, cap in sorted(graph["capabilities"].items())
        if frozenset(cap["scopes"]) <= scopes
        and frozenset(cap["preconditions"]) <= facts
    }
    body = {
        "schema": DOMAIN_SCHEMA,
        "graph_digest": digest_of(graph),
        "world_state_digest": digest_of(world_state),
        "authority_digest": digest_of(authority),
        "actions": sorted(admitted),
        "preconditions": admitted,
    }
    return {**body, "digest": digest_of(body)}


def domain_digest(domain: dict[str, Any]) -> str:
    """Recompute a domain's digest from its body (falsifier for tampering)."""
    body = {k: v for k, v in domain.items() if k != "digest"}
    return digest_of(body)
