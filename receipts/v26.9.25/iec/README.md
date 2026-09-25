# IEC receipts — v26.9.25

- `residue/` — IEC-011 LLM residue census (extractor version 2).

  ```bash
  python -m autofde_lab.iec.crowns.residue receipts/v26.9.25/iec/residue \
    --commit 85c367467889cb8bb55574b8629b4cabdacff47c \
    --base 98b6cc9bfe3af8a25b3ad53019f5fb71fe2d37d0 --gate
  ```

  `residue-census.json` is the census at `85c3674`, the commit that fenced the first frontier.
  `residue-census.base.json` is the census at `98b6cc9` (master before IEC-011).
  `residue-delta.json` compares the two without line numbers (`gate: PASS`). Deterministic:
  no timestamps, no local paths, content-addressed ids. `tests/iec/test_residue_census_chicago.py`
  replays all three byte for byte on Python 3.12 and 3.13. A file that no longer replays is no
  longer evidence.
