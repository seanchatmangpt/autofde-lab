# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Permanent tripwire for the Chicago Crown release-fence wiring.

Guards the law exercised on 2026-09-17 (release v26.9.17 certify-prep): the
CHI-ID fence in ``ChicagoCrownQualificationRunner`` certifies ``git rev-parse
HEAD`` against ``git rev-list -n 1 <release_tag>`` — there is no override. The
``release_tag`` constant is the single source of truth for that fence, and the
OCEL release-artifact identity (``urn:release:<tag>``) must be *derived* from
it, never hardcoded beside it. A hardcoded URN lets the receipt claim one
release while the fence certifies another (or the OCEL trace names a release
the fence never checked). This test fails if a second release constant, a
stale ``urn:release:v*`` literal, or the ``release_urn`` derivation is lost.
"""

from __future__ import annotations

import re
from pathlib import Path

RUNNER_SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "autofde_lab"
    / "sa2a"
    / "conformance"
    / "runner.py"
)


def test_release_tag_is_a_single_constant_and_release_urn_is_derived() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")

    assignments = re.findall(r'^\s*release_tag\s*=\s*"[^"]+"\s*$', source, re.MULTILINE)
    assert len(assignments) == 1, (
        "runner.py must declare exactly one release_tag constant; found "
        f"{len(assignments)}: {assignments}"
    )

    derivation = re.search(r'release_urn\s*=\s*f"urn:release:\{release_tag\}"', source)
    assert derivation is not None, (
        "runner.py must derive release_urn from release_tag "
        '(release_urn = f"urn:release:{release_tag}") so the OCEL release '
        "identity cannot drift from the CHI-ID fence"
    )


def test_no_hardcoded_release_urn_literals_remain_in_runner() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")

    stale = re.findall(r'"urn:release:v[^"]*"', source)
    assert not stale, (
        "runner.py hardcodes release URN literals; every reference must use "
        f"the release_urn derivation (stale literals: {stale})"
    )


def test_chi_id_is_the_first_gate_and_fences_exact_identity() -> None:
    from autofde_lab.sa2a.conformance.runner import ChicagoCrownQualificationRunner

    first = ChicagoCrownQualificationRunner.GATE_SPECS[0]
    assert first[0] == "CHI-ID"
    assert first[1] == "Gate01_ExactIdentityFenced"
    assert len(ChicagoCrownQualificationRunner.GATE_SPECS) == 12
