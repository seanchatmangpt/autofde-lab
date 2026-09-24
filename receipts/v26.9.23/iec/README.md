# IEC receipts — v26.9.23

Produced by `src/autofde_lab/iec/crowns/`. Every file is deterministic (no timestamps, no local
paths, content-addressed ids) and replayed byte for byte by
`tests/iec/test_iec_real_subjects_chicago.py`. A file that no longer replays is no longer
evidence.

- `c1/` — `python -m autofde_lab.iec.crowns.crown --checkout <ggen_igniter@d84da141>
  --ggen-create <ggen-create@eaa463af> --out receipts/v26.9.23/iec/c1`. Start at
  `run-receipt.json`; per-subject courts are in `translation-validations/`, preserved
  mismatches in `counterexamples.jsonl`, open questions in `hypotheses.jsonl`, and
  proposed changes for other repositories (with no authority attached) in
  `promotion-plan.json`.
- `c3/` — `python -m autofde_lab.iec.crowns.c3 --autofde-lab . --c3-dir receipts/v26.9.23/iec/c3
  --ggen-igniter <ggen_igniter>`. The inputs are `mechanized.autofde-lab.frozen.json`
  (frozen before any LLM outcome existed; sha256 `4372b88c…`) and the two
  `llm-outcome.*.json` fixtures (`INFERRED_CANDIDATE`, provenance inside). Everything else is
  recomputed.

The census is kept only as `census.json`; per-fact observations are a projection of it
(`Census.observations()`) and are deliberately not written a second time.
