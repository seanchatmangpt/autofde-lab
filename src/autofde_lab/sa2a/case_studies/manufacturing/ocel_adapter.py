"""ocel_adapter.py — the one module every sa2a-mfg-01 builder imports.

Fully specified by CONTRACT.md §6. Thin, real wrapper over
``autofde_lab.ocel.log.OcelLog`` and ``autofde_lab.ocel.model.*``. Builder
modules (``resource_agent.py``, ``authority_agent.py``, ``actuator.py``,
``runtime.py``) never construct OCEL primitives directly and never disagree
on type/qualifier strings — every one of them imports only this module (plus
the standard library).

``OcelLog`` is frozen/immutable (see ``src/autofde_lab/ocel/log.py``): every
mutator (``with_objects``, ``append_event``) returns a *new* ``OcelLog``.
:class:`LogRef` is the one piece of shared mutable state the contract
permits — a mutable box around the current immutable log — so three
independently-written modules can each append into what is, from the
outside, "the same log" without importing each other.

Deviation from CONTRACT.md §6, reported per the task instructions: the
contract's own inline sketch of ``declare_equipment`` uses
``OcelAttribute(...)`` without importing it in the header import list (the
document says as much in its own trailing note, "``OcelAttribute`` import
was omitted above for brevity"). This module imports ``OcelAttribute`` for
real, as that trailing note directs. No other deviation was needed — the
real ``OcelLog.append_event`` / ``with_objects`` / ``validate`` /
``to_ocel2_json`` / ``digest`` signatures verified against
``src/autofde_lab/ocel/log.py`` match the contract's sketch exactly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import OcelAttribute, OcelAttributeValue, OcelObject

__all__ = [
    "OBJ_EQUIPMENT",
    "OBJ_PLAN",
    "OBJ_RECEIPT",
    "EVT_OBSERVATION",
    "EVT_PERMISSION",
    "EVT_PROHIBITION",
    "EVT_ACTUATION",
    "QUAL_HAS_FEATURE_OF_INTEREST",
    "QUAL_GENERATED",
    "QUAL_USED",
    "QUAL_ASSIGNEE",
    "QUAL_ACTS_ON",
    "LogRef",
    "new_log_ref",
    "declare_equipment",
    "record_observation",
    "record_authority_decision",
    "record_actuation",
    "validate_and_digest",
    "write_json",
]

# ── public OCEL vocabulary — every builder module uses these string
#    constants, never a hand-typed literal ─────────────────────────────────
OBJ_EQUIPMENT = "s4inma:ProductionEquipment"
OBJ_PLAN = "prov:Plan"
OBJ_RECEIPT = "Receipt"

EVT_OBSERVATION = "sosa:Observation"
EVT_PERMISSION = "odrl:Permission"
EVT_PROHIBITION = "odrl:Prohibition"
EVT_ACTUATION = "sosa:Actuation"

QUAL_HAS_FEATURE_OF_INTEREST = "sosa:hasFeatureOfInterest"  # Observation -> Equipment
QUAL_GENERATED = "prov:generated"  # Observation -> Plan (on proposal); Actuation -> Receipt
QUAL_USED = "prov:used"  # Permission/Prohibition -> Plan; Actuation -> Plan
QUAL_ASSIGNEE = "odrl:assignee"  # Permission/Prohibition -> Equipment
QUAL_ACTS_ON = "sosa:actsOnProperty"  # Actuation -> Equipment


@dataclass
class LogRef:
    """A mutable box around the current immutable :class:`OcelLog`.

    ``OcelLog`` is frozen: every append returns a new value. ``LogRef`` is
    the one piece of shared mutable state the contract allows, so three
    independent modules can each append into what is, from the outside,
    "the same log".
    """

    log: OcelLog = field(default_factory=OcelLog.new)


def new_log_ref() -> LogRef:
    """Construct a fresh, empty :class:`LogRef`. Call once per run."""
    return LogRef()


def declare_equipment(
    ref: LogRef, resource_id: str, duration_min: float, energy_kwh: float
) -> None:
    """Declare one ``ProductionEquipment`` object. Call once per resource,
    before round 0."""
    obj = OcelObject(
        id=resource_id,
        object_type=OBJ_EQUIPMENT,
        attributes=(
            OcelAttribute("duration_min", OcelAttributeValue.floating(duration_min)),
            OcelAttribute("energy_kwh", OcelAttributeValue.floating(energy_kwh)),
        ),
    )
    ref.log = ref.log.with_objects(obj)


def record_observation(
    ref: LogRef,
    event_id: str,
    resource_id: str,
    timestamp_ns: int,
    uptime_fraction: float,
    below_target: bool,
    plan_object_id: str | None,
) -> None:
    """Append one ``sosa:Observation`` event.

    If ``plan_object_id`` is given (i.e. a proposal was generated this
    round), also declares the ``prov:Plan`` object and links it with
    ``QUAL_GENERATED``.
    """
    links: list = [(resource_id, QUAL_HAS_FEATURE_OF_INTEREST)]
    if plan_object_id is not None:
        ref.log = ref.log.with_objects(
            OcelObject(id=plan_object_id, object_type=OBJ_PLAN, attributes=())
        )
        links.append((plan_object_id, QUAL_GENERATED))
    ref.log = ref.log.append_event(
        event_id,
        EVT_OBSERVATION,
        links,
        timestamp_ns=timestamp_ns,
        attributes={
            "uptime_fraction": OcelAttributeValue.floating(uptime_fraction),
            "below_target": OcelAttributeValue.boolean(below_target),
        },
    )


def record_authority_decision(
    ref: LogRef,
    event_id: str,
    proposal_id: str,
    resource_id: str,
    timestamp_ns: int,
    verdict: str,
    granted_energy_kwh: float,
    remaining_budget_kwh: float,
    reason: str,
) -> None:
    """Append one ``odrl:Permission`` (``verdict == "admitted"``) or
    ``odrl:Prohibition`` (otherwise) event, linked to the Plan and the
    Equipment."""
    activity = EVT_PERMISSION if verdict == "admitted" else EVT_PROHIBITION
    ref.log = ref.log.append_event(
        event_id,
        activity,
        [(proposal_id, QUAL_USED), (resource_id, QUAL_ASSIGNEE)],
        timestamp_ns=timestamp_ns,
        attributes={
            "verdict": OcelAttributeValue.string(verdict),
            "granted_energy_kwh": OcelAttributeValue.floating(granted_energy_kwh),
            "remaining_budget_kwh": OcelAttributeValue.floating(remaining_budget_kwh),
            "reason": OcelAttributeValue.string(reason),
        },
    )


def record_actuation(
    ref: LogRef,
    event_id: str,
    proposal_id: str,
    receipt_id: str,
    resource_id: str,
    timestamp_ns: int,
    applied: bool,
    pre_state_hash: str,
    post_state_hash: str,
) -> None:
    """Append one ``sosa:Actuation`` event for EVERY decision (admitted or
    refused). Always declares a new ``Receipt`` object carrying the pre/post
    state hashes, linked ``QUAL_GENERATED`` from the actuation."""
    ref.log = ref.log.with_objects(
        OcelObject(
            id=receipt_id,
            object_type=OBJ_RECEIPT,
            attributes=(
                OcelAttribute("pre_state_hash", OcelAttributeValue.string(pre_state_hash)),
                OcelAttribute("post_state_hash", OcelAttributeValue.string(post_state_hash)),
                OcelAttribute("applied", OcelAttributeValue.boolean(applied)),
            ),
        )
    )
    ref.log = ref.log.append_event(
        event_id,
        EVT_ACTUATION,
        [
            (resource_id, QUAL_ACTS_ON),
            (proposal_id, QUAL_USED),
            (receipt_id, QUAL_GENERATED),
        ],
        timestamp_ns=timestamp_ns,
        attributes={"applied": OcelAttributeValue.boolean(applied)},
    )


def validate_and_digest(ref: LogRef) -> str:
    """Run ``OcelLog.validate()`` (raises ``OcelError`` on any structural
    defect) and return ``OcelLog.digest()``. Call once, at the end of the
    run."""
    ref.log.validate()
    return ref.log.digest()


def write_json(ref: LogRef, path: str) -> None:
    """Write the current log's OCEL 2.0 JSON interchange projection to
    ``path``."""
    Path(path).write_text(json.dumps(ref.log.to_ocel2_json(), indent=2, sort_keys=True))
