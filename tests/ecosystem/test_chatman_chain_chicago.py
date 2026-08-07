# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Ecosystem Chicago test: scikit-decide inside the real Chatman chain.

This is the crown test. It differs from
``tests/domains/python/test_career_admission_unit.py`` in the way that
matters: it drives the REAL binaries and the REAL corpora of the sibling
repositories as subprocesses. Nothing here is mocked.

Discipline enforced by this file
--------------------------------
1. Where a prerequisite is genuinely absent, the test **skips with the exact
   blocker named** -- it never substitutes a fixture and proceeds as if the
   stage had run. A green run on a broken ecosystem would be worthless.
2. No artifact is treated as admitted merely because the component that
   produced it says so. `ggen`'s output is checked by `ggen receipt verify`,
   which is a separate verification path from `ggen sync run`.
3. Planner output is asserted to be a CANDIDATE. There is an explicit test
   that this repository emits no receipt and claims no admission, because
   "planning selects, the broker authorizes" is a boundary that a passing
   test suite should defend rather than quietly erode.

Per-stage standing, including the stages that cannot run today and the
repair plan for each, is recorded in ``docs/ecosystem-standing.md``.
"""

from __future__ import annotations

import json

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PDDL_FIXTURES = REPO_ROOT / "tests" / "domains" / "python" / "pddl_domains"
BLOCKS_DOMAIN = PDDL_FIXTURES / "blocks" / "domain.pddl"
BLOCKS_PROBLEM = PDDL_FIXTURES / "blocks" / "probBLOCKS-3-0.pddl"

HOME = Path.home()
MFW = HOME / "mfw"
GGEN_LEGACY = HOME / "ggen-legacy"

GL_PLANNING = GGEN_LEGACY / "planning" / "v26.8.1"
GL_CORE_DOMAIN = GL_PLANNING / "domains" / "ggen-v2681-core.pddl"
GL_GOVERNANCE_PROBLEM = GL_PLANNING / "problems" / "01-governance.pddl"

MFW_TICKET10_POWL = MFW / "runs" / "ticket-10" / "plan.powl.ttl"
MFW_TICKET10_PLAN = MFW / "runs" / "ticket-10" / "work" / "candidate.plan"

ENGINE = [sys.executable, "-m", "skdecide.fabric.pddl_engine"]

EXIT_PLAN_FOUND = 0
EXIT_NO_PLAN = 1
EXIT_REFUSED = 2
EXIT_USAGE = 3


def run_engine(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ENGINE + list(args),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=300,
    )


# ---------------------------------------------------------------------------
# Stage: plan computation -- the vacancy scikit-decide fills
# ---------------------------------------------------------------------------


class TestEngineSatisfiesMfwClassicalContract:
    """The engine must satisfy ~/mfw's real external-engine contract.

    Contract source: ``~/mfw/mfw-planner/src/config.rs`` (roles are a closed
    set; classical + output_mode="file" requires the placeholders
    ``{domain} {problem} {plan}``) and
    ``~/mfw/mfw-planner/fixtures/ticket-11/planner-profile.ttl`` (which pins
    a ``versionWitnessPrefix``). These assertions are what make the engine
    admissible at all -- they are not stylistic.
    """

    def test_version_witness_prefix_is_stable(self):
        """`--help` must start with the pinned witness prefix.

        ~/mfw's PlannerProfile declares `pddl:versionWitnessPrefix "usage:"`
        for fast-downward; matching it lets a skdecide engine be pinned the
        same way. Breaking this silently invalidates any profile.
        """
        result = run_engine("--help")
        assert result.returncode == EXIT_PLAN_FOUND
        assert result.stdout.startswith("usage:"), (
            "version witness must start with 'usage:' to be pinnable as "
            f"pddl:versionWitnessPrefix; got: {result.stdout[:80]!r}"
        )

    def test_three_positional_arguments_is_the_contract(self):
        """Exactly {domain} {problem} {plan} -- mfw's classical+file set."""
        result = run_engine(str(BLOCKS_DOMAIN), str(BLOCKS_PROBLEM))
        assert result.returncode == EXIT_USAGE

    def test_plan_written_to_file_not_stdout(self, tmp_path):
        """output_mode="file" means the plan goes to the path, not stdout."""
        plan = tmp_path / "out.plan"
        result = run_engine(str(BLOCKS_DOMAIN), str(BLOCKS_PROBLEM), str(plan))
        assert result.returncode == EXIT_PLAN_FOUND
        assert plan.exists()
        assert "(unstack" not in result.stdout, (
            "plan content must not leak to stdout under output_mode=file"
        )

    def test_plan_format_matches_mfw_committed_artifact(self, tmp_path):
        """Plan must be VAL-consumable, same shape as mfw's real run.

        Compared against ``~/mfw/runs/ticket-10/work/candidate.plan``, a
        genuine committed Fast Downward output.
        """
        if not MFW_TICKET10_PLAN.exists():
            pytest.skip(
                f"BLOCKED:MFW_ARTIFACT_ABSENT: {MFW_TICKET10_PLAN} not present"
            )
        reference = MFW_TICKET10_PLAN.read_text()
        assert reference.strip().splitlines()[0].startswith("(")
        assert "; cost =" in reference

        plan = tmp_path / "out.plan"
        run_engine(str(BLOCKS_DOMAIN), str(BLOCKS_PROBLEM), str(plan))
        produced = plan.read_text()
        action_lines = [
            line for line in produced.splitlines() if line.startswith("(")
        ]
        assert action_lines, "no ground action lines emitted"
        assert all(line.endswith(")") for line in action_lines)
        assert "; cost =" in produced, (
            "cost trailer missing; mfw's committed plan carries one"
        )

    def test_exit_codes_are_distinguishable(self, tmp_path):
        """A success_codes gate is vacuous if every failure looks alike."""
        missing = run_engine(
            str(tmp_path / "nope.pddl"),
            str(tmp_path / "nope2.pddl"),
            str(tmp_path / "o.plan"),
        )
        assert missing.returncode == EXIT_REFUSED
        assert missing.returncode != EXIT_NO_PLAN


