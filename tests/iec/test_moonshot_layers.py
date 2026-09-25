"""Evidence tests for IEC's parser, routing, receipt, and equivalence layers."""

from __future__ import annotations

from pathlib import Path

import pytest

from autofde_lab.iec.equivalence import EquivalenceCourt
from autofde_lab.iec.filesystem import PassiveRepositoryReader, ReadPolicy
from autofde_lab.iec.manufacture import (
    ManufactureRequirement,
    ManufactureRouter,
    ecosystem_capabilities,
)
from autofde_lab.iec.model import (
    ClaimCeiling,
    EquivalenceDimension,
    RepositorySubject,
)
from autofde_lab.iec.observations import ObservationExtractor, PassiveFile
from autofde_lab.iec.probe import ProbeCandidate, ProbePlanner
from autofde_lab.iec.python_api import extract_python_api, python_api_verifier
from autofde_lab.iec.rdf_projection import project_repository, projection_digest
from autofde_lab.iec.receipts import IECStage, ReceiptChain
from autofde_lab.iec.structural import ParseStanding, StructuralParserRegistry
from autofde_lab.iec.tree import (
    TreeEntry,
    TreeSnapshot,
    compare_trees,
    tree_equivalence_verifier,
)


def subject(name: str = "seanchatmangpt/example") -> RepositorySubject:
    return RepositorySubject(
        repository=name,
        revision="a" * 40,
        default_branch="main",
    )


def test_structural_python_parser_normalizes_ast_without_source_locations() -> None:
    registry = StructuralParserRegistry()
    document = registry.parse(
        path="src/example.py",
        content=b"def f(x: int = 1) -> int:\n    return x + 1\n",
        source_digest="sha256:source",
    )
    assert document.standing is ParseStanding.OBSERVED
    assert document.language == "python"
    assert document.structure["_type"] == "Module"
    assert "lineno" not in repr(document.structure)
    assert document.structure_digest


def test_structural_parser_preserves_syntax_failure() -> None:
    registry = StructuralParserRegistry()
    document = registry.parse(
        path="broken.py",
        content=b"def broken(:\n",
        source_digest="sha256:broken",
    )
    assert document.standing is ParseStanding.BUILD_BROKEN
    assert document.structure is None
    assert document.diagnostic


def test_structural_parser_preserves_unsupported_language() -> None:
    document = StructuralParserRegistry().parse(
        path="module.rs",
        content=b"fn main() {}",
        source_digest="sha256:rs",
    )
    assert document.standing is ParseStanding.UNSUPPORTED
    assert document.diagnostic == "UNSUPPORTED_LANGUAGE:.rs"


def test_structural_json_and_toml_are_deterministic() -> None:
    registry = StructuralParserRegistry()
    json_doc = registry.parse(
        path="a.json",
        content=b'{"b": 2, "a": 1}',
        source_digest="sha256:j",
    )
    toml_doc = registry.parse(
        path="a.toml",
        content=b"[x]\na = 1\n",
        source_digest="sha256:t",
    )
    assert json_doc.structure == {"b": 2, "a": 1}
    assert toml_doc.structure == {"x": {"a": 1}}


def test_rdf_projection_is_sorted_and_exact_subject_bound() -> None:
    repo = subject()
    extractor = ObservationExtractor()
    artifacts, observations = extractor.extract_repository(
        repo,
        (
            PassiveFile("ontology/domain.ttl", b"@prefix ex: <urn:x:> ."),
            PassiveFile("src/a.py", b"def f(): return 1"),
        ),
    )
    first = project_repository(repo, artifacts, observations)
    second = project_repository(repo, reversed(artifacts), reversed(observations))
    assert first == second
    assert repo.revision in first
    assert projection_digest(first) == projection_digest(second)
    assert "RepositorySubject" in first


def test_receipt_chain_is_zero_authority_and_replay_linked() -> None:
    chain = ReceiptChain()
    first = chain.append(
        stage=IECStage.CORPUS_FREEZE,
        subject_ids=("s1",),
        input_ids=("manifest",),
        output_ids=("corpus",),
        result="OBSERVED",
    )
    second = chain.append(
        stage=IECStage.OBSERVE,
        subject_ids=("s1",),
        input_ids=("corpus",),
        output_ids=("observations",),
        result="OBSERVED",
    )
    assert first.authority == "NONE"
    assert second.previous_receipt == first.receipt_id
    assert chain.verify()


def test_probe_planner_prefers_information_gain_per_cost() -> None:
    candidates = (
        ProbeCandidate(
            "cheap-discriminator",
            1.0,
            {"h1": "a", "h2": "b", "h3": "a", "h4": "b"},
        ),
        ProbeCandidate(
            "expensive-discriminator",
            10.0,
            {"h1": "a", "h2": "b", "h3": "c", "h4": "d"},
        ),
        ProbeCandidate(
            "no-discrimination",
            0.5,
            {"h1": "x", "h2": "x", "h3": "x", "h4": "x"},
        ),
    )
    selected = ProbePlanner().select(candidates)
    assert selected.candidate.probe_id == "cheap-discriminator"
    assert selected.information_bits == 1.0


