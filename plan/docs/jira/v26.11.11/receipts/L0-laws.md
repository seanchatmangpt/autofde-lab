# L0 laws receipt

Standing: PARTIAL

- Subject: /Users/sac/plan (not a git repo; no SHA available)
- Rows: 29 (L01..L29). LOCKED 16, DEFAULT 0, OPEN 13.
- Verified: all 16 LOCKED quotes re-checked by script, `quote in tony.txt line[line]` -> 0 mismatches
  (also `grep -nF` per quote; lines 1019, 567, 1047, 273, 274, 271, 384, 476, 408, 1045, 1028, 523,
  518, 270, 1055, 127).
- Unverified (OPEN, quote UNVERIFIED): L03 L05 L08 L11 L12 L15 L16 L17 L18 L20 L22 L26 L27.
  The brief gave no decision text for these numbers; no law text invented.
- Weak citations: L10 quote shows documents only (transcript has no expiry rule); L14 supports internal
  clock only; L29 supports entity->clients/providers only, not the full flow order.
- PDF S-nn ids: none cited (pdftotext found S-nn tokens but none mapped to a law).
- pytest ids, `check`/`pddl` names (NO_PARENT, BAD_LINK, doc_valid, ...) are proposals; BAD_DIM-class
  checks do not exist in store.py yet (only BAD_CHANNEL/BAD_MODE/BAD_NAME/BAD_TYPE/UNKNOWN_KIND).
- Scenarios from pipeline/tests/mega_factories.py labels: cvs_project, cvs_repair, cvs_out_of_coverage,
  cvs_sub_sole_provider, nestle_untagged, nestle_recall_nte.
