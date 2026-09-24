"""IEC foundation: identity, census, anti-unification, templates, and the court.

Every repository here is a real git repository built in `tmp_path` with the real
`git` binary; every blob is read back through git plumbing. No collaborator is
replaced by a double.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from autofde_lab.iec.crowns.antiunify import anti_unify, apply, render, template_text, tokenize
from autofde_lab.iec.crowns.census import census, read_blob, tree_id
from autofde_lab.iec.crowns.corpus import (
    CorpusManifest,
    RepositorySubject,
    freeze_corpus,
    observe_checkout,
)
from autofde_lab.iec.crowns.court import (
    BLOB_IDENTITY,
    BYTE_IDENTITY,
    Verifier,
    VerifierResult,
    VerifierSet,
    git_blob_id,
    run_court,
)
from autofde_lab.iec.crowns.model import (
    ArtifactOrigin,
    EvidenceStrength,
    FactStanding,
    IECRefusal,
    Observation,
    Verdict,
    admit,
)
from autofde_lab.iec.crowns.templates import (
    chunk_depths,
    eex_chunks,
    literal_containment,
    split_frontmatter,
    tera_chunks,
)

REMOTE = "https://github.com/example/subject.git"


def git(repo: Path, *args: str, stdin: bytes | None = None) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], input=stdin, capture_output=True, check=True
    ).stdout.decode()


def make_repo(root: Path, files: dict[str, str], *, remote: str = REMOTE) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "iec@example.invalid")
    git(root, "config", "user.name", "IEC test")
    git(root, "remote", "add", "origin", remote)
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fixture")
    return root


def subject(repo: Path) -> RepositorySubject:
    return observe_checkout(
        repo,
        repository="example/subject",
        branch="main",
        visibility="public",
        inclusion_reason="test fixture",
    )


# -- identity -----------------------------------------------------------------


def test_observe_checkout_binds_exact_commit_and_tree(tmp_path):
    repo = make_repo(tmp_path / "r", {"a.txt": "a\n"})
    frozen = subject(repo)
    assert frozen.commit == git(repo, "rev-parse", "HEAD").strip()
    assert frozen.tree == git(repo, "rev-parse", "HEAD^{tree}").strip()
    assert frozen.uri == f"git:example/subject@{frozen.commit}"


def test_mismatched_remote_is_refused(tmp_path):
    repo = make_repo(
        tmp_path / "r", {"a.txt": "a\n"}, remote="https://github.com/other/thing"
    )
    with pytest.raises(IECRefusal) as refused:
        subject(repo)
    assert refused.value.code == "BLOCKED_CORPUS_IDENTITY"


def test_public_corpus_refuses_a_private_subject(tmp_path):
    repo = make_repo(tmp_path / "r", {"a.txt": "a\n"})
    frozen = subject(repo)
    private = RepositorySubject(**{**frozen.to_json(), "visibility": "private"})
    with pytest.raises(IECRefusal) as refused:
        freeze_corpus(
            [frozen, RepositorySubject(**{**private.to_json(), "repository": "x/y"})],
            revision="r1",
        )
    assert refused.value.code == "REFUSED_PRIVATE_IDENTITY_LEAK"


def test_manifest_round_trips_and_detects_tampering(tmp_path):
    frozen = subject(make_repo(tmp_path / "r", {"a.txt": "a\n"}))
    manifest = freeze_corpus([frozen], revision="r1")
    assert CorpusManifest.from_json(manifest.to_json()).id == manifest.id
    tampered = manifest.to_json()
    tampered["subjects"][0]["branch"] = "other"
    with pytest.raises(IECRefusal):
        CorpusManifest.from_json(tampered)


def test_observations_cannot_self_admit_and_admission_needs_a_named_pass():
    with pytest.raises(IECRefusal) as refused:
        Observation("s", "e", "1", "i", "p", 1, FactStanding.ADMITTED)
    assert refused.value.code == "REFUSED_SELF_ADMISSION"
    candidate = Observation("s", "e", "1", "i", "p", 1, FactStanding.INFERRED_CANDIDATE)
    with pytest.raises(IECRefusal):
        admit(candidate, {"verdict": "PASS", "subject": "s", "receipt_id": "r"})
    with pytest.raises(IECRefusal):
        admit(
            candidate,
            {
                "verdict": "COUNTEREXAMPLE",
                "subject": "s",
                "receipt_id": "r",
                "verifier_set_id": "v",
            },
        )
    admitted = admit(
        candidate,
        {"verdict": "PASS", "subject": "s", "receipt_id": "r", "verifier_set_id": "v"},
    )
    assert admitted.to_json()["standing"] == "ADMITTED"
    assert admitted.to_json()["admitted_by"]["verifier_set_id"] == "v"


# -- census -------------------------------------------------------------------


def test_census_origins_rest_on_explicit_evidence_only(tmp_path):
    repo = make_repo(
        tmp_path / "r",
        {
            "lib/generated.ex": "# GENERATED by ggen_igniter from priv/ggen/p/ontology.ttl.\n# Do not edit.\n",
            "lib/handwritten.ex": 'defmodule Support do\n  @moduledoc """\n  Hand-authored (not ggen-manufactured) real collaborator.\n',
            "lib/plain.ex": "defmodule Plain do\nend\n",
            "priv/templates/emits.ex.eex": "# GENERATED by ggen_igniter from x.\n<%= name %>\n",
            "native/Cargo.toml": "[package]\n",
            "native/Cargo.lock": "# This file is automatically @generated by Cargo.\nversion = 4\n",
            "mix.exs": "defmodule M do end\n",
            "mix.lock": "%{}\n",
        },
    )
    frozen = census(subject(repo), repo)
    origin = {
        record.path: (record.origin, record.origin_strength) for record in frozen.files
    }
    assert origin["lib/generated.ex"] == (
        ArtifactOrigin.GENERATED_PROJECTION,
        EvidenceStrength.EXPLICIT_DECLARATION,
    )
    assert frozen.file("lib/generated.ex").origin_evidence["producer"] == "ggen_igniter"
    assert origin["lib/handwritten.ex"] == (
        ArtifactOrigin.CANONICAL_SOURCE,
        EvidenceStrength.EXPLICIT_DECLARATION,
    )
    # absence of a marker is not evidence of hand authorship
    assert origin["lib/plain.ex"] == (ArtifactOrigin.UNKNOWN, EvidenceStrength.NONE)
    # a marker inside a template is text the template emits, not a claim about it
    assert origin["priv/templates/emits.ex.eex"][0] is ArtifactOrigin.UNKNOWN
    assert origin["native/Cargo.lock"] == (
        ArtifactOrigin.DERIVED_CACHE,
        EvidenceStrength.EXPLICIT_DECLARATION,
    )
    assert origin["mix.lock"] == (
        ArtifactOrigin.DERIVED_CACHE,
        EvidenceStrength.CONVENTION,
    )
    standings = {
        o.subject.rsplit(":", 1)[1]: o.standing
        for o in frozen.observations()
        if o.predicate == "iec:artifactOrigin"
    }
    assert standings["mix.lock"] is FactStanding.INFERRED_CANDIDATE
    assert standings["lib/plain.ex"] is FactStanding.UNKNOWN
    assert standings["lib/generated.ex"] is FactStanding.DERIVED_DETERMINISTIC


