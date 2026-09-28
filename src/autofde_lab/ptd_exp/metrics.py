from .transfer import knowledge_depreciation
from .economics import regeneration_advantage,ptd_efficiency,ptd_advantage
def metric_bundle(stale,fresh,attacker_cost,defender_cost):
 d=knowledge_depreciation(stale,fresh); return {"knowledge_depreciation":d,"regeneration_advantage":regeneration_advantage(attacker_cost,defender_cost),"ptd_efficiency":ptd_efficiency(d,defender_cost),"ptd_advantage":ptd_advantage(d,attacker_cost,defender_cost)}
