"""verifier.py -- independent VerifierAgent for the sa2a manufacturing case study.

Role (per the harness assignment; VerifierAgent is not one of the modules
CONTRACT.md Section 4 enumerates, so its exact public surface is not fixed
by the contract -- the interpretation below is the deviation, reported
explicitly rather than guessed silently, see "Deviations" at the bottom of
this docstring): an independent auditor that re-derives, purely from the
shared OCEL log's own recorded events/objects/links (via `ocel_adapter`'s
`LogRef`), whether three per-round invariants held. It never reads
`ResourceAgent`/`AuthorityAgent`/`Actuator`/`runtime` in-memory state and
never imports those modules -- only `ocel_adapter`, matching Section 4's
"every builder module imports only stdlib + ocel_adapter" rule.

The three invariants, each independently re-derived from log data:

1. **Zero unreceipted actuation.** Every `sosa:Actuation` event carries
   exactly one `prov:generated` link to a `Receipt` object that actually
   exists in the log's object table, and that receipt's `applied` flag
   agrees with the event's `applied` attribute; when not applied,
   `pre_state_hash == post_state_hash` on the receipt.

2. **energy <= 450 kWh per round.** The sum of `granted_energy_kwh` over
   every `odrl:Permission` event in a round never exceeds
   `ENERGY_BUDGET_PER_ROUND_KWH`, and the running `remaining_budget_kwh`
   the authority agent recorded on each decision never goes negative.

3. **Authority closure.** Replaying the round's `odrl:Permission` /
   `odrl:Prohibition` events in emission order, the recorded
   `remaining_budget_kwh` chain is internally consistent (each decision's
   remaining-after equals the previous decision's remaining-after, minus
   this decision's own grant), every `admitted` grant respects the
   anti-monopoly cap (`granted <= AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET *
   remaining_before`), and every `refused_authority` / `refused_budget`
   verdict is justified by the *requested* amount the authority agent
   itself wrote into that event's `reason` string.

This is a real, general decision procedure over whatever a log contains --
it makes no assumption about how many rounds ran, what seed produced them,
or what the plant state was; it walks the log's own event/object tables and
recomputes the same rules `authority_agent.py` is specified to apply,
independently, from data alone.

Deviations from a literal reading of CONTRACT.md
--------------------------------------------------
1. **Public signature.** Section 4's table does not list `verifier.py`.
   Modeled on the same shape every other builder module uses -- a class
   constructed with the shared `LogRef` (`VerifierAgent(log_ref)`), plus a
   `verify_round(round_index)` and a `verify_run()` convenience that walks
   every round the log actually contains. This lets `runtime.py` call it
   once per round (a real per-round invariant check, as asked) or a
   standalone script call it once at the end against a completed log --
   both are "purely reading back OCEL log state", neither requires
   `verifier.py` to be threaded into the fixed four-module composition in
   Section 8, so it does not require changing `runtime.py`.
2. **Authority closure without a stored `requested_energy_kwh`.** The OCEL
   event Section 6 records for a decision (`record_authority_decision`)
   never attaches `requested_energy_kwh` as a structured attribute -- only
   `verdict`, `granted_energy_kwh`, `remaining_budget_kwh`, and a free-text
   `reason`. `authority_agent.py`'s own reason strings (Section 3.2) are
   generated from an f-string that names the exact requested and remaining
   figures verbatim, so the requested amount *is* present in the durable
   log, just not as a typed field. This verifier parses it back out of
   `reason` with a fixed regex tied to the exact wording Section 3.2
   specifies. This is reading the log, not trusting another component's
   live claim -- the string was itself committed to the append-only log at
   decision time -- but it is a real interpretive choice worth naming
   rather than silently assuming; a more robust contract would carry
   `requested_energy_kwh` as its own OCEL event attribute so a verifier
   never has to parse prose. If the reason text does not match either
   pattern (e.g. a future authority_agent implementation rewords its
   messages), the closure check for that one decision degrades to
   `"unparseable_reason"` rather than crashing or silently passing.
2. **Round windowing.** No wire message tags an event with which round's
   "phase" produced it beyond the timestamp -- this verifier recovers
   `round_index` from `timestamp_ns // 1_000_000`, exactly the clock rule
   Section 5 defines, rather than requiring the caller to also pass
   per-round event lists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from autofde_lab.sa2a.case_studies.manufacturing.ocel_adapter import (
    EVT_ACTUATION,
    EVT_PERMISSION,
    EVT_PROHIBITION,
    OBJ_RECEIPT,
    QUAL_GENERATED,
    LogRef,
)

ENERGY_BUDGET_PER_ROUND_KWH = 450.0
AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET = 0.5
ROUND_NS = 1_000_000  # timestamp_ns = round_index * ROUND_NS + emission_k, per CONTRACT.md Section 5

_TOLERANCE = 1e-6

_REFUSED_BUDGET_RE = re.compile(
    r"requested ([0-9.eE+\-]+) kWh exceeds remaining round budget ([0-9.eE+\-]+) kWh"
)
_REFUSED_AUTHORITY_RE = re.compile(
    r"requested ([0-9.eE+\-]+) kWh exceeds authority cap of ([0-9.eE+\-]+) of "
    r"remaining budget ([0-9.eE+\-]+) kWh"
)


def _attr(event_or_object: Any, key: str, default: Any = None) -> Any:
    """Read one attribute value off a real OcelEvent/OcelObject.

    Reads only the public `.attributes` tuple of `OcelAttribute(key, value)`
    pairs every frozen model in `autofde_lab.ocel.model` already exposes --
    no new accessor is invented.
    """
    for a in event_or_object.attributes:
        if a.key == key:
            return a.value.value
    return default


@dataclass
class RoundViolation:
    round_index: int
    invariant: str  # "unreceipted_actuation" | "energy_budget" | "authority_closure"
    event_id: str | None
    detail: str

    def to_dict(self) -> dict:
        return {
            "round_index": self.round_index,
            "invariant": self.invariant,
            "event_id": self.event_id,
            "detail": self.detail,
        }


@dataclass
class RoundReport:
    round_index: int
    checked_actuations: int = 0
    checked_decisions: int = 0
    total_granted_energy_kwh: float = 0.0
    violations: list[RoundViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.violations) == 0

    def to_dict(self) -> dict:
        return {
            "round_index": self.round_index,
            "ok": self.ok,
            "checked_actuations": self.checked_actuations,
            "checked_decisions": self.checked_decisions,
            "total_granted_energy_kwh": self.total_granted_energy_kwh,
            "violations": [v.to_dict() for v in self.violations],
        }


class VerifierAgent:
    """Independent auditor. Reads only `log_ref.log`'s own events/objects/links.

    Construction mirrors every other sa2a-mfg-01 agent's shape
    (`__init__(self, log_ref, ...)`), so `runtime.py` can hold one alongside
    `ResourceAgent`/`AuthorityAgent`/`Actuator` without importing any of
    them.
    """

    def __init__(
        self,
        log_ref: LogRef,
        energy_budget_per_round_kwh: float = ENERGY_BUDGET_PER_ROUND_KWH,
        authority_max_share: float = AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET,
    ) -> None:
        self._ref = log_ref
        self._budget = energy_budget_per_round_kwh
        self._max_share = authority_max_share

    # -- internal: read-back helpers, never mutate ------------------------

    def _events_for_round(self, round_index: int) -> list:
        lo = round_index * ROUND_NS
        hi = lo + ROUND_NS
        return sorted(
            (e for e in self._ref.log.events if lo <= e.timestamp_ns < hi),
            key=lambda e: e.timestamp_ns,
        )

    def _links_for_event(self, event_id: str) -> list[tuple[str, str | None]]:
        return [
            (link.object_id, link.qualifier)
            for link in self._ref.log.event_object_links
            if link.event_id == event_id
        ]

    def _object(self, object_id: str):
        for obj in self._ref.log.objects:
            if obj.id == object_id:
                return obj
        return None

    def known_round_indices(self) -> list[int]:
        """Every round_index actually present in the log, in order."""
        seen = {e.timestamp_ns // ROUND_NS for e in self._ref.log.events}
        return sorted(seen)

    # -- invariant 1: zero unreceipted actuation ---------------------------

    def _check_actuations(
        self, round_index: int, events: list, report: RoundReport
    ) -> None:
        for ev in events:
            if ev.activity != EVT_ACTUATION:
                continue
            report.checked_actuations += 1
            receipt_links = [
                object_id
                for object_id, qualifier in self._links_for_event(ev.id)
                if qualifier == QUAL_GENERATED
            ]
            if len(receipt_links) != 1:
                report.violations.append(
                    RoundViolation(
                        round_index,
                        "unreceipted_actuation",
                        ev.id,
                        f"expected exactly one {QUAL_GENERATED} receipt link, "
                        f"found {len(receipt_links)}",
                    )
                )
                continue
            receipt = self._object(receipt_links[0])
            if receipt is None or receipt.object_type != OBJ_RECEIPT:
                report.violations.append(
                    RoundViolation(
                        round_index,
                        "unreceipted_actuation",
                        ev.id,
                        f"linked receipt object {receipt_links[0]!r} does not exist "
                        f"in the log's object table as a {OBJ_RECEIPT}",
                    )
                )
                continue
            event_applied = bool(_attr(ev, "applied", False))
            receipt_applied = bool(_attr(receipt, "applied", False))
            if event_applied != receipt_applied:
                report.violations.append(
                    RoundViolation(
                        round_index,
                        "unreceipted_actuation",
                        ev.id,
                        f"event.applied={event_applied} disagrees with "
                        f"receipt.applied={receipt_applied}",
                    )
                )
            if not event_applied:
                pre = _attr(receipt, "pre_state_hash")
                post = _attr(receipt, "post_state_hash")
                if pre != post:
                    report.violations.append(
                        RoundViolation(
                            round_index,
                            "unreceipted_actuation",
                            ev.id,
                            "applied=False but pre_state_hash != post_state_hash "
                            f"({pre!r} != {post!r})",
                        )
                    )

    # -- invariants 2 & 3: energy budget + authority closure --------------

    def _check_decisions(
        self, round_index: int, events: list, report: RoundReport
    ) -> None:
        decisions = [
            ev for ev in events if ev.activity in (EVT_PERMISSION, EVT_PROHIBITION)
        ]
        remaining_before = self._budget
        for ev in decisions:
            report.checked_decisions += 1
            verdict = _attr(ev, "verdict", "")
            granted = float(_attr(ev, "granted_energy_kwh", 0.0))
            remaining_after = float(_attr(ev, "remaining_budget_kwh", remaining_before))
            reason = str(_attr(ev, "reason", ""))

            if remaining_after < -_TOLERANCE:
                report.violations.append(
                    RoundViolation(
                        round_index,
                        "energy_budget",
                        ev.id,
                        f"remaining_budget_kwh went negative: {remaining_after}",
                    )
                )

            if verdict == "admitted":
                report.total_granted_energy_kwh += granted
                if abs(remaining_after - (remaining_before - granted)) > _TOLERANCE:
                    report.violations.append(
                        RoundViolation(
                            round_index,
                            "authority_closure",
                            ev.id,
                            "admitted grant does not close the budget ledger: "
                            f"remaining_before={remaining_before} granted={granted} "
                            f"remaining_after={remaining_after}",
                        )
                    )
                cap = self._max_share * remaining_before
                if granted > cap + _TOLERANCE:
                    report.violations.append(
                        RoundViolation(
                            round_index,
                            "authority_closure",
                            ev.id,
                            f"admitted grant {granted} exceeds anti-monopoly cap {cap} "
                            f"({self._max_share} of remaining_before={remaining_before})",
                        )
                    )
                if granted > remaining_before + _TOLERANCE:
                    report.violations.append(
                        RoundViolation(
                            round_index,
                            "energy_budget",
                            ev.id,
                            f"admitted grant {granted} exceeds remaining_before={remaining_before}",
                        )
                    )
            elif verdict in ("refused_budget", "refused_authority"):
                if granted != 0.0:
                    report.violations.append(
                        RoundViolation(
                            round_index,
                            "authority_closure",
                            ev.id,
                            f"{verdict} but granted_energy_kwh={granted} != 0.0",
                        )
                    )
                if abs(remaining_after - remaining_before) > _TOLERANCE:
                    report.violations.append(
                        RoundViolation(
                            round_index,
                            "authority_closure",
                            ev.id,
                            f"{verdict} must leave the budget unchanged: "
                            f"remaining_before={remaining_before} remaining_after={remaining_after}",
                        )
                    )
                self._check_refusal_justified(
                    round_index, ev, verdict, reason, remaining_before, report
                )
            else:
                report.violations.append(
                    RoundViolation(
                        round_index,
                        "authority_closure",
                        ev.id,
                        f"unknown verdict string {verdict!r} "
                        "(must be admitted/refused_budget/refused_authority)",
                    )
                )

            remaining_before = remaining_after

    def _check_refusal_justified(
        self,
        round_index: int,
        ev,
        verdict: str,
        reason: str,
        remaining_before: float,
        report: RoundReport,
    ) -> None:
        if verdict == "refused_budget":
            m = _REFUSED_BUDGET_RE.search(reason)
            if m is None:
                report.violations.append(
                    RoundViolation(
                        round_index,
                        "authority_closure",
                        ev.id,
                        f"unparseable_reason for refused_budget: {reason!r}",
                    )
                )
                return
            requested = float(m.group(1))
            if requested <= remaining_before + _TOLERANCE:
                report.violations.append(
                    RoundViolation(
                        round_index,
                        "authority_closure",
                        ev.id,
                        f"refused_budget but requested={requested} did not exceed "
                        f"remaining_before={remaining_before}",
                    )
                )
        elif verdict == "refused_authority":
            m = _REFUSED_AUTHORITY_RE.search(reason)
            if m is None:
                report.violations.append(
                    RoundViolation(
                        round_index,
                        "authority_closure",
                        ev.id,
                        f"unparseable_reason for refused_authority: {reason!r}",
                    )
                )
                return
            requested = float(m.group(1))
            cap = self._max_share * remaining_before
            if requested <= cap + _TOLERANCE:
                report.violations.append(
                    RoundViolation(
                        round_index,
                        "authority_closure",
                        ev.id,
                        f"refused_authority but requested={requested} did not exceed "
                        f"cap={cap} (max_share={self._max_share} of remaining_before={remaining_before})",
                    )
                )
            if requested > remaining_before + _TOLERANCE:
                report.violations.append(
                    RoundViolation(
                        round_index,
                        "authority_closure",
                        ev.id,
                        f"refused_authority but requested={requested} also exceeds "
                        f"remaining_before={remaining_before} -- should have been refused_budget",
                    )
                )

    # -- public entry points ------------------------------------------------

    def verify_round(self, round_index: int) -> dict:
        """Re-derive all three invariants for one round, from the log alone."""
        events = self._events_for_round(round_index)
        report = RoundReport(round_index=round_index)
        self._check_actuations(round_index, events, report)
        self._check_decisions(round_index, events, report)
        if report.total_granted_energy_kwh > self._budget + _TOLERANCE:
            report.violations.append(
                RoundViolation(
                    round_index,
                    "energy_budget",
                    None,
                    f"round total granted energy {report.total_granted_energy_kwh} "
                    f"exceeds budget {self._budget}",
                )
            )
        return report.to_dict()

    def verify_run(self) -> dict:
        """Re-derive all three invariants across every round present in the log."""
        round_reports = [self.verify_round(r) for r in self.known_round_indices()]
        all_violations = [v for r in round_reports for v in r["violations"]]
        return {
            "ok": len(all_violations) == 0,
            "rounds_checked": len(round_reports),
            "violations": all_violations,
            "round_reports": round_reports,
        }


__all__ = ["VerifierAgent", "RoundReport", "RoundViolation"]
