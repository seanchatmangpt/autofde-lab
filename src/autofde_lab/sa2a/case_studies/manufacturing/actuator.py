"""actuator.py — Independent Actuator/BRCE component for sa2a-mfg-01.

Role (per CONTRACT.md §3.3, §4): the only module permitted to mutate
``ResourceState.uptime_fraction``. Applies admitted AuthorityDecisions to
plant state, refuses admitted-but-invalid ones defensively (an admitted
decision whose granted energy or resource identity doesn't actually check
out is refused rather than blindly applied), and records every attempt —
success or failure — as a real ``sosa:Actuation`` OCEL event plus a new
Receipt object carrying pre/post-state hashes, via ``ocel_adapter``.

This is a pure per-round function of the state and messages it is given.
It holds no notion of "last round" or global stopping — that is
``runtime.py``'s job (CONTRACT.md §2 step 5). Nothing here hardcodes a
scenario, a seed, or a fixed sequence of decisions: every round's mutation
is a deterministic function of the *decisions* and *proposals* passed in,
which vary by seed and by how many rounds have already elapsed, so this
logic must generalize across arbitrarily many rounds/seeds/plant states,
never assuming a specific one.

Only shared import allowed across builder modules, per contract: ocel_adapter.
"""
from __future__ import annotations

import copy
import hashlib
import json

from autofde_lab.sa2a.case_studies.manufacturing.ocel_adapter import (
    LogRef,
    record_actuation,
)

# ── domain constants (CONTRACT.md §0) — every module hard-codes these
#    identically; not re-derived from another builder's module ────────────
BASELINE = {
    "M1": {"duration_min": 20.0, "energy_kwh": 100.0},
    "M2": {"duration_min": 18.0, "energy_kwh": 110.0},
    "M3": {"duration_min": 15.0, "energy_kwh": 120.0},
    "M4": {"duration_min": 17.0, "energy_kwh": 115.0},
}
RESOURCE_IDS = ("M1", "M2", "M3", "M4")
ENERGY_BUDGET_PER_ROUND_KWH = 450.0
UPTIME_TARGET = 0.50
ADJUSTMENT_ENERGY_FRACTION = 0.5
ADJUSTMENT_UPTIME_GAIN = 0.15
AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET = 0.5

_VALID_VERDICTS = ("admitted", "refused_budget", "refused_authority")


