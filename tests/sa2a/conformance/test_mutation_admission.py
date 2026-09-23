# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Identity/digest mutation falsifiers for the Admission & Shape Falsification Court.

Per `.claude/rules/level4-completion-law.md` "Mutation law":

    for every required relation R, construct an otherwise-complete episode,
    mutate exactly R's identity, and require admission to produce a typed
    non-ALIVE evidence object.

This file targets the real `AdmissionCourt` implementation
(`src/autofde_lab/sa2a/conformance/courts/admission_court.py`) and its real
downstream collaborators (`AdmissionPipeline`, `AuthorityBroker`,
`ConsequenceBoundary`, `ConstructionReceipt`). Each test:

  1. Constructs an otherwise-complete, currently-valid admission or evidence
     episode for this court (asserted valid BEFORE mutation, so the mutation
     is proven to be the only broken thing).
  2. Mutates EXACTLY ONE identity or digest field in that episode (issuer
     IRI, actor-id binding, or a construction-receipt digest) to a
     wrong-but-well-formed value.
  3. Asserts the real court/broker/boundary REJECTS the mutated episode with
     a typed, non-ALIVE refusal code -- never a silent pass, never a broad
     `except` swallowing the distinction.

Strict Chicago Zero-Mock Standard (repo-wide, see
`.claude/rules/testing-chicago-style.md`):
- Real `AdmissionCourt`, real `AdmissionPipeline.admit()`, real
  `AuthorityBroker`, real `ConsequenceBoundary`, real `ReceiptStore`.
- Real disk I/O consequence probes (own `RealDiskProbeActuator` /
  `IndependentDiskProbeVerifier`, same shape as the existing zero-mock test
  in `tests/sa2a/conformance/test_court_admission.py`, kept local here so
  this file does not depend on or modify that file).
- Zero unittest.mock / Mock / MagicMock / patch / monkeypatch.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from autofde_lab.sa2a.admission.pipeline import (
    REFUSED_PROVENANCE,
    AdmissionPipeline,
    AdmissionResult,
)
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import ConsequenceBoundary, ExecutionEnvelope
from autofde_lab.sa2a.brce.receipts import ReceiptStore, TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.admission_court import AdmissionCourt
from autofde_lab.sa2a.construct.constructor import (
    AdmittedSemantics,
    ArtifactManufacturer,
    TargetProfile,
)


