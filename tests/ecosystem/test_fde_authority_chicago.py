# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The 14 FDE falsifiers, one negative fixture each.

Scope, stated first so this file is not cited for more than it establishes:
these tests exercise :mod:`skdecide.fabric.fde` against **committed authority
artifacts**. They establish that the compiler/checker refuses each named
organizational failure with a typed code. They establish nothing about any
customer, any real grant, or any organizational standing -- no test here can
stand in for a customer operating owner's acceptance, and none tries to.

Two boundaries this file defends, both by assertion rather than by comment:

* :class:`TestModuleMintsNothing` -- ``fde.py`` exposes no function returning a
  grant, token, capability handle, signature, or receipt. Computing "would
  this grant permit this operation?" is advisory; authorizing is MFW's broker.
  ``tests/ecosystem/test_chatman_chain_chicago.py::TestPlannerOutputIsCandidateNotActuation``
  defends the technical half of the same line.
* :class:`TestActKindsAreNonInterchangeable` -- the seven kinds
  (`.claude/rules/fde-authority-boundary.md`) cannot collapse into one another.

Every assertion is on a typed ``.code`` / ``.reason``, never on message text.
Skips carry a ``BLOCKED:<TOKEN>:`` prefix and are used only for genuine absence
of a prerequisite, per ``tests/ecosystem/CLAUDE.md`` invariant 1.

Nothing in the *positive* fixture asserts a customer decision: it declares a
sunset **authority** (who could decide) and no sunset **authorization** (a
decision taken). Writing ``customerAuthorizedRetirement true`` into a fixture
would manufacture the authority the gate exists to require -- invariant 7. The
only fixtures carrying that flag are negatives, exercised as refusals.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest

from skdecide.fabric import fde
from skdecide.fabric.fde import (
    AuthorityError,
    ProposedOperation,
    load_authority,
    permits,
    validate_authority,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fde"
BASE = FIXTURES / "customer-authority.ttl"
SHAPES = FIXTURES / "customer-authority.shacl.ttl"

FDE_NS = "urn:skdecide:fde:"
CUSTOMER = FDE_NS + "customer/acme"
CUSTOMER_EMEA = FDE_NS + "customer/acme-emea"
CAP_REBALANCE = FDE_NS + "capability/schedule-rebalance"
CAP_PAYROLL = FDE_NS + "capability/payroll-adjust"
OP_REBALANCE = FDE_NS + "operation/rebalance-north"
OP_PAYROLL = FDE_NS + "operation/payroll-adjust-north"
RS_NORTH = FDE_NS + "resource/plant-north"
RS_SOUTH = FDE_NS + "resource/plant-south"
ES_STAGING = FDE_NS + "environment/staging"
ES_PRODUCTION = FDE_NS + "environment/production"
FDE_PARTY = FDE_NS + "party/fde-architect"
VENDOR = FDE_NS + "party/vendor-manufacture"
VERIFIER = FDE_NS + "verifier/ggen-legacy-replay"

IN_WINDOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
IN_PAST_WINDOW = datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc)
EXEC_DIGEST = "blake3:" + "9b2e4a70" * 8


def fixture(name: str):
    path = FIXTURES / name
    assert path.exists(), f"missing committed fixture {path}"
    return load_authority(str(path))


def proposal(**overrides) -> ProposedOperation:
    """A proposal that the base grant permits, unless a field is overridden."""
    kwargs = dict(
        customer=CUSTOMER,
        capability=CAP_REBALANCE,
        operation=OP_REBALANCE,
        resource_scope=RS_NORTH,
        environment_scope=ES_STAGING,
        at=IN_WINDOW,
        executable_digest=EXEC_DIGEST,
        affected_resources=4,
        irreversible_actions=0,
        duration_seconds=900,
        delegated=False,
        performed_by=VENDOR,
        manufactured_by=VENDOR,
        verified_by=VERIFIER,
    )
    kwargs.update(overrides)
    return ProposedOperation(**kwargs)


def refusal_code(name: str, **overrides) -> str:
    """Run ``permits`` against a fixture, assert it refused, return the code."""
    model = fixture(name)
    grant = model.the_grant()
    verdict = permits(model, grant, proposal(**overrides))
    assert not verdict.allowed, (
        f"{name}: expected a refusal, got {verdict.verdict} ({verdict.detail})"
    )
    return verdict.reason


