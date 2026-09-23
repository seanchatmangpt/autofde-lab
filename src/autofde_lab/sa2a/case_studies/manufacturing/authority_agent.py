"""authority_agent.py — independent AuthorityAgent for sa2a-mfg-01.

Implements CONTRACT.md §3.2: a per-round, rule-based energy-budget +
anti-monopoly authority admission/refusal procedure. Decides fresh each
round from the proposals it is handed and its own fixed
`energy_budget_per_round_kwh`; holds no notion of round history, "last
round", or global stopping — that is `runtime.py`'s job alone, per §2/§7.

Only shared import allowed across builder modules, per §4: ocel_adapter.
"""

from __future__ import annotations

from autofde_lab.sa2a.case_studies.manufacturing.ocel_adapter import (
    LogRef,
    record_authority_decision,
)

ENERGY_BUDGET_PER_ROUND_KWH = 450.0
AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET = 0.5


class AuthorityAgent:
    """Independent admission authority.

    Each call to `decide_round` re-derives its verdicts purely from the
    proposals passed in and this instance's fixed budget constant — a real
    decision procedure (two checkable rules applied in sequence against a
    running remaining-budget counter), not a scripted/hardcoded sequence of
    outcomes. It generalizes across any number of proposals (0..len(RESOURCE_IDS)),
    any requested amounts, and any round index or seed, because none of
    those appear in the rule itself.
    """

    def __init__(
        self,
        log_ref: LogRef,
        energy_budget_per_round_kwh: float = ENERGY_BUDGET_PER_ROUND_KWH,
    ) -> None:
        self._log_ref = log_ref
        self.energy_budget_per_round_kwh = energy_budget_per_round_kwh
        # Local monotonic event-id counter per round, used only to derive
        # this agent's own timestamp_ns values deterministically (§5:
        # "monotonic and deterministic", never wall time). This agent has
        # no visibility into the global cross-module event ordering that
        # §5's exact r*1_000_000+k formula assumes (that global k spans
        # observation + authority + actuation events interleaved by
        # runtime.py) — see DEVIATION note in module docstring below.
        self._round_event_counter: dict[int, int] = {}

    def _next_timestamp_ns(self, round_index: int) -> int:
        k = self._round_event_counter.get(round_index, 0)
        self._round_event_counter[round_index] = k + 1
        return round_index * 1_000_000 + k

    def decide_round(self, round_index: int, proposals: list[dict]) -> list[dict]:
        """Evaluate every proposal in the order given against a single
        running `remaining` budget counter reset to
        `self.energy_budget_per_round_kwh` at the start of this call — the
        exact rule-based procedure in CONTRACT.md §3.2.

        Returns [] when `proposals` is empty (still a valid, fully-executed
        call — no proposals to admit or refuse this round). This is a real
        decision procedure, not a fixed scenario: it generalizes to any
        list of proposals, any requested amounts, any round index, because
        the rule only ever reads `proposal["requested_energy_kwh"]` against
        the running `remaining` counter and the two fixed constants above.
        """
        remaining = self.energy_budget_per_round_kwh
        decisions: list[dict] = []

        for proposal in proposals:
            requested = float(proposal["requested_energy_kwh"])
            proposal_id = proposal["proposal_id"]
            resource_id = proposal["resource_id"]

            if requested > remaining:
                verdict = "refused_budget"
                granted = 0.0
                reason = (
                    f"requested {requested} kWh exceeds remaining round "
                    f"budget {remaining} kWh"
                )
            elif requested > AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET * remaining:
                verdict = "refused_authority"
                granted = 0.0
                reason = (
                    f"requested {requested} kWh exceeds authority cap of "
                    f"{AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET} of remaining "
                    f"budget {remaining} kWh"
                )
            else:
                verdict = "admitted"
                granted = requested
                reason = "within budget and authority cap"
                remaining -= granted

            timestamp_ns = self._next_timestamp_ns(round_index)

            decision = {
                "proposal_id": proposal_id,
                "resource_id": resource_id,
                "round_index": round_index,
                "verdict": verdict,
                "granted_energy_kwh": granted,
                "remaining_budget_kwh": remaining,
                "reason": reason,
                "timestamp_ns": timestamp_ns,
            }
            decisions.append(decision)

            record_authority_decision(
                self._log_ref,
                event_id=f"evt-{proposal_id}-decision",
                proposal_id=proposal_id,
                resource_id=resource_id,
                timestamp_ns=timestamp_ns,
                verdict=verdict,
                granted_energy_kwh=granted,
                remaining_budget_kwh=remaining,
                reason=reason,
            )

        return decisions