def test_census_reads_the_commit_not_the_working_tree(tmp_path):
    repo = make_repo(tmp_path / "r", {"a.txt": "committed\n"})
    frozen = subject(repo)
    (repo / "a.txt").write_text("edited after commit\n", encoding="utf-8")
    assert read_blob(frozen, repo, "a.txt") == b"committed\n"
    assert census(frozen, repo).file("a.txt").size == len(b"committed\n")


def test_census_types_gitlinks_and_refuses_symlinks(tmp_path):
    repo = make_repo(tmp_path / "r", {"a.txt": "a\n"})
    pinned = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{pinned},vendor/dep")
    git(repo, "commit", "-q", "-m", "gitlink")
    record = census(subject(repo), repo).file("vendor/dep")
    assert record.origin is ArtifactOrigin.EXTERNAL_VENDORED
    assert record.origin_evidence["pinned_commit"] == pinned

    (repo / "link").symlink_to("a.txt")
    git(repo, "add", "link")
    git(repo, "commit", "-q", "-m", "symlink")
    with pytest.raises(IECRefusal) as refused:
        census(subject(repo), repo)
    assert refused.value.code == "REFUSED_SYMLINK"


def test_tree_id_reproduces_git_and_detects_replacement(tmp_path):
    repo = make_repo(
        tmp_path / "r", {"a.txt": "a\n", "d/b.txt": "b\n", "d/e/c.txt": "c\n"}
    )
    frozen = subject(repo)
    records = census(frozen, repo).files
    entries = [(r.mode, r.object_id, r.path) for r in records]
    assert tree_id(entries) == frozen.tree
    changed = [
        (m, git_blob_id(b"other\n") if p == "d/b.txt" else o, p) for m, o, p in entries
    ]
    assert tree_id(changed) != frozen.tree


# -- anti-unification ---------------------------------------------------------


def test_tokenize_round_trips_and_respects_atoms():
    text = "defmodule Foo.Bar do\n  x = 1  # tail\n"
    assert render(tokenize(text)) == text
    atomized = tokenize(text, [(10, 17)])
    assert "Foo.Bar" in atomized.children[0].children
    with pytest.raises(IECRefusal):
        tokenize("ab\ncd\n", [(1, 4)])


