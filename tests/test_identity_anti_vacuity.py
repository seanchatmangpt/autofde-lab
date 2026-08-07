# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Anti-vacuity guards for the identity surfaces a rename can silently break.

`importlib.metadata.entry_points(group=...)` returns an empty collection for
an unknown group rather than raising. A stale entry-point group name after a
partial rename therefore degrades to "zero domains, zero solvers" with no
error anywhere in the stack -- a valid-looking, capability-less system. These
tests pin the live counts so that degradation fails loudly instead.

As of this commit the live package is still `skdecide` (Phase 3 of the
AutoFDE Lab rename has not landed), so these assert against the LEGACY
entry-point groups in tests/project_identity.py. When Phase 3-4 land, flip
the group constants these use to the primary ones -- do not delete the
counts, they do not change.
"""

from __future__ import annotations

import importlib.metadata

from project_identity import (
    EXPECTED_DOMAIN_COUNT,
    EXPECTED_SOLVER_COUNT,
    LEGACY_DOMAIN_ENTRYPOINT_GROUP,
    LEGACY_SOLVER_ENTRYPOINT_GROUP,
)


def _entries(group: str):
    return list(importlib.metadata.entry_points(group=group))


def test_domain_registry_is_not_silently_empty():
    entries = _entries(LEGACY_DOMAIN_ENTRYPOINT_GROUP)
    assert entries, (
        f"entry-point group {LEGACY_DOMAIN_ENTRYPOINT_GROUP!r} returned zero "
        "entries -- either the group name is stale or pyproject.toml drifted"
    )
    assert len(entries) == EXPECTED_DOMAIN_COUNT, (
        f"expected {EXPECTED_DOMAIN_COUNT} domains, found {len(entries)}: "
        f"{sorted(e.name for e in entries)}"
    )


def test_solver_registry_is_not_silently_empty():
    entries = _entries(LEGACY_SOLVER_ENTRYPOINT_GROUP)
    assert entries, (
        f"entry-point group {LEGACY_SOLVER_ENTRYPOINT_GROUP!r} returned zero "
        "entries -- either the group name is stale or pyproject.toml drifted"
    )
    assert len(entries) == EXPECTED_SOLVER_COUNT, (
        f"expected {EXPECTED_SOLVER_COUNT} solvers, found {len(entries)}: "
        f"{sorted(e.name for e in entries)}"
    )


def test_get_registered_domains_matches_the_entrypoint_count():
    from skdecide.utils import get_registered_domains

    domains = get_registered_domains()
    assert domains, "get_registered_domains() returned nothing"
    assert len(domains) == EXPECTED_DOMAIN_COUNT


def test_get_registered_solvers_matches_the_entrypoint_count():
    from skdecide.utils import get_registered_solvers

    solvers = get_registered_solvers()
    assert solvers, "get_registered_solvers() returned nothing"
    assert len(solvers) == EXPECTED_SOLVER_COUNT