def _canonical_state_hash(state: dict) -> str:
    """SHA-256 hex digest of the canonical JSON of one ResourceState dict.

    Per CONTRACT.md §5: sorted keys, no whitespace.
    """
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Actuator:
    """Owns and mutates plant ``ResourceState``. See CONTRACT.md §3.3.

    ``initial_state`` is ``{resource_id: ResourceState}`` (§1.5).
    ``log_ref`` is the single shared ``ocel_adapter.LogRef`` constructed
    once by ``runtime.py`` and passed by reference (§4).
    """

    def __init__(self, initial_state: dict, log_ref: LogRef) -> None:
        # Deep-copy so this instance owns an independent mutable state
        # dict — never aliases the caller's dict, which would let a
        # module other than Actuator mutate uptime_fraction indirectly.
        self._state: dict = copy.deepcopy(initial_state)
        self._log_ref = log_ref
        # In-round emission counter combined with round_index to derive
        # timestamp_ns per CONTRACT.md §5's monotonic clock rule. Not
        # reset across rounds is unnecessary here because the contract's
        # formula (r * 1_000_000 + k) already makes each round's k-space
        # disjoint from every other round's, as long as k stays bounded
        # by 1_000_000 events per round (true for this domain: at most 4
        # actuations per round).
        self._event_seq: int = 0

    def snapshot(self) -> dict:
        """Return a deep copy of the current {resource_id: ResourceState}."""
        return copy.deepcopy(self._state)

    def _validate_decision(self, decision: dict, proposal: dict | None) -> str | None:
        """Defensive re-check of an incoming AuthorityDecision.

        Returns None if the decision is internally consistent enough to
        act on (per its own verdict), or a short reason string if it is
        admitted-but-invalid and must be refused here instead of blindly
        applied. This is the "refuses admitted-but-invalid ones" half of
        this component's role: an Actuator that trusted every incoming
        'admitted' verdict unconditionally would not be an independent
        check, it would just be a relay.
        """
        verdict = decision.get("verdict")
        if verdict not in _VALID_VERDICTS:
            return f"unknown verdict {verdict!r}"

        resource_id = decision.get("resource_id")
        if resource_id not in self._state:
            return f"unknown resource_id {resource_id!r} not in plant state"

        if verdict != "admitted":
            # Nothing further to validate for a refusal; the decision's
            # own reason already explains why, and no mutation follows.
            return None

        # verdict == "admitted": re-derive what SHOULD have been granted
        # from the matching proposal and cross-check the authority's own
        # arithmetic before trusting it enough to mutate live state.
        if proposal is None:
            return (
                f"admitted decision for proposal_id="
                f"{decision.get('proposal_id')!r} has no matching proposal "
                "in proposals_by_id"
            )
        if proposal.get("resource_id") != resource_id:
            return (
                "admitted decision resource_id does not match its "
                "proposal's resource_id"
            )
        granted = decision.get("granted_energy_kwh")
        requested = proposal.get("requested_energy_kwh")
        if granted is None or requested is None or granted != requested:
            return (
                f"admitted grant {granted} does not equal the proposal's "
                f"requested_energy_kwh {requested}"
            )
        expected_requested = (
            BASELINE.get(resource_id, {}).get("energy_kwh", 0.0)
            * ADJUSTMENT_ENERGY_FRACTION
        )
        if requested != expected_requested:
            return (
                f"proposal requested_energy_kwh {requested} does not match "
                f"the domain rule {expected_requested} for {resource_id}"
            )
        return None

    def apply_round(
        self,
        round_index: int,
        decisions: list,
        proposals_by_id: dict,
    ) -> list:
        """Apply every AuthorityDecision in order (CONTRACT.md §2 step 3).

        For EVERY decision (admitted, refused, or admitted-but-invalid),
        exactly one sosa:Actuation OCEL event and one new Receipt are
        recorded — success or failure alike. Nothing here assumes a fixed
        number, order, or content of decisions beyond the order it is
        given; the same code path handles 0 decisions, 4 decisions, or a
        seed-dependent mix of admitted/refused across arbitrarily many
        rounds.
        """
        results: list = []

        for decision in decisions:
            proposal_id = decision.get("proposal_id")
            resource_id = decision.get("resource_id")
            proposal = proposals_by_id.get(proposal_id)

            resource_state = self._state.get(resource_id)
            if resource_state is None:
                # Unknown resource: nothing to hash/mutate meaningfully,
                # but the contract requires an actuation record for
                # every decision, so record a refusal against a stable
                # empty-state hash rather than crashing the round.
                resource_state = {
                    "resource_id": resource_id,
                    "duration_min": 0.0,
                    "energy_kwh": 0.0,
                    "uptime_fraction": 0.0,
                }

            pre_state_hash = _canonical_state_hash(resource_state)

            invalid_reason = self._validate_decision(decision, proposal)
            can_apply = decision.get("verdict") == "admitted" and invalid_reason is None

            if can_apply:
                gain = proposal["expected_uptime_gain"]
                new_uptime = min(1.0, resource_state["uptime_fraction"] + gain)
                resource_state = dict(resource_state)
                resource_state["uptime_fraction"] = new_uptime
                self._state[resource_id] = resource_state
                post_state_hash = _canonical_state_hash(resource_state)
                applied = True
                new_uptime_fraction: float | None = new_uptime
            else:
                post_state_hash = pre_state_hash
                applied = False
                new_uptime_fraction = None

            receipt_id = f"receipt-{proposal_id}"
            timestamp_ns = round_index * 1_000_000 + self._event_seq
            self._event_seq += 1

            record_actuation(
                self._log_ref,
                event_id=f"evt-actuation-{proposal_id}",
                proposal_id=proposal_id,
                receipt_id=receipt_id,
                resource_id=resource_id,
                timestamp_ns=timestamp_ns,
                applied=applied,
                pre_state_hash=pre_state_hash,
                post_state_hash=post_state_hash,
            )

            results.append(
                {
                    "proposal_id": proposal_id,
                    "resource_id": resource_id,
                    "round_index": round_index,
                    "receipt_id": receipt_id,
                    "applied": applied,
                    "pre_state_hash": pre_state_hash,
                    "post_state_hash": post_state_hash,
                    "new_uptime_fraction": new_uptime_fraction,
                    "timestamp_ns": timestamp_ns,
                }
            )

        return results
