# SPC for delegation/admission headroom

The semantic court detects debt once:

`AdmissionCapacity < DelegationUnits`.

SPC adds an earlier observational layer over:

`headroom = AdmissionCapacity - DelegationUnits`.

Using the first admitted N snapshots as a baseline (default N=5), the court applies
one-sided downward Western Electric rules:

- one point below 3σ;
- two of three below 2σ;
- four of five below 1σ;
- eight consecutive below the baseline mean;
- when baseline variance is zero, any downward movement is an explicit signal.

A signal is not a semantic refusal and does not revoke authority. It identifies
process drift that should trigger evidence investigation or deterministic repair
before admission debt appears.
