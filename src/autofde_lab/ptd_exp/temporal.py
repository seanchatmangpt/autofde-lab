def temporal_advantage(realignment_time,phase_duration):
 if phase_duration<=0: raise ValueError("phase duration must be > 0")
 return realignment_time/phase_duration
def strong_temporal_regime(realignment_time,phase_duration): return temporal_advantage(realignment_time,phase_duration)>1
