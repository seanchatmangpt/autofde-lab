from autofde_lab.ptd_exp.common_mode import *
def test_common_mode():
 assert common_mode_persistence({"a","b"},{"b","c"})==.5