class TestSilentWrongAnswerIsRefused:
    """The most important behavior in this file.

    scikit-decide's PDDL backend PARSES ``:derived-predicates``,
    ``:constraints`` and ``:preferences`` and then does not implement them
    -- verified this session: ``grep -rn "derived" cpp/src/hub/domain/pddl/
    semantics/`` returns zero hits, so derived atoms are never true and any
    action gated on one is silently never applicable. No exception is
    raised. Without a pre-flight gate the engine would emit a confident,
    plausible, WRONG plan, which is strictly worse than refusing because a
    wrong plan can be admitted downstream.
    """

    def test_unimplemented_requirements_are_refused_not_planned(self, tmp_path):
        if not GL_CORE_DOMAIN.exists():
            pytest.skip(
                f"BLOCKED:GGEN_LEGACY_CORPUS_ABSENT: {GL_CORE_DOMAIN} missing"
            )
        plan = tmp_path / "gl.plan"
        result = run_engine(
            str(GL_CORE_DOMAIN), str(GL_GOVERNANCE_PROBLEM), str(plan)
        )
        assert result.returncode == EXIT_REFUSED, (
            "engine must REFUSE a domain whose declared requirements it "
            "cannot implement, rather than emit a wrong plan"
        )
        assert "UNSUPPORTED_REQUIREMENT" in result.stdout
        for requirement in (":derived-predicates", ":constraints", ":preferences"):
            assert requirement in result.stdout, (
                f"refusal must name {requirement} precisely"
            )
        assert not plan.exists(), (
            "no plan file may be written when the domain is refused"
        )

    def test_gate_does_not_over_refuse_supported_domains(self, tmp_path):
        """The gate must not be a blanket refusal -- blocks still plans."""
        plan = tmp_path / "ok.plan"
        result = run_engine(str(BLOCKS_DOMAIN), str(BLOCKS_PROBLEM), str(plan))
        assert result.returncode == EXIT_PLAN_FOUND


