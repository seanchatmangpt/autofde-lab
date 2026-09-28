def regeneration_advantage(attacker_cost,defender_cost):
 if defender_cost<=0 or attacker_cost<0: raise ValueError("invalid cost")
 return attacker_cost/defender_cost
def ptd_efficiency(dep,defender_cost): return dep/defender_cost
def ptd_advantage(dep,attacker_cost,defender_cost): return dep*regeneration_advantage(attacker_cost,defender_cost)
