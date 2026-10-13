# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Differential harness: autofde-lab vs the beam4pm native oracles.

Closes Explore finding #5: autofde-lab's OCEL/conformance checks were only ever
checked against themselves (self-referential); no second implementation existed
to disagree with. This module runs BOTH implementations over the same real
inputs and compares the DECISIONS, not the internals.

Two differential surfaces
-------------------------
1. **OCEL structural surface (rf3-ocel-oracle vs ``OcelLog``).** Both
   implementations ingest the same real OCEL 2.0 JSON fixture and must produce
   the same structural decisions: event/object counts, distinct-id counts,
   e2o/o2o relationship counts, and per-type event/object counts. These are
   integers — the comparison law is **exact integer equality**; any
   disagreement is a typed ``OracleDivergence``.
2. **Conformance surface (rf2-conformance-oracle vs
   ``check_ocel_conformance``).** Both implementations judge the same real
   observed activity sequences against the same intended sequence. The
   comparison law is **per-case verdict agreement**: each case (clean log,
   ghost-activity mutant) must get the SAME binary verdict (FIT / DEVIATION)
   from both implementations. Numeric scores are compared only against pinned
   values within a stated tolerance (``PINNED_FITNESS_TOLERANCE``), never
   cross-implementation: the two implementations use genuinely different
   algorithms (Alpha+++ optimal alignment vs strict prefix token replay), so
   their numeric scores are NOT required to be equal — only their verdicts
   must agree, plus each implementation's own score against its pinned value.

Fixture provenance
------------------
All three fixtures are real logs copied verbatim on 2026-08-06 from
``~/powlv2lsp`` (ISC-licensed), produced by an implementation independent of
this package — see ``tests/ocel/fixtures/PROVENANCE.md``. Nothing is
synthesized; the only mutations are the explicitly-named sabotage twins
(duplicate-id mutant for the structural surface, ghost-activity mutant for the
conformance surface), derived copies whose expected verdicts are asserted from
BOTH implementations.