def test_tree_diff_is_exact_and_dimension_ready() -> None:
    left = TreeSnapshot.from_entries(
        "left",
        (
            TreeEntry("a.py", "sha256:a"),
            TreeEntry("b.py", "sha256:b"),
        ),
    )
    right = TreeSnapshot.from_entries(
        "right",
        (
            TreeEntry("a.py", "sha256:a"),
            TreeEntry("b.py", "sha256:B"),
            TreeEntry("c.py", "sha256:c"),
        ),
    )
    diff = compare_trees(left, right)
    assert diff.added == ("c.py",)
    assert diff.changed == ("b.py",)
    assert not diff.equal

    passed, expected, actual, detail = tree_equivalence_verifier(left, right)
    assert not passed
    assert expected["tree_digest"] == left.tree_digest
    assert actual["changed"] == ("b.py",)
    assert detail


def test_tree_verifier_plugs_into_equivalence_court() -> None:
    left = TreeSnapshot.from_entries("left", (TreeEntry("a", "sha256:a"),))
    right = TreeSnapshot.from_entries("right", (TreeEntry("a", "sha256:a"),))
    court = EquivalenceCourt()
    court.register(
        EquivalenceDimension.SYNTAX,
        "tree-exact/v1",
        tree_equivalence_verifier,
    )
    result = court.validate(
        original_subject_id="left",
        generated_subject_id="right",
        original=left,
        generated=right,
        dimensions=(EquivalenceDimension.SYNTAX,),
        claim_ceiling=ClaimCeiling.STRUCTURAL_EQUIVALENCE_ONLY,
    )
    assert result.passed


def test_passive_reader_refuses_symlink_and_binary(tmp_path: Path) -> None:
    (tmp_path / "text.txt").write_text("hello")
    binary = tmp_path / "binary.bin"
    binary.write_bytes(b"a\x00b")
    target = tmp_path / "target.txt"
    target.write_text("target")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    reader = PassiveRepositoryReader(tmp_path)
    assert reader.read("text.txt").content == b"hello"
    with pytest.raises(ValueError, match="UNSUPPORTED_BINARY"):
        reader.read("binary.bin")
    with pytest.raises(PermissionError, match="REFUSED_SYMLINK"):
        reader.read("link.txt")


def test_passive_reader_enforces_size_ceiling(tmp_path: Path) -> None:
    (tmp_path / "large.txt").write_bytes(b"x" * 11)
    reader = PassiveRepositoryReader(
        tmp_path,
        policy=ReadPolicy(max_file_bytes=10),
    )
    with pytest.raises(ValueError, match="UNSUPPORTED_FILE_SIZE"):
        reader.read("large.txt")


def test_manufacture_router_reuses_existing_ggen_create_capability() -> None:
    capabilities = ecosystem_capabilities(
        ggen_create_revision="ggen-create-sha",
        ggen_revision="ggen-sha",
        ggen_igniter_revision="igniter-sha",
    )
    router = ManufactureRouter(capabilities)
    requirement = ManufactureRequirement(
        input_kind="working-exemplar",
        output_kind="ggen-package",
        subject_id="subject",
    )
    route = router.route(requirement)
    assert route.routable
    assert len(route.steps) == 1
    assert route.steps[0].owner == "seanchatmangpt/ggen-create"
    assert route.steps[0].authority == "NONE"


def test_manufacture_router_returns_typed_unsupported_instead_of_inventing() -> None:
    router = ManufactureRouter()
    route = router.route(
        ManufactureRequirement(
            input_kind="unknown",
            output_kind="magic",
            subject_id="subject",
        )
    )
    assert not route.routable
    assert route.failure is not None
    assert route.failure.kind.value == "UNSUPPORTED_GENERATOR_CAPABILITY"


def test_python_api_extractor_ignores_private_symbols_and_preserves_signature() -> None:
    surface = extract_python_api(
        """
def public(x: int = 1, *, y: str = "a") -> bool:
    return True

def _private():
    return None

class Thing:
    def run(self, value: int) -> str:
        return str(value)

    def _hidden(self):
        return 1
""",
        module_name="example",
    )
    names = tuple(symbol.name for symbol in surface.symbols)
    assert names == ("Thing", "public")
    public = next(symbol for symbol in surface.symbols if symbol.name == "public")
    assert "x:int=1" in public.signature
    assert "y:str='a'" in public.signature


def test_python_api_verifier_detects_interface_drift() -> None:
    left = extract_python_api("def f(x): return x\n", module_name="a")
    right = extract_python_api("def f(x, y=1): return x+y\n", module_name="b")
    passed, expected, actual, _ = python_api_verifier(left, right)
    assert not passed
    assert expected != actual
