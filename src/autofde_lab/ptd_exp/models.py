from dataclasses import dataclass
@dataclass(frozen=True)
class EpochObservation:
 subject_id:str; epoch_id:str; semantic_digest:str; realization_digest:str; defender_cost:float; phase_duration:float; admitted:bool=True
@dataclass(frozen=True)
class AttackObservation:
 task_id:str; source_epoch:str; target_epoch:str; stale_performance:float; fresh_performance:float; realignment_cost:float; realignment_time:float
@dataclass(frozen=True)
class PTDThresholds:
 max_retention:float=.5; min_regeneration_advantage:float=1.; require_temporal_advantage:bool=False
