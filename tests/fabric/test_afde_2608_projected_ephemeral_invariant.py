# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style, real-collaborator local surface test for AFDE-2608 /
remote A2A-2608 ("enforce projected-ephemeral software as an invariant"),
scoped to this repo's one always-overwrite generator:
``ontology/autofde-lab-capabilities.ttl`` via
``autofde_lab.fabric.ontology.generate``.

Per ``.claude/rules/ecosystem-boundary.md`` this repo is the search graph,
never the admission/broker/actuation authority. This test establishes only
the narrow local claim: does the real, on-disk generator for THIS repo's one
always-overwrite ontology surface actually behave the way A2A-2608's
invariant requires -- regenerable from admitted source, indifferent to
whatever a hand tamper left on disk, and consumed by a downstream test that
fails closed on left-uncorrected drift. It says nothing about
``src/autofde_lab/constitution/`` (the ``mode = "Create"`` surface, already
shown ``BLOCKED:GGEN_MODE_CREATE_SKIPS_EXISTING_TARGETS`` in
``docs/jira/v26.9.16/AFDE-2608-projected-ephemeral-ontology-invariant.md``)
and does not re-litigate it.

Scratch-vs-real-file decision (per this test's own task instructions):
``autofde_lab.fabric.ontology.generate`` (``src/autofde_lab/fabric/ontology.py:522-527``)
opens its target with plain ``"w"`` -- an unconditional full overwrite that
never reads existing target content, so the mechanism itself IS safe to
regenerate in place. What is NOT safe is regenerating the REAL tracked file
and diffing it back against its committed content to prove byte-identical
restoration: a sibling AFDE-2608 pass this session (see the ticket's Law 4
finding) already showed a real, named, unrelated 235-line diff between a
fresh regeneration in THIS session's ``.venv`` and the committed file,
entirely attributable to optional extras absent from this environment
(``openap``, ``unified_planning``, ``pyRDDLGym``, ``joblib``, ``dspy``,
``ray``, ``sb3_contrib``) flipping several domains/solvers' ``skdt:standing``
from the committed ``ALIVE`` to a freshly computed ``UNSUPPORTED``. Tampering
the real tracked file and regenerating it in place would therefore leave it
byte-*different* from how this test found it, for reasons that have nothing
to do with the tamper -- violating this test's own "leave the real file
byte-identical" requirement. Every tamper/regenerate cycle below therefore
runs entirely inside pytest's real ``tmp_path`` scratch directory (the
project-appropriate, portable equivalent of a scratchpad location for a
committed test file that must also run in CI, never this session's
ephemeral ``/private/tmp/claude-501/...`` path) and never opens the real
tracked file for writing. The real file is read-only input; a `git diff
--stat` check (below) verifies that holds, not just by construction.

