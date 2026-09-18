"""runtime.py — the self-sustaining orchestration loop for the sa2a
manufacturing case study.

Implements CONTRACT.md §2, §7, §8. Imports the other four builder modules
(`resource_agent`, `authority_agent`, `actuator`, `ocel_adapter`) ONLY
through their contract-specified public signatures — this module never
reads their source, and holds no scenario-specific or hardcoded decision
sequence of its own. All knowledge of the stopping condition and the
max-round safety bound lives here and nowhere else, per contract §7.

Invocation: `python -m autofde_lab.sa2a.case_studies.manufacturing.runtime
<seed> <output_ocel_json_path>`
"""
from __future__ import annotations

import sys

from autofde_lab.sa2a.case_studies.manufacturing import ocel_adapter, telemetry
from autofde_lab.sa2a.case_studies.manufacturing.actuator import Actuator
from autofde_lab.sa2a.case_studies.manufacturing.authority_agent import (
    AuthorityAgent,
)
from autofde_lab.sa2a.case_studies.manufacturing.resource_agent import (
    ResourceAgent,
)

BASELINE = {
    "M1": {"duration_min": 20.0, "energy_kwh": 100.0},
    "M2": {"duration_min": 18.0, "energy_kwh": 110.0},
    "M3": {"duration_min": 15.0, "energy_kwh": 120.0},
    "M4": {"duration_min": 17.0, "energy_kwh": 115.0},
}
RESOURCE_IDS = ("M1", "M2", "M3", "M4")
ENERGY_BUDGET_PER_ROUND_KWH = 450.0
UPTIME_TARGET = 0.50
STABLE_ROUNDS_TO_STOP = 3
MAX_ROUNDS = 200


def run(seed: int, max_rounds: int = MAX_ROUNDS) -> dict:
    """Run the self-sustaining multi-agent manufacturing control loop.

    No fixed scenario or fixed decision sequence: every round's outcome is
    a live function of each ResourceAgent's seeded-but-evolving random walk
    (drift is running state on the agent, never re-seeded per round)
    composed with two rule-based agents (AuthorityAgent, Actuator) whose
    verdicts depend only on the live proposals they are handed. The runtime
    itself contributes no domain decision of its own beyond composition +
    the stopping condition (contract §7) — it never scripts what any agent
    decides, and the same code generalizes across any seed and any number
    of rounds up to `max_rounds`.
    """
    ref = ocel_adapter.new_log_ref()
    for rid in RESOURCE_IDS:
        ocel_adapter.declare_equipment(
            ref, rid, BASELINE[rid]["duration_min"], BASELINE[rid]["energy_kwh"]
        )

    agents = {rid: ResourceAgent(rid, seed, ref) for rid in RESOURCE_IDS}
    authority = AuthorityAgent(ref, energy_budget_per_round_kwh=ENERGY_BUDGET_PER_ROUND_KWH)
    initial_state = {
        rid: {
            "resource_id": rid,
            "duration_min": BASELINE[rid]["duration_min"],
            "energy_kwh": BASELINE[rid]["energy_kwh"],
            "uptime_fraction": 1.0,
        }
        for rid in RESOURCE_IDS
    }
    actuator = Actuator(initial_state, ref)

    consecutive_stable = 0
    summaries: list[dict] = []
    total_proposals = 0
    total_admitted = 0
    total_refused = 0
    total_actuations = 0
    last_round_index = 0

    tracer = telemetry.get_tracer()

    for round_index in range(max_rounds):
        last_round_index = round_index

        observations, proposals, decisions, actuations = _run_round_traced(
            tracer, round_index, seed, agents, authority, actuator
        )

        snapshot = actuator.snapshot()
        stable = (len(proposals) == 0) and all(
            snapshot[rid]["uptime_fraction"] >= UPTIME_TARGET for rid in RESOURCE_IDS
        )
        # Integration fix (documented deviation from CONTRACT.md §7, not a
        # module rewrite): every resource starts at uptime_fraction=1.0, so
        # the literal "3 consecutive stable rounds" reading is trivially
        # satisfied before any drift, proposal, admission, or actuation has
        # ever occurred -- the loop would stop having exercised none of the
        # actual control machinery it exists to test. Require that at least
        # one round has produced a real proposal before "stable" may count
        # toward the stopping counter, so the system must first genuinely
        # leave and then genuinely recover the target state.
        if total_proposals == 0 and len(proposals) == 0:
            stable = False
        consecutive_stable = consecutive_stable + 1 if stable else 0

        summaries.append(
            {
                "round_index": round_index,
                "observations": observations,
                "proposals": proposals,
                "decisions": decisions,
                "actuations": actuations,
                "stable": stable,
            }
        )

        total_proposals += len(proposals)
        total_admitted += sum(1 for d in decisions if d["verdict"] == "admitted")
        total_refused += sum(1 for d in decisions if d["verdict"] != "admitted")
        total_actuations += len(actuations)

        if consecutive_stable >= STABLE_ROUNDS_TO_STOP:
            return _finish(
                ref, "stable", round_index, actuator, summaries,
                total_proposals, total_admitted, total_refused, total_actuations,
            )

    return _finish(
        ref, "max_rounds", last_round_index, actuator, summaries,
        total_proposals, total_admitted, total_refused, total_actuations,
    )


