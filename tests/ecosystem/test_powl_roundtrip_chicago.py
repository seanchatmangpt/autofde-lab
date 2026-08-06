# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for the POWL2 projector and its strict decoder.

The defect these tests exist to prevent recurring: ``project_plan_to_powl``
emitted Turtle that was **SHACL-invalid** against mfw's own committed shapes at
``~/mfw/mfw-planner/shapes/powl2.shacl.ttl``. ``powl2:ActivityLeafShape``
requires ``mfwp:implementsAction`` with ``minCount 1 / maxCount 1``; the
projector never emitted it, while the Rust reference emitter
(``~/mfw/mfw-planner/src/projection/powl_rdf.rs``) and the real committed
artifact ``~/mfw/runs/ticket-10/plan.powl.ttl`` both do. Nothing in the test
suite noticed, because every assertion checked for the presence of terms we
emitted rather than the presence of terms the shapes require.

Discipline, following ``tests/ecosystem/test_chatman_chain_chicago.py``: where
an mfw artifact is genuinely absent the test SKIPS with the blocker named
(``BLOCKED:<TOKEN>: ...``) and never substitutes a fixture in its place. A
green run against a fixture standing in for the real artifact would assert
nothing about the real artifact.

Scope reminder: this file exercises a projector. Projection is not execution,
and nothing here is admitted, receipted, or authorised to actuate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skdecide.fabric.powl import (
    MFWP,
    POWL2,
    PROV,
    PowlDecodeError,
    parse_powl_turtle,
    project_plan_to_powl,
    validate_powl,
)

HOME = Path.home()
MFW = HOME / "mfw"
MFW_TICKET10_POWL = MFW / "runs" / "ticket-10" / "plan.powl.ttl"
MFW_SHAPES = MFW / "mfw-planner" / "shapes" / "powl2.shacl.ttl"
MFW_RUST_EMITTER = MFW / "mfw-planner" / "src" / "projection" / "powl_rdf.rs"

PLAN = [
    "(unstack b a)",
    "(put-down b)",
    "(pick-up a)",
    "(stack a c)",
    "; cost = 4 (unit cost)",
]

BASE = "urn:skdecide:plan"


@pytest.fixture
def turtle() -> str:
    return project_plan_to_powl(PLAN, base_iri=BASE)


def plan_lines_from_model(model) -> list[str]:
    """Recover VAL-format plan lines from a decoded model."""
    lines = []
    for child in model.ordered_children():
        leaf = model.leaves[child.child_model]
        arguments = [
            model.bindings[b].bound_object.rsplit("/object/", 1)[-1]
            for b in leaf.binds_parameter
        ]
        lines.append("(" + " ".join([leaf.activity_label] + arguments) + ")")
    return lines


# ---------------------------------------------------------------------------
# The regression that motivated this file
# ---------------------------------------------------------------------------