class RealDiskProbeActuator:
    """Real consequence actuator that mutates external physical disk filesystem state.

    Local copy of the same shape used in `test_court_admission.py`'s zero-mock
    consequence-gating test -- kept independent so this file never imports
    from, or depends on, that test module.
    """

    def __init__(self, probe_path: Path) -> None:
        self._probe_path = probe_path

    def actuate(
        self, action_iri: str, target_resource: str, parameters: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        data = {
            "action": action_iri,
            "target": target_resource,
            "parameters": dict(parameters),
            "digest": hashlib.sha256(
                json.dumps(dict(sorted(parameters.items()))).encode("utf-8")
            ).hexdigest(),
        }
        self._probe_path.write_text(json.dumps(data), encoding="utf-8")
        return {"applied": True, "path": str(self._probe_path)}

    def actuator_digest(self) -> str:
        return f"actuator:mutation_probe:{self._probe_path.name}"


class IndependentDiskProbeVerifier:
    """Distinct, independent verifier inspecting real physical disk probe state."""

    def __init__(self, probe_path: Path) -> None:
        self._probe_path = probe_path

    def verify_postcondition(
        self,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        evidence: Mapping[str, Any] | None,
    ) -> bool:
        if not self._probe_path.exists():
            return False
        try:
            data = json.loads(self._probe_path.read_text(encoding="utf-8"))
            return (
                data.get("action") == action_iri
                and data.get("target") == target_resource
            )
        except Exception:
            return False

    def verifier_digest(self) -> str:
        return f"verifier:mutation_probe:{self._probe_path.name}"


VALID_ADMITTED_TTL = """
@prefix afl: <urn:autofde-lab:> .
@prefix vocab: <http://example.org/vocab/> .
afl:cluster_mutation_subject vocab:status 'ACTIVE' .
"""


def _admit_action_target_binding(
    action_iri: str, target_resource: str
) -> AdmissionResult:
    """Real, ADMITTED AdmissionResult whose admitted graph binds EXACTLY the given
    action_iri/target_resource via the real relational-binding triple
    `<action_iri> afl:targetResource <target_resource> .` that
    `ConsequenceBoundary._admission_covers_action_target()` (AFDE-2604) requires on
    `ExecutionEnvelope.admission_result` before `execute()`'s admission fence (now
    `require_admission=True` by default) will pass an envelope through to
    AuthorityBroker/DO at all.

    Uses a bare `AdmissionPipeline()` (not `AdmissionCourt().pipeline`) deliberately:
    `AdmissionCourt`'s own pipeline is configured with a strict `IdentityPolicy`
    (`allowed_subject_namespaces=("http://example.org/admitted/", "urn:autofde-lab:")`)
    that would itself refuse a candidate graph whose subject is an `urn:action:...` or
    `urn:resource:...` IRI -- those are this test file's own local action/target
    identifiers, not `AdmissionCourt`'s admitted namespaces, and changing them would
    touch identity strings this file's mutation tests are not about. A bare
    `AdmissionPipeline()` has the unrestricted default `IdentityPolicy()`
    (`allowed_subject_namespaces=()` => no namespace restriction), so it admits the
    exact binding triple these tests need while still enforcing every other real
    admission stage (parse, falsifiers, provenance, meta-admission) for real.
    """
    pipeline = AdmissionPipeline()
    result = pipeline.admit(
        f"@prefix afl: <urn:autofde-lab:> .\n"
        f"<{action_iri}> afl:targetResource <{target_resource}> .\n",
        provenance_record={
            "issuer": "urn:issuer:mutation-admission-binding",
            "timestamp": "2026-09-16T12:00:00Z",
        },
    )
    assert result.is_admitted is True, (
        f"Binding admission for action_iri={action_iri!r}, "
        f"target_resource={target_resource!r} must itself be ADMITTED before it can "
        f"anchor ConsequenceBoundary's admission gate; got standing={result.standing} "
        f"refusal={result.refusal_code} reasons={result.reasons}"
    )
    assert result.standing == Standing.ADMITTED
    return result


# =============================================================================
# Mutation 1: provenance issuer identity swap
#
# CHI-ADM-007 ("Untrusted Issuer") is a declared code
# (`AdmissionFalsificationCode.CHI_ADM_UNTRUSTED_ISSUER`) with no dedicated
# `AdmissionCourt.falsify_*` method and no coverage in
# `test_court_admission.py`. `AdmissionPipeline._check_provenance` (real
# collaborator, `src/autofde_lab/sa2a/admission/pipeline.py:439`) does gate on
# `trusted_issuers`, so this exercises that real, currently-uncovered path
# directly via `court.pipeline.admit()`.
# =============================================================================


def test_mutation_provenance_issuer_identity_swap(tmp_path: Path) -> None:
    """Swap EXACTLY the provenance issuer identity on an otherwise-valid episode.

    Baseline: identical candidate graph + timestamp, admitted with the real
    trusted issuer `urn:issuer:trusted-authority` -> ADMITTED.

    Mutation: the SAME candidate graph, the SAME timestamp, only the issuer
    IRI swapped to a different, well-formed-but-untrusted issuer IRI
    (`urn:issuer:rogue-mutation-actor`) that was never registered in
    `ProvenancePolicy.trusted_issuers`.

    Expected: the real `AdmissionPipeline.admit()` REFUSES with
    `REFUSED_PROVENANCE`, standing REFUSED -- not ADMITTED, not a silent pass.
    """
    consequence_probe = tmp_path / "probe_mutation_issuer.json"
    court = AdmissionCourt()

    # --- Step 1: otherwise-complete, currently-valid baseline episode -----
    baseline: AdmissionResult = court.pipeline.admit(
        VALID_ADMITTED_TTL,
        provenance_record={
            "issuer": "urn:issuer:trusted-authority",
            "timestamp": "2026-09-16T12:00:00Z",
        },
    )
    assert baseline.is_admitted is True, (
        f"Baseline episode must be currently-valid before mutation; "
        f"got standing={baseline.standing} refusal={baseline.refusal_code} "
        f"reasons={baseline.reasons}"
    )
    assert baseline.standing == Standing.ADMITTED
    assert baseline.receipt.admitted_graph_digest is not None

    # --- Step 2: mutate EXACTLY ONE identity -- the issuer IRI ------------
    mutated: AdmissionResult = court.pipeline.admit(
        VALID_ADMITTED_TTL,
        provenance_record={
            "issuer": "urn:issuer:rogue-mutation-actor",  # well-formed IRI, not trusted
            "timestamp": "2026-09-16T12:00:00Z",  # unchanged
        },
    )

    # --- Step 3: real court must reject, with a typed non-ALIVE result ----
    assert mutated.is_admitted is False, (
        "GAP: admission court accepted a candidate whose provenance issuer "
        "identity was swapped for an untrusted-but-well-formed issuer IRI; "
        "the real AdmissionPipeline should have refused with REFUSED_PROVENANCE."
    )
    assert mutated.standing == Standing.REFUSED
    assert mutated.refusal_code == REFUSED_PROVENANCE
    assert any("rogue-mutation-actor" in reason for reason in mutated.reasons)
    assert mutated.receipt.standing == Standing.REFUSED
    assert mutated.receipt.admitted_graph_digest is None

    # No downstream consequence was ever reachable from a refused admission.
    assert not consequence_probe.exists()


# =============================================================================
# Mutation 2: actor-id authority-grant identity swap, downstream of a real
# court admission, through the real BRCE ConsequenceBoundary.
# =============================================================================


def test_mutation_authority_actor_id_identity_swap(tmp_path: Path) -> None:
    """Swap EXACTLY the actor-id binding on an otherwise-valid consequence episode.

    Builds a real, currently-valid end-to-end episode: the AdmissionCourt
    admits a candidate graph, a real AuthorityGrant is issued to a specific
    actor identity, and a real BRCE ConsequenceBoundary actuates a real disk
    write for that exact actor -- succeeds, with independent verification.

    Mutation: a SECOND envelope, identical in every field (action, target,
    parameters, artifact wiring) EXCEPT the `actor_id`, which is swapped to a
    different, well-formed identity that was never granted authority.

    Expected: the real `ConsequenceBoundary.execute()` REFUSES with
    `REFUSED_NO_GRANT` before any actuation, and the disk probe from the
    legitimate run is left byte-for-byte untouched (no second write, no
    consequence for the unauthorized identity).
    """
    court = AdmissionCourt()
    probe_file = tmp_path / "probe_mutation_actor_id.json"

    # --- Step 0: a real court admission anchors this episode --------------
    admit_res: AdmissionResult = court.pipeline.admit(
        VALID_ADMITTED_TTL,
        provenance_record={
            "issuer": "urn:issuer:trusted-authority",
            "timestamp": "2026-09-16T12:00:00Z",
        },
    )
    assert admit_res.is_admitted is True

    actuator = RealDiskProbeActuator(probe_file)
    verifier = IndependentDiskProbeVerifier(probe_file)
    broker = AuthorityBroker()
    receipt_store = ReceiptStore()
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=receipt_store,
    )

    legit_actor = "urn:agent:mutation-legit-worker"
    rogue_actor = "urn:agent:mutation-rogue-worker"
    action_iri = "urn:action:mutation_write"
    target_resource = "urn:resource:mutation_probe"

    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-mutation-001",
            subject_id=legit_actor,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )

    # AFDE-2604: ConsequenceBoundary now defaults to require_admission=True, so
    # every envelope reaching execute() needs a real, bound Standing.ADMITTED
    # AdmissionResult whose admitted content contains the real
    # <action_iri> afl:targetResource <target_resource> . triple (per
    # `_admission_covers_action_target()`). Admission is incidental to what this
    # test actually probes (an actor-id authority-grant identity swap) -- both the
    # legit and mutated envelope share the SAME action_iri/target_resource, so the
    # SAME binding admission legitimately anchors both; only actor_id differs.
    action_target_admission = _admit_action_target_binding(action_iri, target_resource)

    # --- Step 1: otherwise-complete, currently-valid baseline episode -----
    legit_envelope = ExecutionEnvelope(
        idempotency_token="idemp-mutation-legit-01",
        action_iri=action_iri,
        target_resource=target_resource,
        parameters={"admission_digest": admit_res.digest},
        actor_id=legit_actor,
        admission_result=action_target_admission,
    )
    legit_result = boundary.execute(legit_envelope)
    assert legit_result.success is True, (
        f"Baseline consequence episode must be currently-valid before "
        f"mutation; got state={legit_result.state} "
        f"refusal={legit_result.refusal_code} reason={legit_result.reason}"
    )
    assert legit_result.state == TerminalReceiptState.EXECUTED
    assert probe_file.exists()
    legit_disk_content = probe_file.read_text(encoding="utf-8")
    legit_data = json.loads(legit_disk_content)
    assert legit_data["action"] == action_iri
    assert legit_data["target"] == target_resource

    # --- Step 2: mutate EXACTLY ONE identity -- the actor_id binding ------
    mutated_envelope = ExecutionEnvelope(
        idempotency_token="idemp-mutation-rogue-01",  # new token: not a replay hit
        action_iri=action_iri,  # unchanged
        target_resource=target_resource,  # unchanged
        parameters={"admission_digest": admit_res.digest},  # unchanged
        actor_id=rogue_actor,  # <-- the ONE mutated identity
        admission_result=action_target_admission,  # unchanged: same action/target
    )
    mutated_result = boundary.execute(mutated_envelope)

    # --- Step 3: real broker/boundary must reject, typed non-ALIVE result -
    assert mutated_result.success is False, (
        "GAP: ConsequenceBoundary actuated a real disk write for an actor "
        "identity that was swapped away from the granted subject_id, with "
        "no matching AuthorityGrant; expected REFUSED_NO_GRANT."
    )
    assert mutated_result.state == TerminalReceiptState.REFUSED
    assert mutated_result.refusal_code == "REFUSED_NO_GRANT"
    assert rogue_actor in mutated_result.reason

    # Zero consequence for the unauthorized identity: the disk probe file is
    # still exactly what the legitimate run wrote -- no second actuation.
    assert probe_file.read_text(encoding="utf-8") == legit_disk_content