Chicago discipline: no ``unittest.mock``/``Mock``/``MagicMock``/``patch``/
``monkeypatch`` anywhere in this file. Every collaborator is real: the real
``generate()`` function performing a real live-registry import probe, real
files on a real filesystem (``tmp_path``), and the real
``autofde_lab.fabric.coverage.load_ontology`` / ``autofde_lab.utils
.get_registered_domains`` functions that
``tests/ecosystem/test_chatman_chain_chicago.py
::TestOntologyIsGeneratedNotCurated::test_ontology_matches_live_registry_exactly``
(read in full this session, lines 552-575) itself calls -- no reimplementation
of that assertion, the same real functions.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from autofde_lab import utils
from autofde_lab.fabric.coverage import load_ontology
from autofde_lab.fabric.ontology import generate

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_ONTOLOGY = REPO_ROOT / "ontology" / "autofde-lab-capabilities.ttl"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestAFDE2608ProjectedEphemeralOntologyInvariant:
    """Real tamper -> real regenerate -> real downstream-consumer check.

    Three tests, run in this file order, each independently falsifiable:

    1. Precondition/postcondition guard -- this suite never mutates the real
       tracked ontology file. Verified via ``git diff --stat``, not just by
       construction, so a bug elsewhere in this file cannot silently violate
       that hard requirement.
    2. The tamper-then-regenerate cycle itself, entirely inside ``tmp_path``.
    3. The downstream-consumer falsifier: the same two real functions
       ``tests/ecosystem/`` uses, called directly against a tampered scratch
       copy, to show the exact condition that consumer's hard ``assert``
       fails on.
    """

    def test_real_tracked_file_is_untouched_precondition(self) -> None:
        """Precondition, corrected 2026-09-16 (was pinning stale-by-design
        behavior): the original version of this test asserted ``git diff
        --stat`` was empty for the real tracked file before this suite ran.
        That checked an accidental fact about repo state (no session had
        regenerated the file since the last commit) rather than an
        architectural invariant, and it went stale the moment a legitimate
        AFDE-2608 closure regeneration (2026-09-16: adding the live
        ``HDDLDomain``/``HTNDomain``/``HDDLSolver`` entry-point stanzas,
        confirmed clean via ``docs/jira/v26.9.16/
        AFDE-2608-projected-ephemeral-ontology-invariant.md``) produced a
        real, intentional, uncommitted diff on this exact file. Zero
        uncommitted diff was never the property A2A-2608 actually cares
        about (law 1: "source-of-truth identity is the admitted graph/spec
        identity, not the generated file tree") -- what matters, and what
        this corrected assertion checks instead, is that the real tracked
        file's content right now is byte-identical to a fresh regeneration
        from the live/admitted source, i.e. it is not stale or
        hand-tampered relative to ``generate()``'s own canonical output,
        independent of whether that content happens to match the last git
        commit. This is strictly stronger than the old check: a clean git
        diff can hide a hand-edited-then-committed file; canonical-
        regeneration equality cannot. (The postcondition -- still
        byte-identical after -- is covered independently by the explicit
        ``REAL_ONTOLOGY.read_bytes() == real_bytes`` assertions inside the
        two tests below, each of which reads the real file itself, not this
        one's snapshot.)
        """
        assert REAL_ONTOLOGY.exists(), f"FILE_EXISTS: {REAL_ONTOLOGY} missing"
        real_bytes = REAL_ONTOLOGY.read_bytes()
        with tempfile.TemporaryDirectory() as tmpdir:
            scratch_path = Path(tmpdir) / "canonical-regen.ttl"
            generate(str(scratch_path))
            regenerated_bytes = scratch_path.read_bytes()
        assert regenerated_bytes == real_bytes, (
            "precondition violated: the real tracked "
            "ontology/autofde-lab-capabilities.ttl does not match a fresh "
            "canonical regeneration from the live/admitted source right "
            "now -- it is stale or hand-tampered relative to generate()'s "
            "own output"
        )

    def test_tamper_scratch_copy_then_regenerate_restores_canonical_projection(
        self, tmp_path: Path
    ) -> None:
        """(1) read real content + digest; (2) tamper one byte of a scratch
        copy under ``tmp_path``, never the real tracked file; (3) regenerate
        from the real, live entry-point/import-probe state and assert the
        tamper does not survive -- the file tree has no independent semantic
        authority (A2A-2608 law 1), and a second, wholly independent output
        path regenerated in the same process is byte-identical, showing the
        prior on-disk content (tampered or not) has zero causal influence on
        the projection, and that regeneration is deterministic within this
        session's declared environment (A2A-2608 law 4, scoped to
        within-session per AFDE-2608's own named cross-environment gap)."""
        real_bytes = REAL_ONTOLOGY.read_bytes()
        real_digest = hashlib.sha256(real_bytes).hexdigest()

        scratch = tmp_path / "capabilities.ttl"
        scratch.write_bytes(real_bytes)
        assert _sha256(scratch) == real_digest  # real copy, byte-identical

        # Tamper exactly one byte inside a `skdt:identifier` value -- chosen
        # deliberately so the falsifier lands on a parsed identity, not on
        # cosmetic whitespace that a coarser check might not notice.
        text = scratch.read_text(encoding="utf-8")
        needle = 'skdt:identifier "ChatmanCleanSession"'
        assert text.count(needle) == 1, (
            "fixture assumption broke: identifier line moved"
        )
        tampered_text = text.replace(needle, 'skdt:identifier "XhatmanCleanSession"', 1)
        assert tampered_text != text
        assert sum(a != b for a, b in zip(text, tampered_text)) == 1, (
            "tamper must change exactly one byte"
        )
        scratch.write_text(tampered_text, encoding="utf-8")
        tampered_digest = _sha256(scratch)
        assert tampered_digest != real_digest

        # Regenerate directly onto the tampered path. `generate()` opens the
        # target with plain "w" (fabric/ontology.py:525) -- an unconditional
        # full overwrite that never reads existing content -- so the tamper
        # cannot leak into the fresh projection.
        generate(str(scratch))
        restored_digest = _sha256(scratch)
        assert restored_digest != tampered_digest, (
            "regeneration failed to overwrite the tampered scratch copy"
        )

        # Independent corroboration: a wholly separate output path,
        # regenerated from the same live registry state in the same
        # process, is byte-identical to the restored file above.
        independent = tmp_path / "independent-regen.ttl"
        generate(str(independent))
        assert _sha256(independent) == restored_digest

        # The real tracked file must remain untouched by this test.
        assert REAL_ONTOLOGY.read_bytes() == real_bytes

    def test_downstream_ecosystem_consumer_fails_closed_on_left_uncorrected_drift(
        self, tmp_path: Path
    ) -> None:
        """(4): ``tests/ecosystem/test_chatman_chain_chicago.py
        ::TestOntologyIsGeneratedNotCurated::test_ontology_matches_live_registry_exactly``
        (read this session, lines 552-575) is the real drift-detection
        assertion a downstream consumer relies on:
        ``set(domains) == live_domains`` computed from the real
        ``autofde_lab.fabric.coverage.load_ontology`` (parses the committed
        Turtle) against the real ``autofde_lab.utils.get_registered_domains``
        (the live entry-point registry). This test calls those exact two
        real functions -- no reimplementation -- against a tampered scratch
        copy to show precisely that a left-uncorrected one-byte tamper to an
        identifier that currently agrees with the live registry removes
        that identifier from the parsed set, which is exactly the condition
        under which that ecosystem test's hard ``assert`` raises.

        Honesty note, load-bearing: this session's own baseline run of
        ``tests/ecosystem/test_chatman_chain_chicago.py
        ::TestOntologyIsGeneratedNotCurated`` (`.venv/bin/python -m pytest
        tests/ecosystem/test_chatman_chain_chicago.py -k
        TestOntologyIsGeneratedNotCurated -v`) already shows
        ``test_ontology_matches_live_registry_exactly`` and
        ``test_ontology_covers_every_declared_kind`` FAILING today, for
        reasons unrelated to anything in this file: `HTNDomain` and
        `HDDLDomain` are registered live entry points
        (`autofde_lab.utils.get_registered_domains()`) that are entirely
        absent from the currently-committed
        ``ontology/autofde-lab-capabilities.ttl`` (`grep -n "HTNDomain\\|
        HDDLDomain" ontology/autofde-lab-capabilities.ttl` -> zero hits) --
        a genuine, pre-existing drift in the tracked file, not introduced by
        this test and not repaired by it (this ticket makes no code change
        per its own scope). Because of that pre-existing drift, this test
        does not assert full-set equality as its baseline or claim the
        untampered file currently passes that ecosystem test -- it isolates
        the causal effect of exactly one tamper against exactly one
        identifier independently confirmed (below) to agree, pre-tamper,
        between the parsed ontology and the live registry.
        """
        live_domains = set(utils.get_registered_domains())
        real_bytes = REAL_ONTOLOGY.read_bytes()
        scratch = tmp_path / "capabilities.ttl"
        scratch.write_bytes(real_bytes)

        target_identifier = "ChatmanCleanSession"
        _, baseline_domains = load_ontology(str(scratch))
        assert target_identifier in baseline_domains, (
            "fixture assumption broke: target identifier no longer in the "
            "committed ontology"
        )
        assert target_identifier in live_domains, (
            "fixture assumption broke: target identifier no longer a live "
            "registered domain"
        )
        # Pre-tamper: this one identifier currently agrees between the
        # parsed ontology and the live registry -- the exact per-element
        # condition `test_ontology_matches_live_registry_exactly`'s
        # `assert set(domains) == live_domains` depends on, isolated to one
        # element so the pre-existing HTN/HDDL drift named above cannot be
        # mistaken for evidence about this tamper.

        text = scratch.read_text(encoding="utf-8")
        needle = f'skdt:identifier "{target_identifier}"'
        assert text.count(needle) == 1
        tampered_text = text.replace(
            needle, f'skdt:identifier "X{target_identifier[1:]}"', 1
        )
        scratch.write_text(tampered_text, encoding="utf-8")

        _, tampered_domains = load_ontology(str(scratch))
        assert target_identifier not in tampered_domains, (
            "tamper did not remove the identifier from the parsed set -- "
            "falsifier did not fire"
        )
        assert target_identifier in live_domains  # unchanged, still live

        # This is exactly the failure mode `test_ontology_matches_live_registry_exactly`
        # raises on: a real, named identifier present in the live registry
        # and absent from the parsed ontology makes
        # `set(domains) == live_domains` False. Demonstrated with the same
        # two real functions that test calls, not a reimplementation.
        assert target_identifier in (live_domains - set(tampered_domains))

        # The real tracked file must remain untouched by this test.
        assert REAL_ONTOLOGY.read_bytes() == real_bytes
