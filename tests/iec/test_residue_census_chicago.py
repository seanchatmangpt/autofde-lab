"""IEC-011 LLM residue census, against real git repositories.

Chicago: a real `git` binary builds a throwaway repository with real commits, and the
census reads it through the real object database. The last test runs the census on
this checkout itself. Nothing is replaced by a double.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from autofde_lab.iec.crowns.corpus import observe_checkout
from autofde_lab.iec.crowns.model import canonical_json
from autofde_lab.iec.crowns.residue import (
    LDR_UNREPRESENTABLE,
    main,
    residue_census,
    residue_delta,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

PROGRAMS = '''\
import dspy as d
from dspy import ChainOfThought


class ClassifyTicket(d.Signature):
    """Which queue owns this ticket?"""

    ticket = d.InputField()
    queue = d.OutputField()


def route(ticket):
    # llm-residue: kind=classification class=RC-TICKET-ROUTING
    return d.Predict(ClassifyTicket)(ticket=ticket)


def summarize(text):
    return ChainOfThought("text -> summary")(text=text)


def again(ticket):
    return d.Predict(signature=ClassifyTicket)(ticket=ticket)


def invented(x):
    return d.ChainOfThought(ClassifyTicket)(x)  # llm-residue: kind=vibes
'''

LOCAL_PREDICT = """\
class Predict:
    def __call__(self, x):
        return x


print(Predict()(1))
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, body in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "residue@example.invalid")
    _git(repo, "config", "user.name", "residue fixture")
    _git(repo, "remote", "add", "origin", "https://github.com/example/residue-fixture")
    return repo


def _subject(repo: Path, commit: str = "HEAD"):
    return observe_checkout(
        repo,
        repository="example/residue-fixture",
        branch="main",
        visibility="public",
        inclusion_reason="residue census test",
        commit=commit,
    )


def _base_files() -> dict[str, str]:
    return {
        "src/pkg/programs.py": PROGRAMS,
        "src/pkg/only_imports.py": "import openai\n\nMODEL = 'x'\n",
        "src/pkg/local.py": LOCAL_PREDICT,
        "tests/test_client.py": "import anthropic\n\nclient = anthropic.Anthropic()\n",
        "scripts/broken.py": "def (:\n",
    }


def test_census_counts_resolved_invocations_and_nothing_else(
    fixture_repo: Path,
) -> None:
    _commit(fixture_repo, _base_files(), "base")
    census = residue_census(_subject(fixture_repo), fixture_repo)

    edges = {(e["path"], e["line"]): e for e in census["edges"]}
    assert census["llm_residue"] == 5 == len(edges)
    assert census["llm_residue_by_zone"] == {"package": 4, "test": 1}
    assert census["llm_residue_by_api"] == {
        "anthropic.Anthropic": 1,
        "dspy.ChainOfThought": 2,
        "dspy.Predict": 2,
    }

    declared = edges[("src/pkg/programs.py", 14)]
    assert declared["kind"] == "classification"
    assert declared["retirement_mechanism"] == "ontology + SPARQL/Datalog"
    assert declared["reasoning_class"] == "RC-TICKET-ROUTING"
    assert declared["signature"] == "ClassifyTicket"

    literal = edges[("src/pkg/programs.py", 18)]
    assert literal["signature"] == "'text -> summary'"
    assert literal["kind"] == "UNKNOWN" and literal["reasoning_class"] == "UNKNOWN"
    assert edges[("src/pkg/programs.py", 22)]["signature"] == "ClassifyTicket"

    # An undeclared kind is rejected, not coerced into the nearest real one.
    assert edges[("src/pkg/programs.py", 26)]["kind"] == "UNKNOWN"
    assert census["rejected_declarations"] == [
        {"path": "src/pkg/programs.py", "line": 26, "declared_kind": "vibes"}
    ]

    # A local class named Predict is not dspy; an import is not an invocation;
    # a provider call outside the rule table is counted, not dropped.
    assert not any(e["path"] == "src/pkg/local.py" for e in census["edges"])
    assert census["import_only"] == ["src/pkg/only_imports.py"]
    assert census["other_provider_calls"] == {
        "src/pkg/programs.py": {"dspy.InputField": 1, "dspy.OutputField": 1}
    }
    assert set(census["unparseable"]) == {"scripts/broken.py"}

    assert census["declared_reasoning_classes"] == [
        {
            "path": "src/pkg/programs.py",
            "blob": census["edges"][0]["blob"],
            "line": 5,
            "name": "ClassifyTicket",
            "question": "Which queue owns this ticket?",
        }
    ]
    [frontier] = census["frontier"]
    assert frontier["signature"] == "ClassifyTicket"
    assert frontier["call_sites"] == 3
    assert frontier["standing"] == "INFERRED_CANDIDATE"
    assert frontier["llm_cost"] == "UNKNOWN"
    assert census["llm_dependency_ratio"] == LDR_UNREPRESENTABLE


