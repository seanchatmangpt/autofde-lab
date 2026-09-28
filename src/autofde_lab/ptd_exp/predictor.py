def normalized_prediction_error(predicted,actual):
 union=predicted|actual
 return 0. if not union else len(predicted^actual)/len(union)
def attacker_predictability(errors):
 if not errors or any(e<0 or e>1 for e in errors): raise ValueError("invalid errors")
 return 1-sum(errors)/len(errors)
