# IEC receipts — v26.9.25

- `residue/` — IEC-011 LLM residue census.
  `python -m autofde_lab.iec.crowns.residue receipts/v26.9.25/iec/residue --commit f718d65cff85148806cbfdeb307854565fa6eedd --base 98b6cc9bfe3af8a25b3ad53019f5fb71fe2d37d0`.
  `residue-census.json` is the census at the commit that introduced the census module.
  `residue-census.base.json` is the census at its parent. `residue-delta.json` compares the
  two without line numbers. Deterministic: no timestamps, no local paths, content-addressed
  ids. `tests/iec/test_residue_census_chicago.py` replays all three byte for byte. A file
  that no longer replays is no longer evidence.