def validation_code(name: str) -> str:
    model = fixture(name)
    with pytest.raises(AuthorityError) as caught:
        validate_authority(model)
    return caught.value.code


# ---------------------------------------------------------------------------
# The artifact itself
# ---------------------------------------------------------------------------


class TestTheAuthorityArtifact:
    def test_shapes_file_is_committed(self):
        assert SHAPES.exists()
        text = SHAPES.read_text()
        assert text.count("a sh:NodeShape") >= 3
        assert text.count("sh:property") >= 6

    def test_base_artifact_validates(self):
        assert validate_authority(fixture("customer-authority.ttl")) is not None

    def test_base_artifact_permits_the_bounded_operation(self):
        model = fixture("customer-authority.ttl")
        verdict = permits(model, model.the_grant(), proposal())
        assert verdict.allowed, verdict.detail
        assert verdict.verdict == "ALLOW"

    def test_no_naked_approval_boolean_anywhere(self):
        """`approved = true` records no decider, no right, and no evidence.

        Scanned over statement lines only; the prose comments deliberately
        discuss the banned shape in order to say why it is banned.
        """
        for path in sorted(FIXTURES.glob("*.ttl")):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                lowered = stripped.lower()
                for banned in ("approved", "approval", "signoff", "sign_off", "ok "):
                    assert banned not in lowered, (
                        f"{path.name}: {stripped!r} carries {banned!r}"
                    )

    def test_every_required_entity_kind_is_modelled(self):
        turtle = BASE.read_text()
        for term in (
            "fdet:CustomerOrganization",
            "fdet:FdeIdentity",
            "fdet:CustomerAuthorityIdentity",
            "fdet:organizationalRole",
            "fdet:DecisionRight",
            "fdet:AuthorizedCapability",
            "fdet:AuthorizedOperation",
            "fdet:ResourceScope",
            "fdet:EnvironmentScope",
            "fdet:ValidityInterval",
            "fdet:ConsequenceBounds",
            "fdet:Verifier",
            "fdet:Postcondition",
            "fdet:AdoptionOwner",
            "fdet:SunsetAuthority",
            "fdet:grantIdentifier",
        ):
            assert term in turtle, f"authority artifact does not model {term}"

    def test_positive_fixture_asserts_no_customer_decision(self):
        """Invariant 7: a fixture must not manufacture customer authority."""
        turtle = BASE.read_text()
        assert "customerAuthorizedRetirement" not in turtle
        assert "fdet:SunsetAuthorization" not in turtle
        assert "fdet:AdoptionDecision" not in turtle


# ---------------------------------------------------------------------------
# The boundary: compile and check, never mint or enforce
# ---------------------------------------------------------------------------


