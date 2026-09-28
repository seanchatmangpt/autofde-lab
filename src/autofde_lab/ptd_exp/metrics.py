from .economics import ptd_advantage, ptd_efficiency, regeneration_advantage
from .transfer import knowledge_depreciation


def metric_bundle(stale, fresh, attacker_cost, defender_cost):
    d = knowledge_depreciation(stale, fresh)
    return {
        "knowledge_depreciation": d,
        "regeneration_advantage": regeneration_advantage(attacker_cost, defender_cost),
        "ptd_efficiency": ptd_efficiency(d, defender_cost),
        "ptd_advantage": ptd_advantage(d, attacker_cost, defender_cost),
    }
