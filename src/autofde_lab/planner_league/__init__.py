"""Role-conditioned planner league public surface."""

import importlib

from .agent_binding import AgentBinding, identity_quadruple, match_from_bindings
from .catalog import (
    ACTION_PROJECTIONS,
    BUDGETS,
    EXPERIMENT_DIMENSIONS,
    NOVELTY_ORACLES,
    OBSERVATION_PROJECTIONS,
    PLANNER_CAPABILITY_FIELDS,
    PRIMARY_PLANNERS,
    ROLE_SPECS,
    WORLD_CLASSES,
)
from .core import (
    CompatibilityResult,
    CompatibilityStanding,
    LeagueMatch,
    MetaSelector,
    NoveltyRequest,
    PayoffHypergraph,
    PayoffObservation,
    PlannerLeague,
    PolicySpec,
)
from .policy_identity import policy_identity, policy_identity_payload, policy_ref
from .psro import PolicySpaceResponseOracle, PsroReceipt, PsroState, PsroStep

# The ecology surface depends on ``gymact.policy_ecology`` / ``gymact.temperament_engineering``,
# which the admitted gymact pin may not provide. Loading it lazily keeps ``psro``, ``core`` and
# ``catalog`` importable on any admitted pin, and turns a missing dependency into an explicit,
# named ImportError (UNSUPPORTED) at first use instead of breaking the whole package at import.
_LAZY_EXPORTS = {
    "heterogeneity_benchmark": (
        "ExpectedPayoff",
        "HeterogeneityBenchmarkCell",
        "HeterogeneityBenchmarkProgram",
        "complete_heterogeneity_trial",
        "expected_payoff",
        "manufacture_heterogeneity_program",
    ),
    "policy_ecology": ("ConditionedPolicy", "PolicyEcology"),
    "policy_ecology_experiment": (
        "EcologyMatch",
        "EcologyParticipant",
        "EcologyPayoffSurface",
        "EcologySchedule",
        "HeterogeneityEvidence",
        "HeterogeneityTrial",
        "ObservedEcologyOutcome",
        "manufacture_ecology_schedule",
        "summarize_heterogeneity",
    ),
    "policy_ecology_sweep": (
        "CueResponsePoint",
        "CueResponseSurface",
        "CueSweep",
        "CueSweepSpec",
        "build_cue_response_surface",
        "manufacture_cue_sweep",
    ),
    "temperament_design_bridge": (
        "DesignBenchmarkPair",
        "DesignedPolicyEcology",
        "manufacture_design_benchmark_pair",
        "manufacture_designed_policy_ecology",
    ),
}
_LAZY_SOURCE = {name: mod for mod, names in _LAZY_EXPORTS.items() for name in names}


def __getattr__(name: str):
    module_name = _LAZY_SOURCE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        module = importlib.import_module(f".{module_name}", __name__)
    except ModuleNotFoundError as error:
        if error.name and error.name.split(".")[0] == "gymact":
            raise ImportError(
                f"{name} requires {error.name}, which the installed gymact does not provide "
                "(UNSUPPORTED until a gymact revision that has it is admitted)"
            ) from error
        raise
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "ACTION_PROJECTIONS",
    "AgentBinding",
    "BUDGETS",
    "ConditionedPolicy",
    "PolicyEcology",
    "EcologyMatch",
    "EcologyParticipant",
    "EcologyPayoffSurface",
    "EcologySchedule",
    "HeterogeneityEvidence",
    "HeterogeneityTrial",
    "ObservedEcologyOutcome",
    "manufacture_ecology_schedule",
    "policy_identity",
    "summarize_heterogeneity",
    "CueResponsePoint",
    "CueResponseSurface",
    "CueSweep",
    "CueSweepSpec",
    "build_cue_response_surface",
    "manufacture_cue_sweep",
    "DesignBenchmarkPair",
    "DesignedPolicyEcology",
    "manufacture_design_benchmark_pair",
    "manufacture_designed_policy_ecology",
    "ExpectedPayoff",
    "HeterogeneityBenchmarkCell",
    "HeterogeneityBenchmarkProgram",
    "complete_heterogeneity_trial",
    "expected_payoff",
    "manufacture_heterogeneity_program",
    "policy_identity_payload",
    "policy_ref",
    "CompatibilityResult",
    "CompatibilityStanding",
    "EXPERIMENT_DIMENSIONS",
    "LeagueMatch",
    "MetaSelector",
    "NOVELTY_ORACLES",
    "NoveltyRequest",
    "OBSERVATION_PROJECTIONS",
    "PLANNER_CAPABILITY_FIELDS",
    "PRIMARY_PLANNERS",
    "PayoffHypergraph",
    "PayoffObservation",
    "PlannerLeague",
    "PolicySpaceResponseOracle",
    "PolicySpec",
    "PsroReceipt",
    "PsroState",
    "PsroStep",
    "ROLE_SPECS",
    "WORLD_CLASSES",
    "identity_quadruple",
    "match_from_bindings",
]
