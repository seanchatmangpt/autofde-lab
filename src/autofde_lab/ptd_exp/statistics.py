import math
def mean(xs):
 if not xs: raise ValueError("samples required")
 return sum(xs)/len(xs)
def population_stddev(xs):
 m=mean(xs); return math.sqrt(sum((x-m)**2 for x in xs)/len(xs))
def confidence_band(xs,z=1.96):
 m=mean(xs); h=z*population_stddev(xs)/(len(xs)**.5); return m-h,m+h
