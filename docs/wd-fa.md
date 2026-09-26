# WD-FA: well-drilling failure analysis

`autofde_lab.wd_fa` is the well-drilling (WD) semantic failure-analysis domain:
candidate hypothesis triage over synthetic failure cases with standing
(`ALIVE` / `PARTIAL_ALIVE` / `UNKNOWN`), replayable receipts, machine
experience, OCEL 2.0 process evidence and work orders. It has no production
actuation path. Landed 2026-09-21 (commit `865c2376`).

## Entry points

- `src/autofde_lab/wd_fa/api.py` — FastAPI application (`create_app()`,
  module-level `app`) exposing `GET /health`, `POST /triage` and the
  A2A-shaped `POST /a2a/tasks/analyze_failure`; triage runs select-only
  (`authority: SELECT_ONLY`) over the bounded synthetic case set. The app
  admits browser origins via CORS — allowlist `http://127.0.0.1:3000` and
  `http://localhost:3000` only, methods `GET`/`POST`,
  `allow_credentials=False` (commit `4e09a871`).
- `src/autofde_lab/wd_fa/demo.py` — `run_demo()` and a JSON CLI
  (`python -m autofde_lab.wd_fa.demo [--json]`) executing the end-to-end
  court: TPOT training frame, triage of the known/misleading/incomplete/novel
  cases, receipt issue and verify, machine-experience replay, POWL process
  evidence and OCEL 2.0 round-trip, and a work order.

## Contract pack

`apps/wd-fa-web/ggen_contract/ggen.toml` declares the ggen contract pack
`wd-fa-zod-contract` (ontology `ontology.ttl` + `templates/`, composing the
`shacl-projection-pack` and `shacl-to-zod-pack`); the web client's Zod
contracts are manufactured from it, not hand-written.

## CI courts

- `.github/workflows/wd-fa-court.yml` — exact-head OCEL → POWL → TPOT →
  candidate court over the Python domain, tests and web app.
- `.github/workflows/wd-fa-ggen-contract.yml` — exact-head marketplace
  contract manufacture: regenerates the `wd-fa-zod-contract` projections.
- `.github/workflows/wd-fa-fullstack-factory.yml` — semantic full-stack
  manufacture of the WD-FA surface from the pinned producer SHA.
