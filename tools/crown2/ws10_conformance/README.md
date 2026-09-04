# WS10 — OCEL Process Conformance

Falsification rules over Crown-2 OCEL 2.0 logs, as an executable Python engine
and as equivalent SPARQL over an RDF projection. Status: LAB_PROVEN (PARTIAL)
until run on Crown-2 evidence.

## Files

- `ocel_parser.py` — own OCEL 2.0 JSON parser (stdlib), events sorted by time.
- `rules.py` — 10 rules, each returns violating event ids; CLI exits 1 on any hit.
- `rdf_projection.py` — OCEL → N-Triples (`ocel:` vocabulary; materializes
  `ocel:episode` and `ocel:evidenceExists`, the two facts SPARQL cannot derive).
- `sparql/R01..R10.rq` — the same rules as SPARQL SELECT `?ev`.
- `run_sparql.py` — runs the .rq files with rdflib (exit 3 + JSON if rdflib absent).
- `fixtures/build_fixtures.py` — builds `clean.ocel.json` + `violates_Rxx.ocel.json`
  through the real `tools/ocel_v2/emitter.py`; `MUTATIONS` is the falsifier spec.
- `test_conformance.py` — stdlib unittest, real collaborators, no mocks.

## Rules (scope conventions in `rules.py` docstring)

| id | falsifier |
|----|-----------|
| R01 | PlannerInvoked with no later PlanProduced/PlanRefused sharing an object |
| R02 | PlanProduced with no later PredictionFrozen sharing an object |
| R03 | ActionStarted with no PredictionFrozen at-or-before it in its episode |
| R04 | ActionStarted whose Action has no AuthorityEvaluated at-or-before it |
| R05 | ActionStarted at-or-after an AuthorityRefused on the same Action |
| R06 | ActionCompleted with no later WorldStateObserved/QualificationObserved in episode |
| R07 | ActionCompleted/ActionFailed/QualificationObserved with no later ReceiptIssued in episode |
| R08 | LoopStarted with no later LoopClosed/LoopBlocked in episode |
| R09 | production event type related to a ProcessEpisode labelled `heartbeat*` |
| R10 | ReceiptIssued whose `evidence_path` (event or Receipt object) does not exist on disk |

## Run

```bash
cd tools/crown2/ws10_conformance
python3 fixtures/build_fixtures.py
python3 rules.py fixtures/violates_R05.ocel.json --evidence-root fixtures
python3 run_sparql.py fixtures/violates_R05.ocel.json --evidence-root fixtures
python3 -m unittest -v test_conformance
```

`uv run python` in this repo fails to resolve the env (requires-python range),
so the SPARQL path was verified with system `python3` (3.14, rdflib 7.6.0).
`rules.py` needs nothing beyond the stdlib.

## Emitter extension

`tools/ocel_v2/emitter.py`: added `evidence_path` (string) to `Receipt` and
`ReceiptIssued`, and an optional `time=` kwarg on `add_event` (CLI unchanged).
`validate.py` on `bootstrap.ocel.json` stays green.