class TestModuleMintsNothing:
    """`.claude/rules/ecosystem-boundary.md` applied to organizational authority.

    Reads as pedantic until it isn't: the quiet failure mode is a helper named
    ``issue_grant`` appearing six months from now and being used as though the
    envelope it returns were authorization.
    """

    MINTING_VERBS = (
        "mint",
        "issue",
        "sign",
        "authorize",
        "authorise",
        "grant_",
        "receipt",
        "token",
        "certify",
        "admit",
        "actuate",
        "execute",
    )

    def test_no_public_callable_names_a_minting_verb(self):
        """Scoped to functions.

        Dataclasses are the modelled vocabulary -- ``AuthorizedOperation`` and
        ``SunsetAuthorization`` are the names of customer acts this module
        *reads*, and renaming them would obscure the artifact rather than
        tighten the boundary. What must not exist is a verb you could call to
        obtain authority.
        """
        offenders = [
            name
            for name, obj in vars(fde).items()
            if not name.startswith("_")
            and inspect.isfunction(obj)
            and obj.__module__ == fde.__name__
            and any(verb in name.lower() for verb in self.MINTING_VERBS)
        ]
        assert not offenders, (
            f"fde.py exposes minting-shaped callables {offenders}; this module "
            "may compile, structure and check an authority envelope, never "
            "mint or enforce one"
        )

    def test_permission_carries_no_bearer_value(self):
        model = fixture("customer-authority.ttl")
        verdict = permits(model, model.the_grant(), proposal())
        fields = set(vars(verdict))
        assert fields == {"allowed", "reason", "detail", "advisory"}, fields
        for forbidden in ("token", "signature", "receipt", "capability", "grant"):
            assert not hasattr(verdict, forbidden)
        assert verdict.advisory is True

    def test_permission_is_not_usable_as_a_truth_value(self):
        """`if permission:` would swallow a refusal silently."""
        model = fixture("customer-authority.ttl")
        verdict = permits(model, model.the_grant(), proposal())
        with pytest.raises(TypeError):
            bool(verdict)

    def test_validate_returns_the_input_and_confers_nothing(self):
        model = fixture("customer-authority.ttl")
        assert validate_authority(model) is model

    def test_no_function_returns_a_grant_object(self):
        """No public callable is annotated as producing an AuthorityGrant."""
        for name, obj in vars(fde).items():
            if name.startswith("_") or not inspect.isfunction(obj):
                continue
            if obj.__module__ != fde.__name__:
                continue
            annotation = inspect.signature(obj).return_annotation
            assert "AuthorityGrant" not in str(annotation), (
                f"{name} is annotated to return {annotation}; grants are read "
                "and checked here, never produced"
            )

    def test_repository_does_not_author_customer_or_broker_acts(self):
        assert fde.AUTHORABLE_HERE == (fde.KIND_FDE_RECOMMENDATION,)
        assert fde.KIND_CUSTOMER_AUTHORITY_GRANT not in fde.AUTHORABLE_HERE
        assert fde.KIND_BROKER_AUTHORIZATION not in fde.AUTHORABLE_HERE


class TestActKindsAreNonInterchangeable:
    def test_seven_kinds_are_declared(self):
        assert len(fde.ACT_KINDS) == 7
        assert len(set(fde.ACT_KINDS)) == 7

    def test_a_node_may_not_carry_two_act_kinds(self):
        assert validation_code("neg-15-act-kind-collapse.ttl") == (
            fde.REFUSED_ACT_KIND_COLLAPSE
        )


# ---------------------------------------------------------------------------
# The 14 falsifiers
# ---------------------------------------------------------------------------


class TestFalsifier01ModelUsedWithoutCustomerValidation:
    """A compiled customer model is a hypothesis until the customer says so."""

    def test_refused(self):
        assert validation_code("neg-01-model-not-validated.ttl") == (
            fde.REFUSED_UNVALIDATED_MODEL
        )

    def test_permits_propagates_the_same_typed_code(self):
        assert refusal_code("neg-01-model-not-validated.ttl") == (
            fde.REFUSED_UNVALIDATED_MODEL
        )


class TestFalsifier02FdeClaimsCustomerAuthority:
    """The FDE may not be the source of the authority it operates under."""

    def test_refused(self):
        assert validation_code("neg-02-fde-claims-customer-authority.ttl") == (
            fde.REFUSED_FDE_SELF_AUTHORITY
        )

    def test_the_fixture_is_otherwise_well_formed(self):
        """The refusal is about who granted, not about a malformed file."""
        model = fixture("neg-02-fde-claims-customer-authority.ttl")
        grant = model.the_grant()
        assert grant.granted_by == FDE_PARTY
        assert model.parties[grant.granted_by].is_fde


class TestFalsifier03CapabilityMismatch:
    """Granted capability A; the operation is capability B."""

    def test_refused(self):
        assert (
            refusal_code(
                "neg-03-capability-not-granted.ttl",
                capability=CAP_PAYROLL,
                operation=OP_PAYROLL,
            )
            == fde.REFUSED_CAPABILITY_NOT_GRANTED
        )

    def test_the_granted_capability_still_passes(self):
        model = fixture("neg-03-capability-not-granted.ttl")
        verdict = permits(model, model.the_grant(), proposal())
        assert verdict.allowed, (
            "the refusal must be specific to the ungranted capability, not a "
            f"blanket refusal of the artifact: {verdict.detail}"
        )


