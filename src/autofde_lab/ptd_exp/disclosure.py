from dataclasses import dataclass
@dataclass(frozen=True)
class Disclosure: name:str; buyer_utility:float; attacker_utility:float
def disclosure_score(x,w=1.): return x.buyer_utility-w*x.attacker_utility
def frontier(items,w=1.): return sorted(items,key=lambda x:(disclosure_score(x,w),x.name),reverse=True)