# =============================================================================
# Mutation 3: construction-receipt digest corruption, downstream of a real
# court admission, through the real BRCE ConsequenceBoundary construction
# integrity gate (Step 3 of ConsequenceBoundary.execute).
# =============================================================================


def test_mutation_construction_receipt_digest_corruption(tmp_path: Path) -> None:
    """Corrupt EXACTLY the `admitted_input_digest` field of a real, currently-verifying receipt.

    Builds a real end-to-end construction episode: the AdmissionCourt admits
    a candidate graph, its real admitted digest seeds a real
    `AdmittedSemantics`, `ArtifactManufacturer.manufacture()` produces a real
    `ExecutableArtifact` bound by a real `ConstructionReceipt` -- and that
    receipt verifies True against the exact semantics/artifact pair it was
    minted from (asserted BEFORE mutation).

    Mutation: a byte-for-byte copy of that SAME receipt with EXACTLY ONE
    field corrupted -- `admitted_input_digest` swapped for a different,
    well-formed 64-hex-character SHA-256-shaped digest that was never the
    real digest of anything.

    Expected: `ConstructionReceipt.verify()` itself returns False, AND the
    real `ConsequenceBoundary.execute()` REFUSES with
    `REFUSED_CONSTRUCTION_INTEGRITY` before any actuation -- no disk write
    for the corrupted construction episode.
    """
    court = AdmissionCourt()
    probe_file = tmp_path / "probe_mutation_construction.json"

    # --- Step 0: a real court admission anchors this episode --------------
    admit_res: AdmissionResult = court.pipeline.admit(
        VALID_ADMITTED_TTL,
        provenance_record={
            "issuer": "urn:issuer:trusted-authority",
            "timestamp": "2026-09-16T12:00:00Z",
        },
    )
    assert admit_res.is_admitted is True
    assert admit_res.canonical_ntriples is not None
    assert admit_res.digest is not None

    admitted_semantics = AdmittedSemantics(
        ontology_id="urn:autofde-lab:mutation-construct-probe",
        canonical_triples=(admit_res.canonical_ntriples,),
        provenance_hash=admit_res.digest,
    )

    manufacturer = ArtifactManufacturer()
    artifact = manufacturer.manufacture(
        admitted_semantics, target_profile=TargetProfile.PYTHON_EPHEMERAL
    )

    # --- Step 1: otherwise-complete, currently-valid baseline receipt -----
    assert artifact.receipt.verify(admitted_semantics, artifact) is True, (
        "Baseline ConstructionReceipt must currently verify against its own "
        "AdmittedSemantics/ExecutableArtifact pair before mutation."
    )

    actuator = RealDiskProbeActuator(probe_file)
    verifier = IndependentDiskProbeVerifier(probe_file)
    broker = AuthorityBroker()
    receipt_store = ReceiptStore()
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=receipt_store,
    )

    actor_id = "urn:agent:mutation-construct-worker"
    action_iri = "urn:action:mutation_construct_write"
    target_resource = "urn:resource:mutation_construct_probe"

    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-mutation-construct-001",
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )

    # AFDE-2604: ConsequenceBoundary now defaults to require_admission=True, so
    # every envelope reaching execute() needs a real, bound Standing.ADMITTED
    # AdmissionResult whose admitted content contains the real
    # <action_iri> afl:targetResource <target_resource> . triple (per
    # `_admission_covers_action_target()`). Admission is incidental to what this
    # test actually probes (a construction-receipt digest corruption); both the
    # legit and mutated envelope share the SAME action_iri/target_resource, so the
    # SAME binding admission legitimately anchors both -- only construction_receipt
    # differs.
    action_target_admission = _admit_action_target_binding(action_iri, target_resource)

    legit_envelope = ExecutionEnvelope(
        idempotency_token="idemp-mutation-construct-legit-01",
        action_iri=action_iri,
        target_resource=target_resource,
        parameters={},
        actor_id=actor_id,
        artifact=artifact,
        construction_receipt=artifact.receipt,
        admitted_semantics=admitted_semantics,
        admission_result=action_target_admission,
    )
    legit_result = boundary.execute(legit_envelope)
    assert legit_result.success is True, (
        f"Baseline construction-integrity episode must be currently-valid "
        f"before mutation; got state={legit_result.state} "
        f"refusal={legit_result.refusal_code} reason={legit_result.reason}"
    )
    assert legit_result.state == TerminalReceiptState.EXECUTED
    assert probe_file.exists()
    legit_disk_content = probe_file.read_text(encoding="utf-8")

    # --- Step 2: mutate EXACTLY ONE digest field ---------------------------
    corrupted_digest = "0" * 64  # well-formed SHA-256-shaped hex, never real
    assert corrupted_digest != artifact.receipt.admitted_input_digest
    mutated_receipt = dataclasses.replace(
        artifact.receipt,
        admitted_input_digest=corrupted_digest,
    )

    # The real verify() must itself catch the corruption.
    assert mutated_receipt.verify(admitted_semantics, artifact) is False, (
        "GAP: ConstructionReceipt.verify() accepted a corrupted "
        "admitted_input_digest binding."
    )

    mutated_envelope = ExecutionEnvelope(
        idempotency_token="idemp-mutation-construct-rogue-01",  # new token
        action_iri=action_iri,  # unchanged
        target_resource=target_resource,  # unchanged
        parameters={},  # unchanged
        actor_id=actor_id,  # unchanged, still an authorized identity
        artifact=artifact,  # unchanged
        construction_receipt=mutated_receipt,  # <-- the ONE mutated field
        admitted_semantics=admitted_semantics,  # unchanged
        admission_result=action_target_admission,  # unchanged: same action/target
    )
    mutated_result = boundary.execute(mutated_envelope)

    # --- Step 3: real boundary must reject, typed non-ALIVE result --------
    assert mutated_result.success is False, (
        "GAP: ConsequenceBoundary actuated a real disk write despite a "
        "ConstructionReceipt whose admitted_input_digest was corrupted; "
        "expected REFUSED_CONSTRUCTION_INTEGRITY."
    )
    assert mutated_result.state == TerminalReceiptState.REFUSED
    assert mutated_result.refusal_code == "REFUSED_CONSTRUCTION_INTEGRITY"
    assert mutated_result.prepared_receipt is None

    # Zero consequence for the corrupted construction episode: the disk
    # probe file is still exactly what the legitimate run wrote.
    assert probe_file.read_text(encoding="utf-8") == legit_disk_content