class TestPowlProjection:
    """Plan -> POWL2 process model, in mfw's committed vocabulary.

    PDDL selects among admitted transitions; POWL is the process geometry
    that transition becomes. Validated against the real committed artifact
    ``~/mfw/runs/ticket-10/plan.powl.ttl``.
    """

    @pytest.fixture
    def projected(self, tmp_path):
        plan = tmp_path / "b.plan"
        powl = tmp_path / "b.powl.ttl"
        result = run_engine(
            str(BLOCKS_DOMAIN), str(BLOCKS_PROBLEM), str(plan), str(powl)
        )
        if result.returncode != EXIT_PLAN_FOUND:
            pytest.fail(f"engine failed: {result.stdout}\n{result.stderr}")
        return powl.read_text()

    def test_uses_mfw_powl2_vocabulary(self, projected):
        for term in (
            "powl2:Model",
            "powl2:PartialOrder",
            "powl2:ChildBinding",
            "powl2:ActivityLeaf",
            "powl2:activityLabel",
            "mfwp:ParameterBinding",
            "mfwp:planOrdinal",
            "mfwp:projection",
        ):
            assert term in projected, f"POWL projection missing {term}"

    def test_vocabulary_agrees_with_mfw_committed_artifact(self):
        """Terms we emit must actually appear in mfw's real POWL output."""
        if not MFW_TICKET10_POWL.exists():
            pytest.skip(
                f"BLOCKED:MFW_ARTIFACT_ABSENT: {MFW_TICKET10_POWL} missing"
            )
        reference = MFW_TICKET10_POWL.read_text()
        for term in (
            "powl2:Model",
            "powl2:PartialOrder",
            "powl2:ChildBinding",
            "powl2:ActivityLeaf",
            "mfwp:ParameterBinding",
            "mfwp:planOrdinal",
        ):
            assert term in reference, (
                f"{term} not in mfw's committed artifact -- our projection "
                "has drifted from the real vocabulary"
            )

    def test_digests_are_real_blake3_never_a_substitute(self, projected):
        """A sha256 under a `blake3:` label would be a forged identity.

        mfw pins executables and artifacts by blake3 and refuses on drift.
        Emitting a different algorithm under that prefix would mismatch with
        a misleading reason, so the projector refuses instead.
        """
        assert 'mfwp:domainDigest "blake3:' in projected
        digest = projected.split('mfwp:domainDigest "blake3:')[1].split('"')[0]
        assert len(digest) == 64, f"blake3 hex must be 64 chars, got {len(digest)}"

        b3sum = shutil.which("b3sum")
        if b3sum is None:
            pytest.skip("BLOCKED:B3SUM_ABSENT: cannot cross-check digest")
        expected = subprocess.run(
            [b3sum, "--no-names", str(BLOCKS_DOMAIN)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert digest == expected, (
            "emitted digest does not match an independent b3sum of the file"
        )

    def test_activity_count_matches_plan_length(self, tmp_path):
        plan = tmp_path / "c.plan"
        powl = tmp_path / "c.powl.ttl"
        run_engine(str(BLOCKS_DOMAIN), str(BLOCKS_PROBLEM), str(plan), str(powl))
        actions = [
            line for line in plan.read_text().splitlines() if line.startswith("(")
        ]
        turtle = powl.read_text()
        assert f'mfwp:activityCount "{len(actions)}"^^xsd:integer' in turtle


# ---------------------------------------------------------------------------
# Stage: independent verification -- ggen
# ---------------------------------------------------------------------------


GGEN_REPO = HOME / "ggen"
GGEN_BINARY_CANDIDATES = (
    Path("/opt/homebrew/bin/ggen"),
    GGEN_REPO / "target" / "debug" / "ggen",
    HOME / ".cargo" / "bin" / "ggen",
)


def _available_ggen_binaries() -> list[Path]:
    return [p for p in GGEN_BINARY_CANDIDATES if p.exists()]


def _verify_receipt(binary: Path) -> tuple[int, str, str]:
    result = subprocess.run(
        [str(binary), "receipt", "verify", "--format", "json"],
        capture_output=True,
        text=True,
        cwd=GGEN_REPO,
        timeout=120,
    )
    return result.returncode, result.stdout, result.stderr


class TestIndependentVerificationNotSelfAttestation:
    """An artifact is admitted only because an INDEPENDENT check says so.

    The invariant under test is stronger than "some verifier said yes": if
    the verdict depends on *which build of the verifier* happens to be on
    PATH, then "independently verified" is not a property of the artifact at
    all. These tests assert verifier agreement, not merely verifier success.
    """

    def test_at_least_one_verifier_admits_the_receipt(self):
        binaries = _available_ggen_binaries()
        if not binaries:
            pytest.skip("BLOCKED:GGEN_BINARY_ABSENT: no ggen build found")
        if not (GGEN_REPO / ".ggen-v2" / "receipt.json").exists():
            pytest.skip("BLOCKED:GGEN_RECEIPT_ABSENT: no receipt to verify")

        verdicts = {}
        for binary in binaries:
            code, stdout, _ = _verify_receipt(binary)
            verdicts[str(binary)] = (code, stdout)

        passing = [b for b, (code, _) in verdicts.items() if code == 0]
        assert passing, (
            "no available ggen build could verify the committed receipt:\n"
            + "\n".join(f"  {b}: exit {c}" for b, (c, _) in verdicts.items())
        )

        payload = json.loads(verdicts[passing[0]][1].strip().splitlines()[-1])
        assert payload["valid"] is True
        assert payload["signature_valid"] is True, (
            "receipt signature must verify -- an unsigned or badly signed "
            "receipt is not independent evidence"
        )

    def test_all_verifier_builds_agree_on_the_same_receipt(self):
        """Verifier builds must not disagree about identical bytes.

        KNOWN FAILING as of this session -- this is a real, reproduced
        ecosystem defect, not a flaky test:

            /opt/homebrew/bin/ggen   26.8.6 -> INVALID, recomputed chain
                                               23386d67ba4fe290...
            ./target/debug/ggen      26.8.6 -> valid, chain 918c5b0980...
            ~/.cargo/bin/ggen        26.8.6 -> valid, chain 918c5b0980...

        All three self-report version 26.8.6 and read the same git-tracked,
        unmodified `.ggen-v2/receipt.json`. The homebrew build's error text
        additionally MISATTRIBUTES the cause ("record fields were tampered
        with -- restore from git"), which would send an operator chasing a
        tampering incident that did not occur.

        This test is *conditionally* red, not unconditionally failing. It
        hard-fails only when two or more reachable ggen builds disagree about
        the same receipt bytes, and skips `BLOCKED:INSUFFICIENT_VERIFIER_BUILDS`
        when fewer than two are reachable.

        As of 2026-08-06 it PASSES, because `/opt/homebrew/bin/ggen` no longer
        exists on this machine and only two agreeing builds remain. That is a
        weaker result than three-of-three agreeing: EV-1's residual risk -- a
        `brew link` reintroducing the stale Cellar binary and restoring the
        disagreement -- is untested here, not disproven, and RP-1 stays open
        (docs/ecosystem-standing.md).

        Never xfail or skip it to make the suite green, and never relax the
        assertion: a red row here is a finding about the
        independent-verification stage, which is the one prohibited fix
        (tests/ecosystem/CLAUDE.md invariant 4).
        """
        binaries = _available_ggen_binaries()
        if len(binaries) < 2:
            pytest.skip(
                "BLOCKED:INSUFFICIENT_VERIFIER_BUILDS: need >=2 ggen builds "
                "to test agreement"
            )
        if not (GGEN_REPO / ".ggen-v2" / "receipt.json").exists():
            pytest.skip("BLOCKED:GGEN_RECEIPT_ABSENT: no receipt to verify")

        verdicts = {}
        for binary in binaries:
            code, stdout, stderr = _verify_receipt(binary)
            verdicts[str(binary)] = (code, (stdout + stderr).strip())

        codes = {code for code, _ in verdicts.values()}
        assert len(codes) == 1, (
            "ggen verifier builds DISAGREE about the same receipt bytes; "
            "an artifact's admission must not depend on which build is on "
            "PATH:\n"
            + "\n".join(
                f"  {b}: exit {c}\n    {out.splitlines()[-1][:160] if out else ''}"
                for b, (c, out) in verdicts.items()
            )
        )


class TestPlannerOutputIsCandidateNotActuation:
    """Defends the boundary: planning selects, the broker authorizes.

    These assertions exist so that a future change which quietly gives the
    planner receipt/admission semantics fails a test instead of sliding in.
    """

    def test_engine_emits_no_receipt(self, tmp_path):
        plan = tmp_path / "d.plan"
        powl = tmp_path / "d.powl.ttl"
        run_engine(str(BLOCKS_DOMAIN), str(BLOCKS_PROBLEM), str(plan), str(powl))
        produced = {p.name for p in tmp_path.iterdir()}
        assert produced == {"d.plan", "d.powl.ttl"}, (
            f"engine wrote unexpected artifacts: {produced}. A planner emits "
            "candidates only -- receipts belong to the broker/verifier."
        )

    def test_powl_projection_claims_no_admission(self, tmp_path):
        plan = tmp_path / "e.plan"
        powl = tmp_path / "e.powl.ttl"
        run_engine(str(BLOCKS_DOMAIN), str(BLOCKS_PROBLEM), str(plan), str(powl))
        turtle = powl.read_text()
        for forbidden in ("Admitted", "admitted", "ALIVE", "receipt("):
            assert forbidden not in turtle, (
                f"POWL projection must not assert {forbidden!r}; it is a "
                "candidate process model, not an admitted consequence"
            )


# ---------------------------------------------------------------------------
# Stage: ontology-governed capability discovery and coverage
# ---------------------------------------------------------------------------

ONTOLOGY = REPO_ROOT / "ontology" / "skdecide-capabilities.ttl"


class TestOntologyIsGeneratedNotCurated:
    """The ontology must be derived from the live registry, not hand-written.

    Motivated by a real failure this session: an ecosystem-wide claim ("no
    POWL executor exists") was made from a search that had never looked at
    ~/bcinr, which contains one. A capability inventory that depends on which
    repositories someone happened to inspect is not an inventory. The same
    applies within this repo -- a hand-maintained list drifts silently from
    the entry points, and the drift is invisible precisely when it matters.
    """

    def test_ontology_file_exists(self):
        assert ONTOLOGY.exists(), (
            f"{ONTOLOGY} missing; regenerate with "
            "`python -m skdecide.fabric.ontology ontology/skdecide-capabilities.ttl`"
        )

    def test_ontology_matches_live_registry_exactly(self):
        """Fails if any registered capability is absent from the ontology.

        This is the anti-omission invariant. Registering a new solver without
        regenerating the ontology breaks this test, so a capability cannot
        enter the codebase and stay invisible to the coverage report.
        """
        from skdecide import utils
        from skdecide.fabric.coverage import load_ontology

        solvers, domains = load_ontology(str(ONTOLOGY))
        live_solvers = set(utils.get_registered_solvers())
        live_domains = set(utils.get_registered_domains())

        assert set(solvers) == live_solvers, (
            "ontology solvers drifted from the registry.\n"
            f"  missing from ontology: {sorted(live_solvers - set(solvers))}\n"
            f"  stale in ontology:     {sorted(set(solvers) - live_solvers)}"
        )
        assert set(domains) == live_domains, (
            "ontology domains drifted from the registry.\n"
            f"  missing from ontology: {sorted(live_domains - set(domains))}\n"
            f"  stale in ontology:     {sorted(set(domains) - live_domains)}"
        )

    def test_ontology_covers_every_declared_kind(self):
        """The anti-omission invariant, widened past the two entry-point groups.

        ``test_ontology_matches_live_registry_exactly`` compares only
        ``skdecide.domains`` and ``skdecide.solvers`` -- the same two groups
        ``collect_capabilities`` walked -- so it could not fail on a missing
        POWL / agent-lifecycle / OCEL / adapter term no matter how stale the
        file got. This closes that hole: every kind the generator declares is
        compared against what the committed artifact actually contains.
        """
        from skdecide.fabric.ontology import (
            ALL_KINDS,
            capabilities_of_kind,
            collect_capabilities,
            parse_kinds,
        )

        live = collect_capabilities()
        emitted = parse_kinds(ONTOLOGY.read_text())

        for kind in ALL_KINDS:
            expected = set(capabilities_of_kind(live, kind))
            assert expected, f"no live {kind} terms; the walk found nothing"
            found = set(emitted[kind])
            assert found == expected, (
                f"ontology {kind} terms drifted from the live registry.\n"
                f"  missing from ontology: {sorted(expected - found)}\n"
                f"  stale in ontology:     {sorted(found - expected)}\n"
                "  regenerate: python -m skdecide.fabric.ontology "
                "ontology/skdecide-capabilities.ttl"
            )

    def test_vocabulary_terms_carry_an_explicit_claim_ceiling(self):
        """An ALIVE row for a declared term must not read as a capability claim."""
        from skdecide.fabric.ontology import IN_PROCESS_KINDS, parse_kinds

        emitted = parse_kinds(ONTOLOGY.read_text())
        for kind in IN_PROCESS_KINDS:
            assert emitted[kind], f"no {kind} terms emitted"  # not a vacuous pass
            for identifier, record in emitted[kind].items():
                ceiling = record.get("skdt:claimCeiling") or []
                assert ceiling, f"{kind}/{identifier} has no skdt:claimCeiling"

    def test_adapter_standing_is_not_baked_from_a_local_probe(self):
        """A host-dependent probe result must never become a committed fact."""
        from skdecide.fabric.ontology import parse_kinds

        emitted = parse_kinds(ONTOLOGY.read_text())
        assert emitted["Adapter"], "no adapters in the ontology"
        for identifier, record in emitted["Adapter"].items():
            assert record["skdt:standing"] == ["UNKNOWN"], (
                f"adapter {identifier} carries standing "
                f"{record['skdt:standing']}; availability is host-dependent "
                "and must stay UNKNOWN in a committed artifact"
            )

    def test_requirements_are_derived_not_asserted(self):
        """Ontology requirements must match get_domain_requirements() exactly."""
        from skdecide import utils
        from skdecide.fabric.coverage import load_ontology

        solvers, _ = load_ontology(str(ONTOLOGY))
        checked = 0
        for name, record in solvers.items():
            solver_class = utils.load_registered_solver(name)
            if solver_class is None:
                continue
            derived = sorted(
                req.__name__ for req in solver_class.get_domain_requirements()
            )
            assert sorted(record["requirements"]) == derived, (
                f"{name}: ontology requirements {sorted(record['requirements'])} "
                f"!= derived {derived}"
            )
            checked += 1
        assert checked > 20, f"only {checked} solvers cross-checked"

    def test_unimplemented_pddl_requirements_are_first_class_facts(self):
        """The silent-wrong-answer hazard must live in the ontology.

        If it exists only as a constant in one module, nothing outside that
        module can reason about it.
        """
        turtle = ONTOLOGY.read_text()
        for requirement in (":derived-predicates", ":constraints", ":preferences"):
            assert requirement in turtle, f"{requirement} absent from ontology"
        assert 'skdt:standing "UNSUPPORTED"' in turtle


class TestCapabilityCoverageIsComplete:
    """Every declared capability is selected, compared, or excluded with cause.

    "Use all available capabilities" cannot mean forcing every solver to run
    regardless of semantics. It means: enumerate the complete admitted set,
    exercise everything that can lawfully contribute, compare alternatives
    that solve the same subproblem, and produce evidence for every exclusion.
    """

    @pytest.fixture(scope="class")
    def report(self):
        from skdecide.fabric.coverage import build_report
        from skdecide.hub.domain.career_admission import CareerAdmission

        if not ONTOLOGY.exists():
            pytest.skip("BLOCKED:ONTOLOGY_ABSENT")
        return build_report(lambda: CareerAdmission(), str(ONTOLOGY))

    def test_no_capability_silently_omitted(self, report):
        """THE key invariant from the coverage requirement."""
        from skdecide.fabric.coverage import coverage_is_complete

        complete, problems = coverage_is_complete(report, str(ONTOLOGY))
        assert complete, "coverage incomplete:\n" + "\n".join(problems)

    def test_every_capability_classified_exactly_once(self, report):
        names = [row.capability for row in report]
        assert len(names) == len(set(names)), "a capability was classified twice"

    def test_every_exclusion_has_a_machine_readable_cause(self, report):
        """A free-text reason is not machine-readable; "it failed" is not actionable."""
        from skdecide.fabric.coverage import CAUSE_NONE

        for row in report:
            if row.disposition in ("excluded", "failed"):
                assert row.cause and row.cause != CAUSE_NONE, (
                    f"{row.capability}: excluded without a machine-readable cause"
                )
                assert row.reason.strip(), f"{row.capability}: empty reason"
                assert row.falsifier.strip(), f"{row.capability}: no falsifier"

    def test_comparison_actually_happened(self, report):
        """`match_solvers(ranked=True)` is a no-op, so ranking must be measured.

        `src/skdecide/utils.py:126` carries `# TODO: implement ranking
        heuristic` and always returns an unranked list. A "dominated" verdict
        that was not measured would therefore be an empty claim.
        """
        compared = [
            row
            for row in report
            if row.disposition in ("selected", "tied_optimal", "dominated")
        ]
        assert len(compared) >= 2, (
            "fewer than 2 capabilities were actually run and compared; a "
            "coverage claim without comparison is not a comparison"
        )
        for row in compared:
            assert "cost" in row.execution_evidence, (
                f"{row.capability}: claimed comparison without measured cost"
            )

    def test_applicable_and_available_capabilities_were_run(self, report):
        """No capability may be applicable, available, and simply skipped."""
        skipped = [
            row.capability
            for row in report
            if row.applicability == "applicable"
            and row.disposition not in ("selected", "tied_optimal", "dominated", "failed")
        ]
        assert not skipped, f"applicable capabilities never exercised: {skipped}"

    def test_report_is_machine_readable(self, report):
        from skdecide.fabric.coverage import report_to_json

        payload = json.loads(report_to_json(report))
        assert payload
        required = {
            "capability",
            "ontology_id",
            "owner",
            "applicability",
            "standing",
            "disposition",
            "cause",
            "reason",
            "execution_evidence",
            "falsifier",
        }
        for entry in payload:
            assert required.issubset(entry.keys()), (
                f"row missing fields: {required - set(entry.keys())}"
            )


# ---------------------------------------------------------------------------
# Stage: cross-repository recursive controller -- honestly reported absent
# ---------------------------------------------------------------------------


def test_recursive_bootstrap_controller_is_absent_across_ecosystem():
    """`Blocked -> spawn child -> manufacture -> verify -> admit -> resume`.

    Eleven Explore agents this session found no code implementing this loop
    in ~/mfw, ~/ggen, ~/ggen-create or ~/ggen-legacy. Its individual
    primitives are real; the orchestration is not. This test asserts the
    absence deliberately, so that the day someone implements it, this test
    fails and forces the standing doc to be updated rather than letting the
    claim drift.
    """
    controller = REPO_ROOT / "src" / "skdecide" / "fabric" / "recursive_controller.py"
    assert not controller.exists(), (
        "A recursive bootstrap controller now exists. Update "
        "docs/ecosystem-standing.md: this stage is no longer UNSUPPORTED."
    )