class TestFalsifier04ModelChangedAfterApproval:
    """Editing the admitted model after approval, without re-admission."""

    def test_refused(self):
        assert validation_code("neg-04-model-changed-after-approval.ttl") == (
            fde.REFUSED_MODEL_DIGEST_DRIFT
        )

    def test_drift_is_detectable_because_the_validation_pins_bytes(self):
        model = fixture("neg-04-model-changed-after-approval.ttl")
        compiled = next(iter(model.models.values()))
        validation = model.validations[compiled.validation]
        assert compiled.model_digest != validation.validated_model_digest


class TestFalsifier05VerifiedButNobodyAccepted:
    """Technical verification succeeded; no adoption owner accepted."""

    def test_refused(self):
        assert validation_code("neg-05-verified-but-no-adoption-owner.ttl") == (
            fde.REFUSED_MISSING_ADOPTION_OWNER
        )

    def test_the_technical_chain_did_close_in_this_fixture(self):
        """Otherwise the test would be passing for the wrong reason."""
        model = fixture("neg-05-verified-but-no-adoption-owner.ttl")
        assert model.verdicts, "fixture must contain a successful verifier verdict"
        assert model.the_grant().adoption_owner is None


class TestFalsifier06FdeVerifiesItsOwnArtifact:
    """Self-certification: the producer's own check is not evidence."""

    def test_refused(self):
        assert validation_code("neg-06-fde-verifies-own-artifact.ttl") == (
            fde.REFUSED_SELF_CERTIFICATION
        )

    def test_the_verifier_is_not_independent_of_the_producer(self):
        model = fixture("neg-06-fde-verifies-own-artifact.ttl")
        verifier = model.verifiers[FDE_NS + "verifier/fde-inhouse"]
        consequence = next(iter(model.consequences.values()))
        assert consequence.produced_by not in verifier.independent_of


class TestFalsifier07AcceptedWithoutIndependentEvidence:
    """Acceptance resting on nothing is assent, not acceptance."""

    def test_refused(self):
        assert validation_code(
            "neg-07-accepted-without-independent-evidence.ttl"
        ) == fde.REFUSED_MISSING_INDEPENDENT_EVIDENCE

    def test_the_adoption_is_declared_adopted(self):
        model = fixture("neg-07-accepted-without-independent-evidence.ttl")
        adoption = next(iter(model.adoptions.values()))
        assert adoption.adoption_decision == "ADOPTED"
        assert adoption.on_evidence == ()


class TestFalsifier08GrantReusedForAnotherCustomerOrEnvironment:
    def test_reuse_for_another_customer_is_refused(self):
        assert (
            refusal_code("neg-08-grant-reused-other-customer.ttl")
            == fde.REFUSED_WRONG_CUSTOMER
        )

    def test_reuse_in_another_environment_is_refused(self):
        assert (
            refusal_code(
                "customer-authority.ttl", environment_scope=ES_PRODUCTION
            )
            == fde.REFUSED_OUT_OF_ENVIRONMENT_SCOPE
        )

    def test_reuse_on_another_resource_is_refused(self):
        assert (
            refusal_code("customer-authority.ttl", resource_scope=RS_SOUTH)
            == fde.REFUSED_OUT_OF_RESOURCE_SCOPE
        )

    def test_the_grant_identifier_is_unchanged_in_the_reuse_fixture(self):
        """Reuse means the same grant pointed elsewhere, not a new grant."""
        original = fixture("customer-authority.ttl").the_grant()
        reused = fixture("neg-08-grant-reused-other-customer.ttl").the_grant()
        assert reused.grant_identifier == original.grant_identifier
        assert reused.for_customer == CUSTOMER_EMEA


