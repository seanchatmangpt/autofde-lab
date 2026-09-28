from autofde_lab.ptd_exp.metrics import metric_bundle
def test_metrics():
 r=metric_bundle(1,2,10,2); assert r["knowledge_depreciation"]==.5 and r["regeneration_advantage"]==5
