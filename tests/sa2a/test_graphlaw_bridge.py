"""Unit tests for Praxis GraphLaw WASM bridge in Python SA2A."""

from __future__ import annotations

import pytest
from autofde_lab.sa2a.admission.graphlaw_bridge import GraphLawBridge


def test_graphlaw_version_and_hash():
    bridge = GraphLawBridge()
    version = bridge.version()
    assert "praxis-graphlaw" in version

    digest = bridge.blake3_hex("hello world")
    assert len(digest) == 64
    assert digest == "d74981efa70a0c880b8d8c1985d075dbcbf679b99a5f9914e5aaf96b831a9e24"


def test_graphlaw_validate_all_clean():
    bridge = GraphLawBridge()
    sample_ttl = """
    @prefix ex: <http://example.org/> .
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    ex:item1 rdf:type ex:Item ;
             ex:value "42" .
    """
    res = bridge.validate_all(sample_ttl)
    assert res.conforms is True
    assert len(res.graph_hash) == 64
    assert res.replay_status == "ADMITTED"
    assert any(d.dialect == "DATALOG" for d in res.dialects)
    assert any(d.dialect == "N3_DENIAL" for d in res.dialects)