class TestFalsifier09ExpiredOrOverBounds:
    def test_expired_grant_is_refused(self):
        assert (
            refusal_code("neg-09-expired-and-over-bounds.ttl")
            == fde.REFUSED_GRANT_EXPIRED
        )

    def test_irreversible_action_beyond_bounds_is_refused(self):
        assert (
            refusal_code(
                "neg-09-expired-and-over-bounds.ttl",
                at=IN_PAST_WINDOW,
                irreversible_actions=1,
            )
            == fde.REFUSED_CONSEQUENCE_BOUNDS_EXCEEDED
        )

    def test_resource_count_beyond_bounds_is_refused(self):
        assert (
            refusal_code(
                "neg-09-expired-and-over-bounds.ttl",
                at=IN_PAST_WINDOW,
                affected_resources=3,
            )
            == fde.REFUSED_CONSEQUENCE_BOUNDS_EXCEEDED
        )

    def test_duration_beyond_bounds_is_refused(self):
        assert (
            refusal_code(
                "neg-09-expired-and-over-bounds.ttl",
                at=IN_PAST_WINDOW,
                affected_resources=1,
                duration_seconds=61,
            )
            == fde.REFUSED_CONSEQUENCE_BOUNDS_EXCEEDED
        )


class TestFalsifier10RetirementFlagWithoutAuthority:
    """`customer_authorized_retirement = true` with nobody behind it.

    This is the exact shape `.claude/rules/fde-authority-boundary.md` names:
    ``~/ggen-legacy/appliance/bin/decision-engine.py``'s last conjunct is a
    bare boolean in a manifest, and a true value there is unattributable
    unless it resolves to a record naming the authority and the decision
    right. The fixture writes the bare flag; the checker refuses it.
    """

    def test_refused(self):
        assert validation_code("neg-10-retirement-without-authority.ttl") == (
            fde.REFUSED_MISSING_SUNSET_AUTHORITY
        )

    def test_the_flag_really_is_set_in_the_fixture(self):
        model = fixture("neg-10-retirement-without-authority.ttl")
        sunset = next(iter(model.sunsets.values()))
        assert sunset.customer_authorized_retirement is True
        assert sunset.authorized_by is None


class TestFalsifier11ResumedBeforeOrganizationalAdmission:
    """Parent resumes from technical completion, skipping adoption."""

    def test_artifact_level_refusal(self):
        assert validation_code(
            "neg-11-resumed-before-organizational-admission.ttl"
        ) == fde.REFUSED_RESUMED_BEFORE_ORGANIZATIONAL_ADMISSION

    def test_live_recursive_resume_cannot_be_exercised_yet(self):
        """BLOCKED: no component runs the blocked-parent resume loop.

        The artifact-level property above is checked. The *dynamic* property
        -- that a running parent workflow does not resume until an adoption
        decision exists -- needs a recursive bootstrap controller, which
        ``test_chatman_chain_chicago.py::
        test_recursive_bootstrap_controller_is_absent_across_ecosystem``
        asserts is absent across the whole portfolio. Skipping rather than
        faking: there is no loop to observe.
        """
        controller = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "skdecide"
            / "fabric"
            / "recursive_controller.py"
        )
        if not controller.exists():
            pytest.skip(
                "BLOCKED:RECURSIVE_CONTROLLER_ABSENT: no component in the "
                "portfolio implements blocked -> child -> admit -> resume; "
                "only the artifact-level invariant is exercised"
            )
        pytest.fail(
            "a recursive controller now exists -- exercise the live resume "
            "ordering here instead of skipping"
        )


class TestFalsifier12AdoptedWithoutOwnershipObligations:
    def test_refused(self):
        assert validation_code(
            "neg-12-adopted-without-operating-obligations.ttl"
        ) == fde.REFUSED_MISSING_OPERATING_OBLIGATION

    def test_adoption_decision_without_obligations_is_also_refused(self):
        """Two distinct places the obligation can go missing; both refuse."""
        model = fixture("customer-authority.ttl")
        model.adoptions[FDE_NS + "adoption/x"] = fde.AdoptionDecision(
            iri=FDE_NS + "adoption/x",
            decided_by=FDE_NS + "owner/director-operations",
            on_evidence=(),
            adoption_decision="ADOPTED",
        )
        with pytest.raises(AuthorityError) as caught:
            validate_authority(model)
        assert caught.value.code == fde.REFUSED_MISSING_INDEPENDENT_EVIDENCE


