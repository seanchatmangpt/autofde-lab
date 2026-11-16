# L0-open receipt

Standing: PARTIAL

Lane L0 (OPEN.md part). Subject: /Users/sac/plan, no git (no SHA available).

## Counts
- OPEN.md rows: 11 (O01-O11); open_switches.toml tables: 11; every row's switch key and
  default validated by a tomllib script (output: `11 rows ok 11 tables`).
- Transcript lines verified by `grep -n`/`sed -n`: 10. UNVERIFIED: 1.

## Unverified
- O10 (pm_daily_minutes_cap): no transcript line; `grep -c -i "minutes cap|daily minutes|per day"`
  on tony.txt returned 0. Only the stated tunable 480 is used.
- Thresholds #5,#3,#8,#11,#12,#15,#17,#16,#18,#20,#26/#27 are numbers only in
  MULTI-AGENT-PROMPT.md; neither it nor tony.txt names them, so no row is mapped to them.
  Rows O01-O10 are the operator-listed questions; O11 is found at tony.txt:275.
- Defaults other than the operator-stated tunables are the conservative option; code not read.

## Evidence (grep -n tony.txt)
408 internal/external clock; 450 desolate market; 1028 change order/recall; 1032 NTE;
1047 no one accepting/reactive hire; 270 one and many DBAs; 380 W9, COI; 1019 provider filter
dimensions; 475 AI photo prompt; 275 secondary out-of-coverage risk (`grep -c "secondary market"` = 1).