class TestShaclConformance:
    """Re-expresses the committed shapes. Would have caught the real defect."""

    def test_every_activity_leaf_implements_an_action(self, turtle):
        """powl2:ActivityLeafShape: mfwp:implementsAction minCount 1 / maxCount 1.

        This is the assertion whose absence let SHACL-invalid output ship.
        """
        leaves = [
            block
            for block in turtle.split("\n\n")
            if "a powl2:Leaf, powl2:ActivityLeaf" in block
        ]
        assert len(leaves) == 4
        for block in leaves:
            assert block.count("mfwp:implementsAction") == 1, (
                "every powl2:ActivityLeaf must carry exactly one "
                f"mfwp:implementsAction; got:\n{block}"
            )

    def test_shape_file_still_requires_what_we_assert(self):
        """The shapes are the authority; assert we did not drift from them."""
        if not MFW_SHAPES.exists():
            pytest.skip(f"BLOCKED:MFW_SHAPES_ABSENT: {MFW_SHAPES} not present")
        shapes = MFW_SHAPES.read_text()
        assert "powl2:ActivityLeafShape" in shapes
        assert "mfwp:implementsAction" in shapes
        # 3 node shapes, 6 sh:property constraint blocks.
        assert shapes.count("a sh:NodeShape") == 3
        assert shapes.count("sh:property") == 6

    def test_root_binds_its_source_domain(self, turtle):
        assert "prov:wasDerivedFrom" in turtle, (
            "the prov: prefix was declared and never used; mfw's emitter binds "
            "the plan to its domain with prov:wasDerivedFrom"
        )
        model = parse_powl_turtle(turtle)
        assert model.derived_from == (BASE,)
        assert model.was_derived_from == (f"{BASE}/domain",)

    def test_partial_order_carries_actual_order_edges(self, turtle):
        """A declared PartialOrder with zero edges is a chain by accident."""
        assert turtle.count("powl2:precedes") == 3, (
            "4 steps in total order must yield 3 powl2:precedes edges"
        )
        model = parse_powl_turtle(turtle)
        ordered = model.ordered_children()
        for before, after in zip(ordered, ordered[1:]):
            assert after.iri in before.precedes

    def test_rust_emitter_agrees_on_the_terms_we_emit(self):
        if not MFW_RUST_EMITTER.exists():
            pytest.skip(
                f"BLOCKED:MFW_SOURCE_ABSENT: {MFW_RUST_EMITTER} not present"
            )
        rust = MFW_RUST_EMITTER.read_text()
        for term in (
            "mfwp:implementsAction",
            "prov:wasDerivedFrom",
            "powl2:precedes",
        ):
            assert term in rust, f"{term} absent from mfw's reference emitter"


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_project_parse_project_is_byte_identical(self, turtle):
        model = parse_powl_turtle(turtle)
        again = project_plan_to_powl(plan_lines_from_model(model), base_iri=BASE)
        assert again == turtle

    def test_decoded_structure_matches_the_plan(self, turtle):
        model = parse_powl_turtle(turtle)
        assert model.activity_count == 4
        assert len(model.children) == 4
        assert len(model.leaves) == 4
        assert [c.child_index for c in model.ordered_children()] == [0, 1, 2, 3]
        assert [
            model.leaves[c.child_model].activity_label
            for c in model.ordered_children()
        ] == ["unstack", "put-down", "pick-up", "stack"]
        assert model.projection == "total-order"

    def test_comment_lines_are_not_activities(self, turtle):
        assert "cost" not in turtle

    def test_empty_plan_decodes_to_an_empty_model(self):
        model = parse_powl_turtle(project_plan_to_powl([], base_iri=BASE))
        assert model.children == {}
        assert model.activity_count == 0

    def test_single_step_plan_has_no_precedes_edge(self):
        turtle = project_plan_to_powl(["(pick-up a)"], base_iri=BASE)
        assert "powl2:precedes" not in turtle
        assert len(parse_powl_turtle(turtle).children) == 1


# ---------------------------------------------------------------------------
# The real mfw artifact -- skipped, never substituted
# ---------------------------------------------------------------------------


class TestRealMfwArtifact:
    @pytest.fixture
    def reference(self) -> str:
        if not MFW_TICKET10_POWL.exists():
            pytest.skip(
                f"BLOCKED:MFW_ARTIFACT_ABSENT: {MFW_TICKET10_POWL} not present"
            )
        return MFW_TICKET10_POWL.read_text()

    def test_decoder_accepts_mfws_committed_output(self, reference):
        """Our decoder must read the real emitter's real output, unmodified."""
        model = parse_powl_turtle(reference)
        assert POWL2 + "Model" in model.types
        assert POWL2 + "PartialOrder" in model.types
        assert model.activity_count == len(model.children)
        assert model.projection == "total-order"

    def test_mfws_own_artifact_satisfies_the_shape_we_enforce(self, reference):
        model = parse_powl_turtle(reference)
        for leaf in model.leaves.values():
            assert leaf.implements_action.startswith("urn:mfw:id:")
        assert model.was_derived_from

    def test_prefixes_are_expanded_not_compared_as_strings(self, reference):
        model = parse_powl_turtle(reference)
        assert model.iri.startswith("urn:mfw:id:")
        leaf = next(iter(model.leaves.values()))
        assert not leaf.implements_action.startswith("mfwp:")
        assert MFWP.endswith(":") and PROV.endswith("#")


# ---------------------------------------------------------------------------
# Rejection cases -- a decoder that skips what it cannot read cannot validate
# ---------------------------------------------------------------------------


def _mutate(turtle: str, old: str, new: str) -> str:
    assert old in turtle, f"fixture drifted: {old!r} not present"
    return turtle.replace(old, new, 1)


