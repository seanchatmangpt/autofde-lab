from autofde_lab.ptd_exp.models import *
from autofde_lab.ptd_exp.court import evaluate_epoch_pair
def test_court():
 a=EpochObservation("s","1","sem","r1",1,10); b=EpochObservation("s","2","sem","r2",2,10); x=AttackObservation("q","1","2",1,4,8,20)
 assert evaluate_epoch_pair(a,b,x,PTDThresholds(require_temporal_advantage=True))["admitted"]
