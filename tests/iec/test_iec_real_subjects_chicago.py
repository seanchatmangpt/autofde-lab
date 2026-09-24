"""IEC crowns against the real sibling repositories, at their pinned commits.

Chicago for its scope: the real ggen_igniter and ggen-create checkouts, the real
git object database, real rdflib, and ggen-create's own code imported from its
pinned checkout. Nothing is replaced by a double.

Checkouts are located by `IEC_GGEN_IGNITER_CHECKOUT` / `IEC_GGEN_CREATE_CHECKOUT`,
falling back to the ecosystem convention `~/ggen_igniter` / `~/ggen-create`. A
missing checkout, or one that lacks the pinned commit, is a named environment
gate (`UNSUPPORTED`), never a pass.

The replay tests re-run the committed crowns and require the committed receipts
back byte for byte: `receipts/v26.9.23/iec/` is evidence only while this holds.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from autofde_lab.iec.crowns.c3 import HELD_OUT_COMMIT, run_c3
from autofde_lab.iec.crowns.crown import run_c1

REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIPTS = REPO_ROOT / "receipts" / "v26.9.23" / "iec"
GGEN_IGNITER_COMMIT = "d84da1419a6945c6a8a64b8f6cdca9d0b2c9e0f3"
GGEN_CREATE_COMMIT = "eaa463af138d7aff88db813f0f65307bf5c9b5ba"


def _checkout(variable: str, fallback: str, commit: str) -> Path | None:
    path = Path(os.environ.get(variable, str(Path.home() / fallback))).expanduser()
    if not (path / ".git").exists():
        return None
    probe = subprocess.run(
        ["git", "-C", str(path), "cat-file", "-e", f"{commit}^{{commit}}"],
        capture_output=True,
    )
    return path if probe.returncode == 0 else None


GGEN_IGNITER = _checkout(
    "IEC_GGEN_IGNITER_CHECKOUT", "ggen_igniter", GGEN_IGNITER_COMMIT
)
GGEN_CREATE = _checkout("IEC_GGEN_CREATE_CHECKOUT", "ggen-create", GGEN_CREATE_COMMIT)
HAS_HELD_OUT = (
    subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "cat-file",
            "-e",
            f"{HELD_OUT_COMMIT}^{{commit}}",
        ],
        capture_output=True,
    ).returncode
    == 0
)

needs_ggen_igniter = pytest.mark.skipif(
    GGEN_IGNITER is None,
    reason=f"UNSUPPORTED: no ggen_igniter checkout containing {GGEN_IGNITER_COMMIT} "
    "(set IEC_GGEN_IGNITER_CHECKOUT)",
)
needs_ggen_create = pytest.mark.skipif(
    GGEN_CREATE is None,
    reason=f"UNSUPPORTED: no ggen-create checkout containing {GGEN_CREATE_COMMIT} "
    "(set IEC_GGEN_CREATE_CHECKOUT)",
)
needs_held_out = pytest.mark.skipif(
    not HAS_HELD_OUT,
    reason=f"UNSUPPORTED: this checkout lacks {HELD_OUT_COMMIT} (shallow clone)",
)


@pytest.fixture(scope="module")
def c1(tmp_path_factory):
    if GGEN_IGNITER is None or GGEN_CREATE is None:
        pytest.skip("UNSUPPORTED: pinned sibling checkouts not present")
    root = tmp_path_factory.mktemp("c1")
    receipt = run_c1(
        GGEN_IGNITER,
        root / "out",
        root / "regenerated",
        commit=GGEN_IGNITER_COMMIT,
        ggen_create=GGEN_CREATE,
        scratch=root / "ggen-create-scratch",
    )
    return root, receipt


def _verdicts(receipt: dict) -> dict[str, dict[str, str]]:
    return {
        subject["target"]: {
            name: court["verdict"] for name, court in subject["courts"].items()
        }
        for subject in receipt["subjects"]
    }


@needs_ggen_igniter
@needs_ggen_create
def test_c1_regenerates_every_committed_output_of_ggen_igniter(c1):
    root, receipt = c1
    assert receipt["subject"]["commit"] == GGEN_IGNITER_COMMIT
    assert receipt["declared_outputs"] == {"total": 15, "literal": 9, "committed": 4}
    assert receipt["tree_identity"] == "PASS"
    assert receipt["header_family"] == "PASS"
    verdicts = _verdicts(receipt)
    assert verdicts["docs/architecture/adr/README.md"]["iec-c1-static-row/1"] == "PASS"
    for target in (
        "lib/ggen_igniter/discovery/examples/incremental_dfg.ex",
        "lib/ggen_igniter/stream/examples/sensor_sink.ex",
    ):
        assert verdicts[target]["iec-c1-static-flat/1"] == "PASS"
    reactor = verdicts["lib/ggen_igniter/reactors/examples/expense_approval_reactor.ex"]
    # the raw-render hypothesis is falsified and stays falsified; the refined,
    # weaker court is a separate, separately named claim
    assert reactor["iec-c1-static-flat/1"] == "COUNTEREXAMPLE"
    assert reactor["iec-c1-static-modulo-formatter-flat/1"] == "PASS"
    assert all(v["ggen_igniter-native/1"] == "BLOCKED" for v in verdicts.values())
    assert len(receipt["validated_claims"]) == 4
    tree = json.loads((root / "out" / "tree-identity.json").read_text())
    assert tree["tree_with_regenerated_subjects"] == tree["frozen_tree"]
    assert tree["tree_without_regenerated_subjects"] != tree["frozen_tree"]


@needs_ggen_igniter
@needs_ggen_create
def test_c1_findings_on_ggen_igniter(c1):
    root, receipt = c1
    plan = json.loads((root / "out" / "promotion-plan.json").read_text())
    by_id = {candidate["id"]: candidate for candidate in plan["candidates"]}
    uncovered = [item["uncovered_matches"] for item in by_id["PROMO-C1-03"]["evidence"]]
    assert uncovered == [["0009-runtime-shape-semantic-ir.md"]]
    assert by_id["PROMO-C1-04"]["destination"] == "seanchatmangpt/ggen-create"
    hypotheses = [
        json.loads(line)
        for line in (root / "out" / "hypotheses.jsonl").read_text().splitlines()
    ]
    status = next(h for h in hypotheses if h["id"].endswith(":constant:status"))
    assert (
        status["standing"] == "UNKNOWN"
        and status["declared_by_template"] == "interpolated"
    )


@needs_ggen_igniter
@needs_ggen_create
def test_federation_reuses_ggen_create_and_keeps_its_refusals(c1):
    _root, receipt = c1
    federation = receipt["federation"]
    assert federation["producer"]["commit"] == GGEN_CREATE_COMMIT
    assert federation["role_classes_joined"] == 690
    assert federation["header_lines_routed"] == [
        "ggen-create",
        "ggen-create",
        "ggen-create",
        "iec-anti-unification",
    ]
    # render_concrete_many drops the text before each replacement at this commit;
    # the lifecycle probe shows it surfacing as a false TARGET_COLLISION_REFUSED
    assert federation["differential_probe"] == "COUNTEREXAMPLE"


@needs_ggen_igniter
@needs_ggen_create
def test_committed_c1_receipts_replay_byte_for_byte(c1):
    root, receipt = c1
    committed = json.loads((RECEIPTS / "c1" / "run-receipt.json").read_text())
    engine = json.loads(
        (RECEIPTS / "c1" / "kernels" / "adr-index-pack.json").read_text()
    )["engine"]
    import rdflib

    if engine["version"] != rdflib.__version__:
        pytest.skip(
            f"UNSUPPORTED: committed kernels were computed with rdflib {engine['version']}, "
            f"this environment has {rdflib.__version__}; a different engine is a different "
            "observation"
        )
    assert receipt["run_id"] == committed["run_id"]
    for path in (RECEIPTS / "c1").rglob("*"):
        if path.is_file():
            assert (
                path.read_bytes()
                == (root / "out" / path.relative_to(RECEIPTS / "c1")).read_bytes()
            ), path


@needs_held_out
@needs_ggen_igniter
def test_committed_c3_court_replays_and_retires_exactly_one_class(tmp_path):
    work = tmp_path / "c3"
    work.mkdir()
    for name in (
        "mechanized.autofde-lab.frozen.json",
        "llm-outcome.autofde-lab.json",
        "llm-outcome.ggen_igniter.calibration.json",
    ):
        shutil.copy(RECEIPTS / "c3" / name, work / name)
    receipt = run_c3(REPO_ROOT, work, ggen_igniter=GGEN_IGNITER)
    assert receipt["frozen_file_sha256"] == (
        "4372b88c42278572e4905efd33d45462b9ed4edeaac5957b1f6955f5136a2edd"
    )
    assert receipt["replayed_outcome_id"] == receipt["frozen_outcome_id"]
    assert receipt["held_out_verdict"] == "PASS"
    assert receipt["calibration_verdict"] == "UNSUPPORTED"
    assert receipt["ledger_status"] == {
        "RC-GENERATED-OUTPUT-AUDIT": "RETIRED_FROM_LLM",
        "RC-PRODUCER-POSTPROCESSING": "MECHANIZATION_CANDIDATE",
        "RC-INDEX-DRIFT": "KNOWN",
        "RC-FEDERATION-SURFACE": "KNOWN",
    }
    for name in (
        "court.held-out.autofde-lab.json",
        "court.calibration.ggen_igniter.json",
        "mechanized.ggen_igniter.json",
        "retirement-ledger.jsonl",
        "run-receipt.json",
    ):
        assert (work / name).read_bytes() == (RECEIPTS / "c3" / name).read_bytes(), name
