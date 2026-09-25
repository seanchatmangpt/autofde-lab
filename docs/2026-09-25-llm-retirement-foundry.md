# LLM Retirement Foundry — what exists, what was added, what stays unrepresentable

2026-09-25. Maps the "Claude Cloud = LLM Retirement Foundry" objective onto machinery that
already exists here, closes the one missing link it can close at `technicalStanding`, and
names the metrics that cannot be computed yet rather than approximating them.

## The objective, restated in this repo's law

A Cloud session is judged by how much *future* LLM work it deletes, not by how much code it
writes:

```text
Find -> Fence -> Reuse/Compose -> Falsify -> Verify -> Formalize
     -> Automate -> Receipt -> Replay -> Retire
```

Every serious change should satisfy `LLMResidue(E_after) <= LLMResidue(E_before)`, and a
*retirement* is claimed only when a replacement is shown equal to the LLM on a held-out subject.

## What already existed (IEC, v26.9.23)

| Foundry step | Machinery | Evidence |
|---|---|---|
| Falsify / Verify / Replay / Retire | `iec/crowns/retirement.py` — `ReasoningClass`, `c3_court`, `ledger_entry` | `receipts/v26.9.23/iec/c3/retirement-ledger.jsonl`: `RC-GENERATED-OUTPUT-AUDIT` → `RETIRED_FROM_LLM` (13/13 held-out rows) |
| Formalize / Automate | `iec/crowns/{kernel,decompile,antiunify}.py`, ggen | `receipts/v26.9.23/iec/c1/` |
| Handoff for the residual | `iec/claude_contract.py` — Claude output is a hypothesis only | — |

What was missing was the **left edge**: nothing enumerated *which* LLM edges exist, so the
retirement ledger had no inventory to drain and no way to show a change reduced residue.

## What was added: IEC-011 residue census (`iec/crowns/residue.py`)

`python -m autofde_lab.iec.crowns.residue <out> [--commit C] [--base B]`

- Reads every `.py` blob at an exact commit from the git object database (never the working
  tree), resolves call targets through each file's own imports with `ast`, and records every
  construction of an LLM program (`dspy.Predict`, `ChainOfThought`, `ReAct`, …) or client
  (`dspy.LM`, `anthropic.Anthropic`, `openai.OpenAI`, …).
- Imports are not edges; provider calls outside the rule table are counted, not dropped;
  unparseable files are listed, not skipped.
- Residue kind (→ retirement mechanism: ggen, SPARQL, PDDL, SAT/SMT, TLA+, SHACL, …) and the
  ledger reasoning-class id stay `UNKNOWN` until the producer writes
  `# llm-residue: kind=<k> class=<RC-…>` at the call site. That marker is the **Fence**: the
  only way a call site joins a ledger row is an explicit edge, never a matching name.
- `residue_delta` compares two commits without line numbers. A removed edge is reported as
  removed; `retired` stays `UNKNOWN` — deleting a feature also deletes its LLM call.

### Measured win — first census, autofde-lab@f718d65

Receipt: `receipts/v26.9.25/iec/residue/` (replayed byte for byte by
`tests/iec/test_residue_census_chicago.py`).

- `LLMResidue = 94` static edges: 47 package (`src/`), 39 test, 8 other (`scripts/` etc.).
- By API: `dspy.Predict` 33, `dspy.LM` 31, `dspy.ChainOfThought` 19, `dspy.ReAct` 5,
  `dspy.MultiChainComparison` 3, `dspy.BestOfN` 2, `dspy.Refine` 1. No direct
  anthropic/openai/litellm client construction anywhere in the tree.
- 44 declared reasoning classes (`dspy.Signature` subclasses); 10 import-only files.
- Kind: 94/94 `UNKNOWN` — no call site has been fenced yet. That is the honest starting line.
- Package-zone concentration: `reasoning/sre_troubleshooting_pipeline.py` 10,
  `sregym_sota/agent.py` 8, `reasoning/gymact_dspy_signatures.py` 6.
- Delta vs `98b6cc9` (the commit before the census existed): `UNCHANGED` 94 → 94. The census
  module and its fixtures add no edges; the fixture programs live in string literals, which
  `ast` correctly does not count.

### Retirement frontier (recurrence only, `INFERRED_CANDIDATE`)

| Signature | Call sites | Files |
|---|---|---|
| `DiagnoseKubernetesFault` | 4 | 4 (`gepa_train`, `gymact_dspy_react`, `k8s_diagnosis_pipeline`, one test) |
| `ArithmeticClaim` | 4 | 1 |
| `ChooseMove` | 3 | 3 |
| `ClassifyAnomaly`, `DiagnoseRootCause`, `SynthesizeMitigation`, `VerifyMitigationOutcome`, … | 2 | 1–2 |

Recurrence is the one factor of `frequency × LLMcost × reuse × formalizability` observable
from a static read. The other three stay `UNKNOWN`, not zero. `DiagnoseKubernetesFault` is the
top candidate because it recurs across four independent files. It is also a diagnosis, and
diagnosis over a closed fault taxonomy is the textbook target for an ontology + rule
(classification) or a planner (hypothesis elimination).

## Metrics: which can be computed, which cannot

| Metric | Standing | Why |
|---|---|---|
| `LLMResidue(E)` | `ALIVE` (static) | `residue-census.json#llm_residue`, per commit |
| `ΔLLMResidue` per PR | `ALIVE` | `residue-delta.json`; `--base` = merge base |
| `IntelligenceRetirementRate` | `PARTIAL_ALIVE` | Numerator: `RETIRED_FROM_LLM` rows in the retirement ledger (1 so far). A rate over time needs ledger rows bound to commits. Query the ledger; don't keep a counter. |
| `LLMDependencyRatio` | `UNREPRESENTABLE:NO_REACHABILITY_OBSERVATION` | The denominator ("all reachable executable edges") needs a reachability observation, and no component produces one. It is never approximated by the static count. |

The retirement lattice proposed for chatman-ecosystem (`LLM_ONLY … LLM_RETIRED`) is the
cross-repo projection of `retirement.RETIREMENT_STATES`. Keep one lattice and project it. Don't
define a second vocabulary here.

## Next retirement edges, in order

1. **Fence the frontier.** Add `# llm-residue: kind=… class=RC-…` to the four
   `DiagnoseKubernetesFault` sites and the three `ChooseMove` sites. Each marker is a producer
   claim that takes no court. It turns `UNKNOWN` into a declared kind that can be checked.
2. **Mechanize `RC-K8S-FAULT-DIAGNOSIS`.** Freeze a deterministic diagnoser (fault ontology +
   SPARQL/Datalog rules over the observation schema) *before* collecting LLM outcomes. Then run
   `c3_court` on a held-out gym episode set, the same protocol that retired
   `RC-GENERATED-OUTPUT-AUDIT`.
3. **Gate CI on the delta.** Run the census with `--base` = merge base in the IEC courts lane.
   An `INCREASED` direction with no fenced marker on each added edge becomes a named finding.
   Unfenced residue growth is the failed-edge signal.
4. **Reachability.** Only an observed call graph (or OCEL traces of real episodes) can give
   `LLMDependencyRatio` a denominator. Until then it stays unrepresentable.