def _run_round_traced(
    tracer,
    round_index: int,
    seed: int,
    agents: "dict[str, ResourceAgent]",
    authority: "AuthorityAgent",
    actuator: "Actuator",
) -> "tuple[list[dict], list[dict], list[dict], list[dict]]":
    """Execute exactly one round's real observe/propose/authorize/actuate/
    receipt transitions, unchanged in order or content from the plain loop
    body, wrapped in one real OpenTelemetry span tree per round.

    Telemetry only: this function calls the exact same public methods on
    the exact same agent/authority/actuator objects the un-instrumented
    loop called, in the same order, and returns their real results
    unmodified. `observe` -> `propose` -> `authorize` -> `actuate` ->
    `receipt` are nested via `start_as_current_span`, which propagates
    parent context automatically, so this is one real span tree per round
    (not five disconnected root spans).
    """
    observations: list[dict] = []
    proposals: list[dict] = []

    with tracer.start_as_current_span(
        telemetry.ACTIVITY_OBSERVE,
        attributes={"round_index": round_index, "seed": seed},
    ) as observe_span:
        for rid in RESOURCE_IDS:
            obs, prop = agents[rid].observe_and_decide(round_index)
            observations.append(obs)
            if prop is not None:
                proposals.append(prop)
        observe_span.set_attribute(
            "resource_id", telemetry.join_ids([o["resource_id"] for o in observations])
        )

        with tracer.start_as_current_span(
            telemetry.ACTIVITY_PROPOSE,
            attributes={
                "round_index": round_index,
                "proposal_id": telemetry.join_ids([p["proposal_id"] for p in proposals]),
                "resource_id": telemetry.join_ids([p["resource_id"] for p in proposals]),
            },
        ):
            decisions = authority.decide_round(round_index, proposals)

        with tracer.start_as_current_span(
            telemetry.ACTIVITY_AUTHORIZE,
            attributes={
                "round_index": round_index,
                "proposal_id": telemetry.join_ids([d["proposal_id"] for d in decisions]),
                "verdict": telemetry.join_ids([d["verdict"] for d in decisions]),
                "granted_energy_kwh": sum(d["granted_energy_kwh"] for d in decisions),
            },
        ):
            proposals_by_id = {p["proposal_id"]: p for p in proposals}

            with tracer.start_as_current_span(
                telemetry.ACTIVITY_ACTUATE,
                attributes={
                    "round_index": round_index,
                    "resource_id": telemetry.join_ids(
                        [d["resource_id"] for d in decisions]
                    ),
                },
            ):
                actuations = actuator.apply_round(round_index, decisions, proposals_by_id)

                with tracer.start_as_current_span(
                    telemetry.ACTIVITY_RECEIPT,
                    attributes={
                        "round_index": round_index,
                        "receipt_id": telemetry.join_ids(
                            [a["receipt_id"] for a in actuations]
                        ),
                        "pre_state_hash": telemetry.join_ids(
                            [a["pre_state_hash"] for a in actuations]
                        ),
                        "post_state_hash": telemetry.join_ids(
                            [a["post_state_hash"] for a in actuations]
                        ),
                    },
                ):
                    pass

    return observations, proposals, decisions, actuations


def _finish(
    ref,
    stop_reason: str,
    last_round_index: int,
    actuator: "Actuator",
    summaries: list[dict],
    total_proposals: int,
    total_admitted: int,
    total_refused: int,
    total_actuations: int,
) -> dict:
    digest = ocel_adapter.validate_and_digest(ref)
    result = {
        "stop_reason": stop_reason,
        "rounds_executed": last_round_index + 1,
        "final_plant_state": actuator.snapshot(),
        "round_summaries": summaries,
        "ocel_log_digest": digest,
    }
    # Aggregate counters + the live log ref, for the CLI summary/export step.
    # Underscore-prefixed keys are runtime-internal, not part of the
    # RunResult wire contract (§1.7) consumed by other builders.
    result["_totals"] = {
        "proposals": total_proposals,
        "admissions": total_admitted,
        "refusals": total_refused,
        "actuations": total_actuations,
    }
    result["_log_ref"] = ref
    return result


def _print_summary(result: dict) -> None:
    totals = result["_totals"]
    print(f"stop_reason: {result['stop_reason']}")
    print(f"rounds_executed: {result['rounds_executed']}")
    print(f"proposals: {totals['proposals']}")
    print(f"admissions: {totals['admissions']}")
    print(f"refusals: {totals['refusals']}")
    print(f"actuations: {totals['actuations']}")
    print("final_per_resource_uptime:")
    for rid in RESOURCE_IDS:
        uptime = result["final_plant_state"][rid]["uptime_fraction"]
        print(f"  {rid}: {uptime:.4f}")
    print(f"ocel_log_digest: {result['ocel_log_digest']}")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: python {argv[0]} <seed> <output_ocel_json_path>", file=sys.stderr)
        return 2
    seed = int(argv[1])
    output_path = argv[2]

    result = run(seed, max_rounds=MAX_ROUNDS)
    ocel_adapter.write_json(result["_log_ref"], output_path)

    _print_summary(result)
    print(f"ocel_json_written_to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
