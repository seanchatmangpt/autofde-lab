from autofde_lab.ptd_exp.disclosure import *
def test_disclosure():
 assert frontier([Disclosure("buyer",1,.1),Disclosure("attacker",.5,.9)])[0].name=="buyer"
