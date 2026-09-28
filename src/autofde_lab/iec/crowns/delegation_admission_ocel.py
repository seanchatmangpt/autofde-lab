"""OCEL 2.0 projection for delegation/admission histories.

The history receipt remains canonical evidence. This module projects that receipt
into the repository's OCEL model so process-conformance tooling can observe
admission, delegation growth/contraction, evidence revocation, and failed standing
without inventing new authority.
"""

from __future__ import annotations

from typing import Any, Mapping

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import OcelAttribute, OcelAttributeValue, OcelObject

from .model import IECRefusal

__all__ = ["history_receipt_to_ocel"]


def _string(value: Any) -> OcelAttributeValue:
    return OcelAttributeValue.string(str(value))


def _integer(value: Any) -> OcelAttributeValue:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            f"expected integer, got {value!r}",
        )
    return OcelAttributeValue.integer(value)


def history_receipt_to_ocel(receipt: Mapping[str, Any]) -> OcelLog:
    """Project one evaluated history receipt into a validated OCEL log."""
    if receipt.get("schema") != "autofde-lab.delegation-admission-history-receipt/1":
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            "unexpected history receipt schema",
        )

    subject = receipt.get("subject")
    receipt_id = receipt.get("receipt_id")
    snapshots = receipt.get("snapshots")
    transitions = receipt.get("transitions")
    if not isinstance(subject, str) or not subject:
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            "history receipt subject is missing",
        )
    if not isinstance(receipt_id, str) or not receipt_id:
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            "history receipt identity is missing",
        )
    if not isinstance(snapshots, list) or not isinstance(transitions, list):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            "snapshots/transitions must be lists",
        )

    subject_id = "delegation-subject"
    log = OcelLog.new().with_objects(
        OcelObject(
            subject_id,
            "DelegationSubject",
            (
                OcelAttribute("subject", _string(subject)),
                OcelAttribute("history_receipt_id", _string(receipt_id)),
            ),
        )
    )

    for snapshot in snapshots:
        if not isinstance(snapshot, Mapping):
            raise IECRefusal(
                "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
                "snapshot must be an object",
            )
        sequence = snapshot.get("sequence")
        snapshot_id = f"admission-snapshot-{sequence}"
        attributes = [
            OcelAttribute("sequence", _integer(sequence)),
            OcelAttribute("receipt_id", _string(snapshot.get("receipt_id"))),
            OcelAttribute("producer_id", _string(snapshot.get("producer_id"))),
            OcelAttribute("gate", _string(snapshot.get("gate"))),
            OcelAttribute(
                "delegation_units",
                _integer(snapshot.get("delegation_units")),
            ),
            OcelAttribute(
                "admission_capacity_units",
                _integer(snapshot.get("admission_capacity_units")),
            ),
            OcelAttribute(
                "admission_debt_units",
                _integer(snapshot.get("admission_debt_units")),
            ),
        ]
        standing = snapshot.get("standing")
        if standing is not None:
            attributes.append(OcelAttribute("standing", _string(standing)))
        log = log.with_objects(
            OcelObject(
                snapshot_id,
                "AdmissionSnapshot",
                tuple(attributes),
            )
        )
        log = log.append_event(
            f"evt-{sequence:04d}-AdmissionSnapshotObserved",
            "AdmissionSnapshotObserved",
            [(subject_id, "subject"), (snapshot_id, "snapshot")],
            timestamp_ns=sequence * 10,
            attributes={
                "gate": _string(snapshot.get("gate")),
                "delegation_units": _integer(snapshot.get("delegation_units")),
                "capacity_units": _integer(
                    snapshot.get("admission_capacity_units")
                ),
            },
        )
        if snapshot.get("gate") != "PASS":
            log = log.append_event(
                f"evt-{sequence:04d}-AdmissionFailed",
                "AdmissionFailed",
                [(subject_id, "subject"), (snapshot_id, "snapshot")],
                timestamp_ns=sequence * 10 + 1,
                attributes={
                    "debt_units": _integer(snapshot.get("admission_debt_units")),
                    "falsifiers": _string(
                        ",".join(str(x) for x in snapshot.get("falsifiers", []))
                    ),
                },
            )

    for transition in transitions:
        if not isinstance(transition, Mapping):
            raise IECRefusal(
                "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
                "transition must be an object",
            )
        start = transition.get("from_sequence")
        end = transition.get("to_sequence")
        transition_id = f"admission-transition-{start}-{end}"
        log = log.with_objects(
            OcelObject(
                transition_id,
                "AdmissionTransition",
                (
                    OcelAttribute(
                        "receipt_id",
                        _string(transition.get("receipt_id")),
                    ),
                    OcelAttribute(
                        "comparison_receipt_id",
                        _string(transition.get("comparison_receipt_id")),
                    ),
                    OcelAttribute(
                        "delegation_delta",
                        _integer(transition.get("delegation_delta")),
                    ),
                    OcelAttribute(
                        "capacity_delta",
                        _integer(transition.get("capacity_delta")),
                    ),
                    OcelAttribute(
                        "growth_law",
                        _string(transition.get("growth_law")),
                    ),
                ),
            )
        )
        log = log.append_event(
            f"evt-{end:04d}-AdmissionTransition",
            "AdmissionTransition",
            [
                (subject_id, "subject"),
                (f"admission-snapshot-{start}", "from"),
                (f"admission-snapshot-{end}", "to"),
                (transition_id, "transition"),
            ],
            timestamp_ns=end * 10 + 2,
            attributes={
                "delegation_delta": _integer(transition.get("delegation_delta")),
                "capacity_delta": _integer(transition.get("capacity_delta")),
                "growth_law": _string(transition.get("growth_law")),
                "capacity_loss": _string(transition.get("capacity_loss")),
            },
        )

    return log.validate(strict_qualifiers=True)
