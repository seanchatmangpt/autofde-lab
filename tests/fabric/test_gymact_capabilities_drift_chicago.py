# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style drift-detection test for
`src/autofde_lab/fabric/gymact_capabilities.toml`.

Real collaborators throughout: the real, installed
`gymact.gyms.sregym.SREGYM_CAPABILITIES` tuple (real import, no mock
substitute) and the real, on-disk `gymact_capabilities.toml`, parsed with
the real stdlib `tomllib`. Found this session: the file's own header
comment claimed exactly 5 real sregym capabilities exist and explicitly
denied any jaeger/loki/prometheus capability exists -- both now false; the
real upstream tuple has grown to 14. This test turns that drift into a
real, checkable failure instead of a comment that can go stale silently
again.

No `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere
in this file.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from gymact.gyms.sregym import SREGYM_CAPABILITIES

REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_PATH = REPO_ROOT / "src" / "autofde_lab" / "fabric" / "gymact_capabilities.toml"


def _real_upstream_binding_names() -> set[str]:
    return {capability.binding for capability in SREGYM_CAPABILITIES}


def _real_allowlisted_names() -> set[str]:
    manifest = tomllib.loads(_MANIFEST_PATH.read_text())
    return {entry["name"] for entry in manifest["capability"]}


def test_real_upstream_capability_count_is_fourteen_not_the_stale_five() -> None:
    """Confirms this session's real finding directly against the real,
    installed gymact package -- if upstream ever changes this count again,
    this test (not a comment) is what notices."""
    assert len(SREGYM_CAPABILITIES) == 14


def test_allowlist_is_a_real_subset_of_the_real_upstream_bindings() -> None:
    """Every real binding name in gymact_capabilities.toml must correspond
    to a real, currently-existing gymact.gyms.sregym.SREGYM_CAPABILITIES
    binding -- catches the allowlist ever drifting to reference a
    capability that no longer exists upstream."""
    allowlisted = _real_allowlisted_names()
    upstream = _real_upstream_binding_names()
    assert allowlisted, "the manifest must list at least one real capability"
    assert allowlisted <= upstream, f"allowlisted names not present upstream: {allowlisted - upstream}"


def test_allowlist_deliberately_excludes_the_nine_real_observability_capabilities() -> None:
    """Names the real, deliberate exclusion explicitly (per
    gymact_capabilities.toml's own 'adding a capability is a deliberate,
    reviewed act' rule) -- this must fail loudly if the 9 real jaeger/loki/
    prometheus capabilities are ever silently added to the allowlist
    without being named as a reviewed change."""
    allowlisted = _real_allowlisted_names()
    real_observability_bindings = {
        "jaeger_get_services",
        "jaeger_get_operations",
        "jaeger_get_traces",
        "jaeger_get_dependency_graph",
        "loki_get_logs",
        "loki_get_labels",
        "loki_get_label_values",
        "prometheus_get_metrics",
        "prometheus_get_alerts",
    }
    # Every one of these must be real, upstream bindings (confirms the "9"
    # count is accurate, not just asserted).
    assert real_observability_bindings <= _real_upstream_binding_names()
    # None are currently allowlisted -- this session deliberately left them
    # out pending their own review.
    assert allowlisted.isdisjoint(real_observability_bindings)
