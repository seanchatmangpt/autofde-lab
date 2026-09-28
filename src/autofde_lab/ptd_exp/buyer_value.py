def buyer_value(auditability,operability,compliance,interoperability,assurance):
 xs=[auditability,operability,compliance,interoperability,assurance]
 if any(x<0 or x>1 for x in xs): raise ValueError("dimensions must be [0,1]")
 return sum(xs)/len(xs)
