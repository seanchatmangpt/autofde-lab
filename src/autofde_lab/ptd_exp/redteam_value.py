def redteam_value(recon_reuse,predictability,authority_reuse,common_mode):
 xs=[recon_reuse,predictability,authority_reuse,common_mode]
 if any(x<0 or x>1 for x in xs): raise ValueError("dimensions must be [0,1]")
 return sum(xs)/len(xs)
