from .epochs import validate_pair
from .transfer import knowledge_retention
from .economics import regeneration_advantage
from .temporal import strong_temporal_regime
def evaluate_epoch_pair(a,b,attack,t):
 validate_pair(a,b)
 if (attack.source_epoch,attack.target_epoch)!=(a.epoch_id,b.epoch_id): raise ValueError("attack epoch binding mismatch")
 retention=knowledge_retention(attack.stale_performance,attack.fresh_performance); ra=regeneration_advantage(attack.realignment_cost,b.defender_cost); failures=[]
 if retention>t.max_retention: failures.append("retention")
 if ra<t.min_regeneration_advantage: failures.append("economics")
 if t.require_temporal_advantage and not strong_temporal_regime(attack.realignment_time,b.phase_duration): failures.append("temporal")
 return {"subject_id":a.subject_id,"source_epoch":a.epoch_id,"target_epoch":b.epoch_id,"retention":retention,"regeneration_advantage":ra,"failures":failures,"admitted":not failures}
def evaluate_campaign(rows): return {"pair_count":len(rows),"admitted_count":sum(bool(r["admitted"]) for r in rows),"failed_count":sum(not bool(r["admitted"]) for r in rows),"all_admitted":all(bool(r["admitted"]) for r in rows)}