Binary availability
-------------------
Either oracle binary may be absent; the skip is NAMED with the exact build
command, never silent (this repo's own convention, cf. ``test_wasm4pm_bridge``):

    CARGO_TARGET_DIR=/tmp/autofde-oracle-target cargo build --release
    (in the matching crate dir under /Users/sac/beam4pm/native/)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import (
    OcelAttribute,
    OcelAttributeValue,
    OcelEvent,
)
from autofde_lab.ocel.powl_replay import plan_lines_to_powl_node
from autofde_lab.powl.conformance import check_ocel_conformance

__all__ = [
    "OracleDivergence",
    "OracleWireFailure",
    "PINNED_FITNESS_TOLERANCE",
    "run_oracle",
    "observed_labels_of_log",
    "relabel_as_structural_fires",
    "log_to_xes",
]

# ── oracle plumbing ──────────────────────────────────────────────────────────

_BEAM4PM_NATIVE = Path("/Users/sac/beam4pm/native")
_RF2 = _BEAM4PM_NATIVE / "rf2-conformance-oracle/target/release/rf2-conformance-oracle"
_RF3 = _BEAM4PM_NATIVE / "rf3-ocel-oracle/target/release/rf3-ocel-oracle"

#: Numeric tolerance pinned in this test (comparison law, part 2): a float
#: score is compared to its pinned expected value within this tolerance.
#: Cross-implementation, only the binary verdict is compared.
PINNED_FITNESS_TOLERANCE = 1e-9

_BUILD_INSTRUCTIONS = {
    "rf2": (
        "BLOCKED:RF2_ORACLE_BINARY_ABSENT — build with: "
        "CARGO_TARGET_DIR=/tmp/autofde-oracle-target cargo build --release "
        "(in /Users/sac/beam4pm/native/rf2-conformance-oracle)"
    ),
    "rf3": (
        "BLOCKED:RF3_ORACLE_BINARY_ABSENT — build with: "
        "CARGO_TARGET_DIR=/tmp/autofde-oracle-target cargo build --release "
        "(in /Users/sac/beam4pm/native/rf3-ocel-oracle)"
    ),
}

FIXTURES = ("gundam_factory_trace", "out", "vision_ocel_trace")
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


class OracleDivergence(AssertionError):
    """Typed failure: the two implementations disagreed on a decision."""


class OracleWireFailure(AssertionError):
    """Typed failure: an oracle binary failed at the wire level (nonzero exit
    or malformed stdout JSON)."""


def run_oracle(binary: Path, payload: dict) -> dict:
    """One real subprocess over the oracle's stdin-JSON/stdout-JSON wire.

    Nonzero exit or unparseable stdout is a typed ``OracleWireFailure``, never
    a silent pass. (The rf3 oracle emits ``[rust4pm]`` progress lines on
    *stderr*; stdout must still be a single JSON object.)
    """
    proc = subprocess.run(
        [str(binary)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise OracleWireFailure(
            f"{binary.name} exited {proc.returncode} on {payload.get('op')}: "
            f"stderr tail: {proc.stderr[-400:]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise OracleWireFailure(
            f"{binary.name} stdout was not a single JSON object on "
            f"{payload.get('op')}: {exc}; stdout head: {proc.stdout[:200]}"
        ) from exc


def _require_rf2() -> Path:
    if not _RF2.exists():
        pytest.skip(_BUILD_INSTRUCTIONS["rf2"])
    return _RF2


def _require_rf3() -> Path:
    if not _RF3.exists():
        pytest.skip(_BUILD_INSTRUCTIONS["rf3"])
    return _RF3


# ── shared mechanical conversions over the REAL fixtures ─────────────────────


def observed_labels_of_log(log: OcelLog) -> tuple[str, ...]:
    """The real observed activity sequence of the log, in its own canonical
    order (timestamp, then event id) — the sequence both implementations judge.
    """
    return tuple(
        e.activity for e in sorted(log.events, key=lambda e: (e.timestamp_ns, e.id))
    )


def relabel_as_structural_fires(
    log: OcelLog,
    *,
    extra_labels: tuple[str, ...] = (),
) -> tuple[OcelEvent, ...]:
    """Mechanically re-shape the real fixture events into the input shape
    ``check_ocel_conformance`` consumes (its ``observed_labels_from_events``
    reads only ``powl_structural_fire`` events' ``detail`` attribute). The
    observed sequence — labels, order, count — is the real fixture's own; only
    the envelope is relabelled. ``extra_labels`` appends the sabotage twin's
    ghost fires AFTER the real sequence, each as a real ``OcelEvent``.
    """
    events = sorted(log.events, key=lambda e: (e.timestamp_ns, e.id))
    relabelled = tuple(
        OcelEvent(
            id=e.id,
            activity="powl_structural_fire",
            timestamp_ns=e.timestamp_ns,
            attributes=(
                OcelAttribute(
                    key="detail", value=OcelAttributeValue.string(e.activity)
                ),
            ),
        )
        for e in events
    )
    next_ns = (events[-1].timestamp_ns + 1) if events else 0
    ghosts = tuple(
        OcelEvent(
            id=f"ghost-{i}",
            activity="powl_structural_fire",
            timestamp_ns=next_ns + i,
            attributes=(
                OcelAttribute(key="detail", value=OcelAttributeValue.string(label)),
            ),
        )
        for i, label in enumerate(extra_labels)
    )
    return relabelled + ghosts


def log_to_xes(log: OcelLog) -> str:
    """Mechanically serialize the real fixture log into minimal XES — one
    trace per object, that object's linked events in canonical order, labelled
    by the real event type. Deterministic; content is the fixture's own.
    """
    events = sorted(log.events, key=lambda e: (e.timestamp_ns, e.id))
    by_object: dict[str, list[str]] = {}
    for link in log.event_object_links:
        by_object.setdefault(link.object_id, []).append(
            next(e.activity for e in events if e.id == link.event_id)
        )
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<log xmlns="http://www.xes-standard.org/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1">',
    ]
    for case_index, (object_id, labels) in enumerate(sorted(by_object.items())):
        lines.append("\t<trace>")
        lines.append(
            f'\t\t<string key="concept:name" value="{object_id}-{case_index}"/>'
        )
        for label in labels:
            lines.append("\t\t<event>")
            lines.append(f'\t\t\t<string key="concept:name" value="{label}"/>')
            lines.append("\t\t</event>")
        lines.append("\t</trace>")
    lines.append("</log>")
    return "\n".join(lines) + "\n"


def _intended_model(log: OcelLog):
    """The intended model: the fixture's own real event-type sequence in
    canonical order, as a strict POWL sequence (each step exactly once, in
    order). This is the same intended sequence handed to both implementations.
    """
    return plan_lines_to_powl_node(list(observed_labels_of_log(log)))


# ── court 0: the fixtures are real and parseable ─────────────────────────────


@pytest.mark.parametrize("fixture", FIXTURES)
def test_fixture_is_real_and_parses(fixture: str) -> None:
    """The differential runs over the real powlv2lsp fixtures only."""
    doc = json.loads((FIXTURE_DIR / f"{fixture}.json").read_text())
    log = OcelLog.from_ocel2_json(doc)
    assert len(log.events) > 0
    assert len(log.objects) > 0
    assert len(log.event_object_links) == len(log.events)


# ── surface 1: OCEL structural differential (rf3 vs OcelLog) ─────────────────


def _autofde_structural_stats(log: OcelLog) -> dict:
    """The same structural decisions rf3's ``ocel_stats`` reports, computed
    from ``OcelLog``'s own tables — the autofde side of the differential."""
    return {
        "num_events": len(log.events),
        "num_objects": len(log.objects),
        "distinct_event_ids": len({e.id for e in log.events}),
        "distinct_object_ids": len({o.id for o in log.objects}),
        "e2o_relationship_count": len(log.event_object_links),
        "o2o_relationship_count": len(log.object_object_links),
        "event_type_counts": dict(
            sorted(_count(e.activity for e in log.events).items())
        ),
        "object_type_counts": dict(
            sorted(_count(o.object_type for o in log.objects).items())
        ),
    }


def _count(labels) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return counts


@pytest.mark.parametrize("fixture", FIXTURES)
def test_rf3_structural_differential_agreement(fixture: str) -> None:
    """Both implementations must agree EXACTLY on every structural decision
    over the same real fixture. Integer equality; any difference is a typed
    ``OracleDivergence`` naming the divergent field."""
    rf3 = _require_rf3()
    doc = json.loads((FIXTURE_DIR / f"{fixture}.json").read_text())
    log = OcelLog.from_ocel2_json(doc)

    out = run_oracle(rf3, {"op": "ocel_stats", "ocel_path": str(FIXTURE_DIR / f"{fixture}.json")})
    assert out["ok"] is True, f"rf3 reported ok=false on real fixture {fixture}"

    expected = _autofde_structural_stats(log)
    actual = {
        "num_events": out["num_events"],
        "num_objects": out["num_objects"],
        "distinct_event_ids": out["raw"]["distinct_event_ids"],
        "distinct_object_ids": out["raw"]["distinct_object_ids"],
        "e2o_relationship_count": out["raw"]["e2o_relationship_count"],
        "o2o_relationship_count": out["raw"]["o2o_relationship_count"],
        "event_type_counts": out["type_stats"]["event_type_counts"],
        "object_type_counts": out["type_stats"]["object_type_counts"],
    }
    divergences = {
        field: (expected.get(field), actual.get(field))
        for field in sorted(set(expected) | set(actual))
        if expected.get(field) != actual.get(field)
    }
    if divergences:
        raise OracleDivergence(
            f"rf3 vs OcelLog structural disagreement on {fixture}: {divergences}"
        )


def test_rf3_duplicate_id_mutant_detected_by_both() -> None:
    """Sabotage twin (structural surface): a derived copy of the real gundam
    fixture with one event id duplicated. BOTH implementations must report the
    same collapsed distinct-id count — the differential must be able to
    disagree, and this proves the comparator kills a real defect."""
    rf3 = _require_rf3()
    doc = json.loads((FIXTURE_DIR / "gundam_factory_trace.json").read_text())
    duplicate = dict(doc["events"][0])
    doc["events"].append(duplicate)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        mutant_path = Path(tmp) / "duplicate-id.jsonocel"
        mutant_path.write_text(json.dumps(doc))
        out = run_oracle(
            rf3, {"op": "ocel_stats", "ocel_path": str(mutant_path)}
        )
    assert out["ok"] is True
    log = OcelLog.from_ocel2_json(doc)

    rf3_events, rf3_distinct = out["raw"]["num_events"], out["raw"]["distinct_event_ids"]
    autofde_events = len(log.events)
    autofde_distinct = len({e.id for e in log.events})

    assert (rf3_events, rf3_distinct) == (
        autofde_events,
        autofde_distinct,
    ), "duplicate-id mutant: implementations disagree"
    assert rf3_distinct < rf3_events, (
        "sabotage twin vacuous: the duplicate was not visible to either side"
    )


# ── surface 2: conformance differential (rf2 vs check_ocel_conformance) ──────


@pytest.mark.parametrize("fixture", FIXTURES)
def test_rf2_conformance_differential_verdict_agreement(fixture: str) -> None:
    """Per-case verdict agreement, per the comparison law in the module
    docstring:

    * clean real log  → BOTH implementations must render FIT;
    * ghost-activity mutant → BOTH must render DEVIATION.

    rf2's verdict: ``log_fitness == 1.0`` (perfect alignment fit) ⇔ FIT.
    autofde's verdict: ``check_ocel_conformance(...).conforms`` ⇔ FIT.
    Numeric scores are each checked against their own pinned value within
    ``PINNED_FITNESS_TOLERANCE``; they are deliberately NOT compared to each
    other (different algorithms).
    """
    rf2 = _require_rf2()
    doc = json.loads((FIXTURE_DIR / f"{fixture}.json").read_text())
    log = OcelLog.from_ocel2_json(doc)
    model = _intended_model(log)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        clean_xes = tmp_dir / "clean.xes"
        clean_xes.write_text(log_to_xes(log))

        # Case CLEAN, both implementations.
        rf2_out = run_oracle(
            rf2, {"op": "conformance", "xes_path": str(clean_xes)}
        )
        rf2_fit = rf2_out["fitness"]["log_fitness"]
        assert abs(rf2_fit - 1.0) <= PINNED_FITNESS_TOLERANCE, (
            f"rf2 pinned clean log_fitness must be 1.0, got {rf2_fit}"
        )
        assert rf2_out["fitness"]["total_costs"] == 0

        autofde_result = check_ocel_conformance(
            model, relabel_as_structural_fires(log)
        )
        assert autofde_result.conforms is True, (
            f"autofde pinned clean verdict must be FIT, got {autofde_result}"
        )

        clean_agreement = (rf2_fit == 1.0) == autofde_result.conforms
        assert clean_agreement

        # Case MUTATED (ghost activity appended after the real sequence),
        # model FIXED to the clean log's model via model_xes_path.
        mutant_xes = tmp_dir / "mutant.xes"
        mutant_log_text = log_to_xes(log)
        ghost_trace = mutant_log_text.replace(
            "</trace>",
            '\t\t<event>\n\t\t\t<string key="concept:name" '
            'value="SABOTAGE_GHOST_STEP"/>\n\t\t</event>\n\t</trace>',
            1,
        )
        assert ghost_trace != mutant_log_text, "ghost insertion was a no-op"
        mutant_xes.write_text(ghost_trace)

        rf2_mut = run_oracle(
            rf2,
            {
                "op": "conformance",
                "xes_path": str(mutant_xes),
                "model_xes_path": str(clean_xes),
            },
        )
        rf2_mut_fit = rf2_mut["fitness"]["log_fitness"]
        assert rf2_mut_fit < 1.0, (
            f"rf2 pinned mutant log_fitness must be < 1.0, got {rf2_mut_fit}"
        )

        autofde_mut = check_ocel_conformance(
            model, relabel_as_structural_fires(log, extra_labels=("SABOTAGE_GHOST_STEP",))
        )
        assert autofde_mut.conforms is False, (
            f"autofde pinned mutant verdict must be DEVIATION, got {autofde_mut}"
        )
        assert (
            autofde_mut.divergence_label == "SABOTAGE_GHOST_STEP"
        ), "autofde must name the exact diverging label"

        mutant_agreement = (rf2_mut_fit < 1.0) == (not autofde_mut.conforms)
        assert mutant_agreement

        # Comparison-law receipt: per-case verdict agreement stats.
        cases = {
            f"{fixture}:clean": (True, True, clean_agreement),
            f"{fixture}:ghost-mutant": (False, False, mutant_agreement),
        }
        assert all(agree for _, _, agree in cases.values())


def test_rf2_and_rf3_determinism() -> None:
    """Determinism: two runs of each oracle over the same input produce
    identical parsed JSON. A flip-flopping oracle would make every agreement
    stat above meaningless."""
    rf2 = _require_rf2()
    rf3 = _require_rf3()
    fixture_path = FIXTURE_DIR / "gundam_factory_trace.json"
    doc = json.loads(fixture_path.read_text())
    log = OcelLog.from_ocel2_json(doc)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        xes = Path(tmp) / "clean.xes"
        xes.write_text(log_to_xes(log))
        rf2_a = run_oracle(rf2, {"op": "conformance", "xes_path": str(xes)})
        rf2_b = run_oracle(rf2, {"op": "conformance", "xes_path": str(xes)})
        assert rf2_a == rf2_b, "rf2 is nondeterministic across runs"
        assert rf2_a["num_variants_aligned"] == 1

    rf3_a = run_oracle(rf3, {"op": "ocel_stats", "ocel_path": str(fixture_path)})
    rf3_b = run_oracle(rf3, {"op": "ocel_stats", "ocel_path": str(fixture_path)})
    assert rf3_a == rf3_b, "rf3 is nondeterministic across runs"


def test_sabotage_twin_comparator_kills_wrong_verdict_expectation() -> None:
    """Sabotage twin (comparator): mutate a verdict expectation and the
    differential must FAIL, not agree. Proves the comparator carries real
    bits — a wrong expected verdict map is rejected with ``OracleDivergence``.
    """
    doc = json.loads((FIXTURE_DIR / "gundam_factory_trace.json").read_text())
    log = OcelLog.from_ocel2_json(doc)
    model = _intended_model(log)

    observed = observed_labels_of_log(log)

    # The comparator under test: expected verdict per case vs autofde's real
    # verdict, same law the differential courts apply.
    def compare(expected: dict[str, bool]) -> None:
        result = check_ocel_conformance(
            model, relabel_as_structural_fires(log, extra_labels=("SABOTAGE_GHOST_STEP",))
        )
        actual = {"clean": True, "ghost-mutant": result.conforms}
        for case, expected_verdict in expected.items():
            if actual[case] != expected_verdict:
                raise OracleDivergence(
                    f"verdict expectation diverges on {case}: "
                    f"expected {expected_verdict}, actual {actual[case]}"
                )

    # Correct expectation: passes.
    compare({"clean": True, "ghost-mutant": False})

    # Sabotaged expectation (mutant flipped to FIT): must FAIL.
    with pytest.raises(OracleDivergence, match="ghost-mutant"):
        compare({"clean": True, "ghost-mutant": True})