class TestFalsifier13InformalEscalationInsteadOfChildWorkflow:
    def test_artifact_level_refusal(self):
        assert validation_code("neg-13-informal-escalation.ttl") == (
            fde.REFUSED_INFORMAL_ESCALATION_NOT_A_CHILD_WORKFLOW
        )

    def test_live_child_workflow_spawn_cannot_be_exercised_yet(self):
        """BLOCKED: nothing spawns a child workflow for a blocker.

        The artifact-level property -- a blocker whose ``resolutionMode`` is
        not ``CHILD_WORKFLOW`` is refused -- is checked above. Observing that a
        *recursive organizational* blocker actually causes a child workflow to
        be manufactured and admitted requires the same absent controller, plus
        an organizational-blocker driver that no component implements.
        """
        controller = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "skdecide"
            / "fabric"
            / "recursive_controller.py"
        )
        if not controller.exists():
            pytest.skip(
                "BLOCKED:CHILD_WORKFLOW_SPAWNER_ABSENT: no component spawns a "
                "child workflow from an organizational blocker; only the "
                "artifact-level invariant is exercised"
            )
        pytest.fail(
            "a controller now exists -- exercise the live spawn here instead"
        )


class TestFalsifier14SunsetAgainstAnUnadoptedReplacement:
    def test_refused(self):
        assert validation_code("neg-14-sunset-replacement-not-adopted.ttl") == (
            fde.REFUSED_REPLACEMENT_NOT_ORGANIZATIONALLY_ADMITTED
        )

    def test_the_replacement_is_technically_complete_in_the_fixture(self):
        """The point: technical completion is present, adoption is not."""
        model = fixture("neg-14-sunset-replacement-not-adopted.ttl")
        adoption = model.adoptions[FDE_NS + "adoption/replacement"]
        assert adoption.adoption_decision == "TECHNICALLY_COMPLETE"
        assert adoption.on_evidence, "a verifier verdict does exist"


# ---------------------------------------------------------------------------
# Remaining typed refusals from the required floor
# ---------------------------------------------------------------------------


class TestRemainingTypedRefusals:
    def test_delegation_not_allowed(self):
        assert (
            refusal_code("customer-authority.ttl", delegated=True)
            == fde.REFUSED_DELEGATION_NOT_ALLOWED
        )

    def test_executable_digest_mismatch(self):
        assert (
            refusal_code(
                "customer-authority.ttl", executable_digest="blake3:" + "00" * 32
            )
            == fde.REFUSED_EXECUTABLE_DIGEST_MISMATCH
        )

    def test_missing_decision_right(self):
        """An operation requiring a right the grant does not convey."""
        model = fixture("customer-authority.ttl")
        grant = model.the_grant()
        model.operations[OP_REBALANCE] = fde.AuthorizedOperation(
            iri=OP_REBALANCE,
            identifier="OP-REBALANCE-NORTH",
            under_capability=CAP_REBALANCE,
            on_resource=RS_NORTH,
            in_environment=ES_STAGING,
            requires_decision_right=(FDE_NS + "right/retire-legacy",),
        )
        verdict = permits(model, grant, proposal())
        assert verdict.reason == fde.REFUSED_MISSING_DECISION_RIGHT

    def test_every_required_refusal_reason_is_declared(self):
        required = {
            "WRONG_CUSTOMER",
            "MISSING_DECISION_RIGHT",
            "OUT_OF_RESOURCE_SCOPE",
            "OUT_OF_ENVIRONMENT_SCOPE",
            "GRANT_EXPIRED",
            "EXECUTABLE_DIGEST_MISMATCH",
            "CONSEQUENCE_BOUNDS_EXCEEDED",
            "CAPABILITY_NOT_GRANTED",
            "DELEGATION_NOT_ALLOWED",
            "SELF_CERTIFICATION",
            "UNVALIDATED_MODEL",
            "MISSING_ADOPTION_OWNER",
            "MISSING_SUNSET_AUTHORITY",
        }
        assert required.issubset(set(fde.REFUSAL_REASONS))

    def test_an_untyped_refusal_reason_is_rejected(self):
        with pytest.raises(ValueError):
            fde.refuse("BECAUSE_I_SAID_SO", "no")

    def test_malformed_turtle_is_refused_not_ignored(self):
        with pytest.raises(AuthorityError) as caught:
            fde.parse_authority_turtle("<urn:x> a fdet:AuthorityGrant ;")
        assert caught.value.code == fde.REFUSED_MALFORMED_ARTIFACT
