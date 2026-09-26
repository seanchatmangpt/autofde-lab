import json

from autofde_lab.semantic_parts.benchmark_cli import main


def _fixture(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "subject_id": "python:dijkstra",
                        "verified_equivalents": ["rust:dijkstra"],
                        "lexical_candidates": ["python:dijkstra-helper"],
                        "semantic_candidates": ["rust:dijkstra"],
                    },
                    {
                        "subject_id": "java:observer",
                        "verified_equivalents": ["elixir:observer"],
                        "lexical_candidates": ["java:observer-utils"],
                        "semantic_candidates": ["elixir:observer"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_cli_emits_replayable_receipt(tmp_path, capsys):
    input_path = _fixture(tmp_path)
    out = tmp_path / "receipt.json"

    assert main(["--input", str(input_path), "--k", "3", "--out", str(out)]) == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == "autofde.semantic-substitution-receipt.v1"
    assert payload["case_count"] == 2
    assert payload["authority"] == "NONE"
    assert payload["result"]["semantic"]["discovery_rate"] == 1.0
    assert len(payload["input_sha256"]) == 64
    assert len(payload["result_sha256"]) == 64

    stdout = json.loads(capsys.readouterr().out)
    assert stdout == payload


def test_cli_can_run_multiple_candidate_budgets(tmp_path, capsys):
    input_path = _fixture(tmp_path)

    assert main(["--input", str(input_path), "--cutoffs", "1,3,5"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"]["schema"] == "autofde.semantic-substitution-sweep.v1"
    assert payload["result"]["cutoffs"] == [1, 3, 5]


def test_cli_refuses_malformed_oracle_input(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            [
                {
                    "subject_id": "a",
                    "verified_equivalents": "b",
                    "lexical_candidates": [],
                    "semantic_candidates": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    assert main(["--input", str(path)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["standing"] == "REFUSED"
    assert payload["authority"] == "NONE"
    assert payload["code"] == "REFUSED_BENCHMARK_INPUT"
