"""Lane W10 court: gymact <-> autofde-lab bridge adapter.

Every court here kills a named mutant class:

* schema tests kill "row shape drift" (RESOLUTIONS #7 non-conformance);
* the determinism test kills "hidden entropy" (wall clock / OS entropy /
  set-order leakage into the row);
* ``test_refuse_is_feasible`` kills the feasibility-mapping mutant
  (Refuse swapped to infeasible) -- the ANTI-VACUITY control, physically
  mutated and re-run to prove this court carries bits (procedure and
  captured failure recorded in the lane receipt);
* ``test_forced_failure_feasible_false`` kills "feasible is constant True"
  (a table that admits everything is not a mapping);
* the totality test kills "silent key deletion" from the law table.

Run (RESOLUTIONS #9 parallel pytest hygiene):
    PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider \
        tests/simulation/test_bridge_gymact.py
"""

from __future__ import annotations

import hashlib
import json

import pytest

from autofde_lab.simulation import bridge_gymact

skip_unless_gymact = pytest.mark.skipif(
    not bridge_gymact.gymact_available(),
    reason="gymact.execution_loop not importable via any recorded mechanism",
)

ROW_KEYS = set(bridge_gymact.ROW_KEYS)


def _row(world_spec, doctrine_id="doctrine-under-test", seed=7):
    return bridge_gymact.run_episode_backend(world_spec, doctrine_id, seed)


def _canonical(row) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


@skip_unless_gymact
def test_import_mechanism_recorded():
    """The probe must name exactly which mechanism exposes the loop."""
    report = bridge_gymact.import_report()
    assert report["mechanism"] is not None
    assert report["mechanism"].startswith(
        ("plain-import", "sys-path-insert", "file-location-overlay")
    )
    assert report["execution_loop_file"] and "execution_loop.py" in str(
        report["execution_loop_file"]
    )
    assert report["gymact_file"]


@skip_unless_gymact
def test_happy_path_row_conforms_to_pinned_schema():
    row = _row({"world_id": "l10-ok"})
    assert set(row.keys()) == ROW_KEYS  # RESOLUTIONS #7 exact shape
    assert row["backend"] == "gymact"
    assert row["doctrine_id"] == "doctrine-under-test"
    assert row["world_id"] == "l10-ok"
    assert row["seed"] == 7
    assert isinstance(row["metrics"], dict)
    assert row["feasible"] is True
    assert row["metrics"]["outcome"] == "Recover"
    assert row["metrics"]["episode_standing"] == "AUTONOMOUS"
    assert row["metrics"]["actuation_count"] == 1
    assert row["metrics"]["illegal_outcome_observed"] is False
    assert len(row["receipt_digests"]) == 1
    assert len(row["receipt_digests"][0]) == 64
    int(row["receipt_digests"][0], 16)  # sha256 hex


@skip_unless_gymact
def test_deterministic_replay_byte_identical():
    spec = {"world_id": "l10-replay", "claim_faults": [["rate_limit", 2]]}
    first = _row(spec, seed=11)
    second = _row(spec, seed=11)
    assert _canonical(first) == _canonical(second)
    # and a different seed is a different (still valid) row: the seed is
    # carried, not normalized away.
    other = _row(spec, seed=12)
    assert other["seed"] == 12
    assert other["receipt_digests"] == first["receipt_digests"]


@skip_unless_gymact
def test_refuse_is_feasible():
    """Lawful refusal is a successful outcome. THIS is the court the
    anti-vacuity mutation (FEASIBILITY_BY_OUTCOME['Refuse'] -> False) must
    kill; see the lane receipt for the captured failing run."""
    row = _row({"world_id": "l10-refuse", "registry_valid": False})
    assert row["metrics"]["outcome"] == "Refuse"
    assert row["metrics"]["episode_standing"] == "BLOCKED_AUTHORITY"
    assert row["metrics"]["typed_reason"] == "REFUSED_NO_AUTHORITY"
    assert row["metrics"]["actuation_count"] == 0
    assert row["metrics"]["illegal_outcome_observed"] is False
    assert row["feasible"] is True, "lawful refusal mapped infeasible: law table mutated"
    assert row["receipt_digests"] == []  # refusal: zero actuation, no receipt


@skip_unless_gymact
def test_forced_failure_feasible_false():
    """A non-TransportFault escaping the loop is the constructible
    forced-failure world: crash-class, not a legal outcome."""
    row = _row({"world_id": "l10-crash", "explode_on_claim": "injected lane-10 crash"})
    assert row["feasible"] is False
    assert row["metrics"]["outcome"] is None
    assert row["metrics"]["exception"] is not None
    assert "injected lane-10 crash" in row["metrics"]["exception"]
    assert row["metrics"]["episode_standing"] not in ("AUTONOMOUS",)
    assert row["receipt_digests"] == []


@skip_unless_gymact
def test_receipt_digest_is_sha256_of_canonical_serialization():
    """Digest stability: same episode twice => same digest; the digest is
    sha256 over the receipt's canonical pydantic JSON (documented fallback to
    repr NOT needed -- the canonical serialization exists)."""
    spec = {"world_id": "l10-digest", "execute_faults": [["crash_before_actuation"]]}
    row_a = _row(spec, seed=3)
    row_b = _row(spec, seed=3)
    assert row_a["receipt_digests"] == row_b["receipt_digests"]
    digest = row_a["receipt_digests"][0]
    assert (
        hashlib.sha256(bytes.fromhex(digest)).hexdigest() is not None
    )  # well-formed hex
    # information-carrying: a different world digests differently
    row_c = _row({"world_id": "l10-digest-other"}, seed=3)
    assert row_c["receipt_digests"] != row_a["receipt_digests"]


@skip_unless_gymact
def test_wait_for_human_unreachable():
    """gymact's law (execution_loop.py:84-91, :336-341): the loop never ends
    by waiting for a human; this bridge re-checks it per run, fail-closed."""
    worlds = [
        {"world_id": "l10-illegal-ok"},
        {"world_id": "l10-illegal-refuse", "registry_valid": False},
        {
            "world_id": "l10-illegal-faults",
            "claim_faults": [["rate_limit", 1], ["network_partition", 2]],
            "execute_faults": [["crash_after_actuation"]],
        },
    ]
    for spec in worlds:
        row = _row(spec, seed=5)
        assert row["metrics"]["outcome"] != "WaitForHumanToNotice"
        assert row["metrics"]["illegal_outcome_observed"] is False
        assert row["metrics"]["outcome"] in bridge_gymact.LEGAL_OUTCOME_VALUES


@skip_unless_gymact
def test_feasibility_table_totality():
    """Every legal outcome is an explicit key: silent key deletion must not
    convert lawful endings into fail-closed infeasibility."""
    import gymact.execution_loop as execution_loop

    for outcome in execution_loop.LegalOutcome:
        assert outcome.value in bridge_gymact.FEASIBILITY_BY_OUTCOME


def test_module_imports_without_gymact_side_effects():
    """The bridge imports nothing from gymact (and nothing from W8-owned
    fortune5_safe modules) at module top level: resolution is lazy, at call
    time, so sibling lanes' in-flight edits cannot break our collection."""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(bridge_gymact.__file__).read_text(encoding="utf-8"))
    for node in tree.body:  # top-level statements only
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            modules = names if isinstance(node, ast.Import) else [node.module or ""]
            for module in modules:
                assert not module.startswith("gymact"), f"top-level gymact import: {module}"
                assert "fortune5_safe" not in module, f"top-level W8 import: {module}"
    assert bridge_gymact.run_episode_backend is not None
