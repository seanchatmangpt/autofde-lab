from autofde_lab.ptd_exp.replay import *
def test_replay():
 assert replay_key("s","x",["1","2"])==replay_key("s","x",["1","2"])