def test_census_reads_the_commit_not_the_working_tree(fixture_repo: Path) -> None:
    _commit(fixture_repo, _base_files(), "base")
    subject = _subject(fixture_repo)
    first = residue_census(subject, fixture_repo)
    (fixture_repo / "src/pkg/more.py").write_text(
        "import dspy\nP = dspy.Predict('a -> b')\n", encoding="utf-8"
    )
    second = residue_census(subject, fixture_repo)
    assert canonical_json(first) == canonical_json(second)
    assert second["llm_residue"] == 5


def test_delta_ignores_line_moves_and_does_not_call_removal_retirement(
    fixture_repo: Path,
) -> None:
    before_commit = _commit(fixture_repo, _base_files(), "base")
    shifted = "# a new comment moves every line down\n" + PROGRAMS.replace(
        'def summarize(text):\n    return ChainOfThought("text -> summary")(text=text)\n',
        "def summarize(text):\n    return text[:80]\n",
    )
    after_commit = _commit(fixture_repo, {"src/pkg/programs.py": shifted}, "retire one")

    before = residue_census(_subject(fixture_repo, before_commit), fixture_repo)
    after = residue_census(_subject(fixture_repo, after_commit), fixture_repo)
    delta = residue_delta(before, after)

    assert delta["direction"] == "DECREASED"
    assert (delta["llm_residue_before"], delta["llm_residue_after"]) == (5, 4)
    assert delta["removed"] == [
        {
            "path": "src/pkg/programs.py",
            "api": "dspy.ChainOfThought",
            "signature": "'text -> summary'",
            "count": 1,
        }
    ]
    assert delta["added"] == []
    assert delta["retired"].startswith("UNKNOWN:")

    grown = residue_delta(after, before)
    assert grown["direction"] == "INCREASED"
    assert grown["added"] == delta["removed"]


def test_cli_replays_byte_for_byte(fixture_repo: Path, tmp_path: Path) -> None:
    base = _commit(fixture_repo, _base_files(), "base")
    _commit(fixture_repo, {"src/pkg/only_imports.py": "import openai\n"}, "edit")
    outputs = []
    for run in ("a", "b"):
        out = tmp_path / run
        assert (
            main(
                [
                    str(out),
                    "--checkout",
                    str(fixture_repo),
                    "--repository",
                    "example/residue-fixture",
                    "--base",
                    base,
                ]
            )
            == 0
        )
        outputs.append({p.name: p.read_bytes() for p in sorted(out.iterdir())})
    assert outputs[0] == outputs[1]
    assert set(outputs[0]) == {
        "residue-census.json",
        "residue-census.base.json",
        "residue-delta.json",
    }
    delta = json.loads(outputs[0]["residue-delta.json"])
    assert delta["direction"] == "UNCHANGED"
    assert str(tmp_path) not in outputs[0]["residue-census.json"].decode()


def _this_checkout_is_autofde_lab() -> bool:
    probe = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0 and "autofde-lab" in probe.stdout


@pytest.mark.skipif(
    not _this_checkout_is_autofde_lab(),
    reason="UNSUPPORTED: not a git checkout whose origin is seanchatmangpt/autofde-lab",
)
def test_census_of_this_repository() -> None:
    subject = observe_checkout(
        REPO_ROOT,
        repository="seanchatmangpt/autofde-lab",
        branch="",
        visibility="public",
        inclusion_reason="residue census test",
    )
    census = residue_census(subject, REPO_ROOT)
    assert census["llm_residue"] > 0
    assert census["llm_dependency_ratio"] == LDR_UNREPRESENTABLE
    assert all(
        edge["api"].startswith(
            ("dspy.", "anthropic.", "openai.", "litellm.", "ollama.")
        )
        for edge in census["edges"]
    )
    assert canonical_json(census) == canonical_json(residue_census(subject, REPO_ROOT))
