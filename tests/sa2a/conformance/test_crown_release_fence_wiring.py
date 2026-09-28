# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Permanent tripwire for the Chicago Crown release-fence wiring.

Guards the law exercised on 2026-09-17 (release v26.9.17 certify-prep): the
CHI-ID fence in ``ChicagoCrownQualificationRunner`` certifies ``git rev-parse
HEAD`` against ``git rev-list -n 1 <fence tag>``. Since WO-03 (commit 5d86b1cb) the
tag is *named at the invocation* (``release_tag=...``) instead of being hard-pinned,
because a hard pin made every later HEAD fail closed; the pinned default stays at the
tag the court was minted for. What must never change, and what this test guards:

* there is exactly one pinned default tag literal (the single source of truth when the
  caller names none);
* the OCEL release-artifact identity (``urn:release:<tag>``) is *derived* from the fence
  tag, never hardcoded beside it -- a hardcoded URN lets the receipt claim one release
  while the fence certifies another;
* the fence is exact identity: it compares HEAD to the tag's commit and passes on
  nothing else. Naming a tag is not a bypass, so no other path may set the gate result.
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


def test_fence_tag_has_one_pinned_default_and_release_urn_is_derived() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")

    # Any fallback literal for the tag, under any name, counts: a second pinned default
    # would be a second source of truth for the fence.
    fallbacks = re.findall(r'release_tag\s+or\s+"[^"]+"', source)
    assert len(fallbacks) == 1, (
        "runner.py must declare exactly one pinned default fence tag "
        f'(release_tag or "<tag>"); found {len(fallbacks)}: {fallbacks}'
    )
    assert re.search(
        r'^\s*fence_tag\s*=\s*release_tag\s+or\s+"[^"]+"\s*$', source, re.MULTILINE
    ), "the single pinned default must feed fence_tag"

    derivation = re.search(r'release_urn\s*=\s*f"urn:release:\{fence_tag\}"', source)
    assert derivation is not None, (
        "runner.py must derive release_urn from fence_tag "
        '(release_urn = f"urn:release:{fence_tag}") so the OCEL release '
        "identity cannot drift from the CHI-ID fence"
    )


def test_fence_is_exact_identity_and_naming_a_tag_is_not_a_bypass() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")

    assert re.search(r'\["git",\s*"rev-list",\s*"-n",\s*"1",\s*fence_tag\]', source), (
        "the fence must resolve the named tag with `git rev-list -n 1 <fence_tag>`"
    )
    assert re.search(
        r"tag_equality\s*=\s*bool\(exact_sha and \(exact_sha == tag_sha\)\)", source
    ), "the fence must compare HEAD to the tag's commit for exact equality"
    gate_assignments = re.findall(r"^\s*g1_passed\s*=\s*(.+)$", source, re.MULTILINE)
    assert gate_assignments == ["tag_equality"], (
        "Gate01 must pass on tag_equality and nothing else; found assignments "
        f"{gate_assignments}"
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