class TestRejections:
    def test_missing_implements_action_is_refused(self, turtle):
        broken = _mutate(
            turtle, f"    mfwp:implementsAction <{BASE}/unstack> ;\n", ""
        )
        with pytest.raises(PowlDecodeError, match="implementsAction"):
            parse_powl_turtle(broken)

    def test_missing_derived_from_is_refused(self, turtle):
        broken = _mutate(turtle, f"    powl2:derivedFrom <{BASE}> ;\n", "")
        with pytest.raises(PowlDecodeError, match="derivedFrom"):
            parse_powl_turtle(broken)

    def test_missing_prov_derivation_is_refused(self, turtle):
        broken = _mutate(turtle, f"    prov:wasDerivedFrom <{BASE}/domain> ;\n", "")
        with pytest.raises(PowlDecodeError, match="wasDerivedFrom"):
            parse_powl_turtle(broken)

    def test_duplicate_child_index_is_refused(self, turtle):
        broken = _mutate(
            turtle, '    powl2:childIndex "1"^^xsd:integer ;', '    powl2:childIndex "0"^^xsd:integer ;'
        )
        with pytest.raises(PowlDecodeError, match="childIndex"):
            parse_powl_turtle(broken)

    def test_non_integer_ordinal_is_refused(self, turtle):
        broken = _mutate(
            turtle, 'mfwp:planOrdinal "0"^^xsd:integer', 'mfwp:planOrdinal "first"'
        )
        with pytest.raises(PowlDecodeError, match="planOrdinal"):
            parse_powl_turtle(broken)

    def test_cyclic_precedes_is_refused(self, turtle):
        broken = turtle + (
            f"\n<{BASE}/plan/binding-slot/3> powl2:precedes "
            f"<{BASE}/plan/binding-slot/0> .\n"
        )
        with pytest.raises(PowlDecodeError, match="cycle"):
            parse_powl_turtle(broken)

    def test_dangling_child_model_is_refused(self, turtle):
        broken = _mutate(
            turtle,
            f"    powl2:childModel <{BASE}/plan/step/0> .",
            f"    powl2:childModel <{BASE}/plan/step/99> .",
        )
        with pytest.raises(PowlDecodeError, match="dangling"):
            parse_powl_turtle(broken)

    def test_dangling_binds_parameter_is_refused(self, turtle):
        broken = _mutate(
            turtle,
            f"    mfwp:bindsParameter <{BASE}/plan/step/0/binding/0> ;",
            f"    mfwp:bindsParameter <{BASE}/plan/step/0/binding/7> ;",
        )
        with pytest.raises(PowlDecodeError, match="dangling"):
            parse_powl_turtle(broken)

    def test_stray_predicate_after_terminator_is_refused(self, turtle):
        broken = turtle + '\n    mfwp:projection "temporal-order" .\n'
        with pytest.raises(PowlDecodeError):
            parse_powl_turtle(broken)

    def test_unknown_construct_is_refused(self, turtle):
        broken = _mutate(
            turtle,
            f"    powl2:derivedFrom <{BASE}> ;",
            "    powl2:derivedFrom [ a powl2:Thing ] ;",
        )
        with pytest.raises(PowlDecodeError):
            parse_powl_turtle(broken)

    def test_undeclared_prefix_is_refused(self, turtle):
        broken = _mutate(
            turtle, "    mfwp:projection", "    nosuch:projection"
        )
        with pytest.raises(PowlDecodeError, match="undeclared prefix"):
            parse_powl_turtle(broken)

    def test_unterminated_statement_is_refused(self, turtle):
        with pytest.raises(PowlDecodeError, match="unterminated"):
            parse_powl_turtle(turtle + f"\n<{BASE}/x> a powl2:Leaf ;\n")

    def test_activity_count_disagreement_is_refused(self, turtle):
        broken = _mutate(
            turtle,
            'mfwp:activityCount "4"^^xsd:integer',
            'mfwp:activityCount "9"^^xsd:integer',
        )
        with pytest.raises(PowlDecodeError, match="activityCount"):
            parse_powl_turtle(broken)

    def test_validate_powl_is_callable_independently(self, turtle):
        assert validate_powl(parse_powl_turtle(turtle)) is not None


# ---------------------------------------------------------------------------
# The projector remains a projector
# ---------------------------------------------------------------------------


def test_projection_claims_no_admission(turtle):
    """Same boundary as test_chatman_chain_chicago.py, asserted at unit level."""
    for forbidden in ("Admitted", "admitted", "ALIVE", "receipt("):
        assert forbidden not in turtle