def test_anti_unification_shares_identical_differences_and_reconstructs():
    members = [
        tokenize("defmodule Foo do\n  def foo, do: :foo\nend\n"),
        tokenize("defmodule Bar do\n  def bar, do: :bar\nend\n"),
    ]
    generalization = anti_unify(members)
    assert (
        template_text(generalization.template)
        == "defmodule {{X0}} do\n  def {{X1}}, do: :{{X1}}\nend\n"
    )
    for member, substitution in zip(members, generalization.substitutions):
        assert apply(generalization.template, substitution) == member
    assert (
        generalization.compression()["generalized_cost"]
        < generalization.compression()["original_cost"]
    )


def test_hedge_holes_cover_runs_of_different_length():
    members = [
        tokenize("| a | one |\n"),
        tokenize("| b | two words here |\n"),
        tokenize("| c | x |\n"),
    ]
    generalization = anti_unify(members)
    assert any(hole.hedge for hole in generalization.holes)
    assert [
        generalization.binding_text(i, h.index)
        for i in range(3)
        for h in generalization.holes
        if h.hedge
    ] == [
        "one",
        "two words here",
        "x",
    ]


# -- templates ----------------------------------------------------------------


def test_frontmatter_and_eex_chunks_follow_ggen_igniter_conventions():
    header, unsupported, body = split_frontmatter(
        '---\nto: "lib/out.ex"\nmode: file\nsparql:\n  q: |\n    SELECT\n---\n<%= name %> <%% x\n'
    )
    assert header == {"to": "lib/out.ex", "mode": "file"}
    assert unsupported == ["sparql"]
    chunks = eex_chunks(body)
    assert [(c.kind, c.text) for c in chunks] == [
        ("output", "name"),
        ("literal", " <% x\n"),
    ]


def test_containment_requires_only_unconditional_literals():
    body = "head\n<%= if show do %>maybe\n<% end %>tail\n"
    chunks = eex_chunks(body)
    assert chunk_depths(chunks) == [0, 0, 1, 0, 0]
    assert literal_containment(chunks, "head\ntail\n").holds
    assert literal_containment(chunks, "head\nmaybe\ntail\n").holds
    missing = literal_containment(chunks, "head\nTAIL\n")
    assert not missing.holds and missing.missing["anchored_end"]


def test_tera_whitespace_control_and_raw_blocks():
    chunks = tera_chunks(
        "a  {%- if x -%}\n  b  {%- endif %}\n{% raw %}{{ kept }}{% endraw %}"
    )
    literals = [c.text for c in chunks if c.kind == "literal"]
    assert literals == ["a", "b", "\n{{ kept }}"]
    assert (
        chunk_depths(chunks)[chunks.index(next(c for c in chunks if c.text == "b"))]
        == 1
    )


# -- court --------------------------------------------------------------------


def test_court_names_its_verifier_set_and_preserves_counterexamples(tmp_path):
    repo = make_repo(tmp_path / "r", {"a.txt": "alpha\n"})
    frozen = subject(repo)
    original = read_blob(frozen, repo, "a.txt")
    expected = census(frozen, repo).file("a.txt").object_id
    assert (
        git_blob_id(original) == expected == git(repo, "hash-object", "a.txt").strip()
    )
    court = VerifierSet("t/1", (BYTE_IDENTITY, BLOB_IDENTITY))
    passing = run_court(
        "s",
        original,
        original,
        court,
        original_identity=expected,
        generated_identity=git_blob_id(original),
        context={"expected_blob_id": expected},
    )
    assert passing.verdict is Verdict.PASS
    assert passing.claim.endswith(court.short_id)
    failing = run_court(
        "s",
        original,
        b"alphA\n",
        court,
        original_identity=expected,
        generated_identity=git_blob_id(b"alphA\n"),
        context={"expected_blob_id": expected},
    )
    assert (
        failing.verdict is Verdict.COUNTEREXAMPLE and failing.claim == "NOT_VALIDATED"
    )
    assert {c["verifier"] for c in failing.counterexamples()} == {
        "byte-identity",
        "git-blob-identity",
    }
    assert failing.counterexamples()[0]["evidence"]["offset"] == 4


def test_blocked_verifiers_stay_in_the_set_and_lower_the_claim():
    never = Verifier(
        "native", "1", "tests", lambda *_: VerifierResult(Verdict.PASS, "unreachable")
    )
    court = VerifierSet("t/2", (BYTE_IDENTITY, never))
    receipt = run_court(
        "s",
        b"x",
        b"x",
        court,
        original_identity="a",
        generated_identity="a",
        blocked={"native": "BLOCKED_EXECUTION_AUTHORITY: not brokered"},
    )
    assert receipt.dimensions == {"syntax": "PASS", "tests": "BLOCKED"}
    assert receipt.verdict is Verdict.BLOCKED and receipt.claim == "NOT_VALIDATED"
    with pytest.raises(IECRefusal):
        VerifierSet("empty/1", ())
