# Role

The Inverse Ecosystem Compiler (IEC, v26.9.23 — `docs/jira/v26.9.23/`): recover the
semantics behind committed software, regenerate it from that recovered kernel, and
translation-validate every regeneration. It is an inference and falsification layer.
Nothing in it actuates.

# Authority

- **Observe** exact subjects: `corpus.observe_checkout` / `freeze_corpus` bind a checkout to
  `(repository, commit, tree)`; `census.census` reads the git object database at that commit,
  never the working tree.
- **Classify** artifact origin from explicit producer evidence only (`census`): generator
  markers, declared targets (`generators`), lockfiles, gitlinks, self-declared hand authorship.
  No rule reached → `UNKNOWN`.
- **Construct** candidate kernels and programs: `kernel.pack_kernel` (independent rdflib
  SPARQL), `decompile` (flat and row programs), `antiunify` (n-ary LGG with hedge holes).
- **Verify** with named verifier sets: `court.run_court` returns `PASS` / `COUNTEREXAMPLE` /
  `BLOCKED` / `UNSUPPORTED` per verifier and a claim naming the verifier-set id.
- **Retire** a reasoning class only through `retirement.ledger_entry` over a held-out C3 court.

# Non-authority

- No execution of a subject's own code. A subject's native verifiers (`mix test`, ...) are a
  `BLOCKED` court until a broker runs them (ARD section 22).
- No writes into any subject repository. Regenerated files go to an isolated destination; tree
  identity is recomputed in Python (`census.tree_id`).
- No mutation of neighbouring repositories. Findings for ggen_igniter, ggen-create, or anyone
  else are `promotion-plan.json` candidates with `authority_required` — never pushes.
- No LLM output becomes `ADMITTED` (`model.admit` refuses anything but a named `PASS`).

# Inputs

Pinned checkouts (ggen_igniter, ggen-create, autofde-lab itself); pack ontologies, gates and
templates read from the frozen commit; LLM outcomes only as `INFERRED_CANDIDATE` fixtures.

# Outputs

`receipts/v26.9.23/iec/c1/` (`python -m autofde_lab.iec.crown`) and
`receipts/v26.9.23/iec/c3/` (`python -m autofde_lab.iec.c3`). The JSON files are the only
durable record; `Census.observations()` is a projection of `census.json`, not a second copy.

# Invariants

1. **Absence is not handwritten.** A file no rule classifies stays `UNKNOWN`;
   `HANDWRITTEN_IRREDUCIBLE` is never assigned by a rule.
2. **Templates are parsed, never evaluated.** `templates.eex_chunks` / `tera_chunks` only
   tokenize; only block-depth-0 literals are necessary conditions (`chunk_depths`).
3. **A falsified hypothesis stays falsified.** A refined court (e.g. modulo formatter) is a
   second, separately named receipt; the raw counterexample is kept.
4. **A kernel that fails to explain a row is a counterexample**, never a reason to fall back to
   a flat program (flat programs reconstruct by construction).
5. **Reuse before invention (PR-005).** ggen-create is imported from its pinned checkout
   (`federation.GgenCreate`); IEC keeps its own generalization only where ggen-create returns
   a typed refusal, recorded as the capability falsifier.
6. **Receipts replay byte for byte.** No timestamps, no local paths; ids are content ids.
   `tests/iec/test_iec_real_subjects_chicago.py` re-runs both crowns and diffs every file.

# Neighboring components

`ggen_igniter` (C1 subject), `ggen-create` (federated primitive), `fabric/` (unrelated; IEC
does not register domains or solvers), `docs/STATUS.md` (ledger).

# Verification

```bash
PYTHONPATH=src python -m pytest -q -rs tests/iec
IEC_GGEN_IGNITER_CHECKOUT=~/ggen_igniter IEC_GGEN_CREATE_CHECKOUT=~/ggen-create \
  PYTHONPATH=src python -m pytest -q -rs tests/iec     # includes the real-subject crowns
grep -rn "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" tests/iec   # expect nothing
```

# Standing ceiling

Strongest establishable claim: **`IEC_TRANSLATION_VALIDATED_FOR_<exact subject>_UNDER_<verifier
set>`** — byte and tree identity of a regeneration plus static reflexion against its declared
template — and, for C3, `IEC_OUTCOME_EQUIVALENT_TO_LLM` on the compared fields only. Not
build, test, runtime, or formatter equivalence; not repository obsolescence; not global
minimality.

# Update obligations

- Changing a verifier's logic → bump its `version`; the verifier-set id changes with it.
- Changing census rules, kernel extraction, or decompile → re-run both crowns and commit the
  receipts; the replay test fails until you do.
- Changing the audit mechanism → the C3 frozen outcome must still replay (`replayed_outcome_id`
  == `frozen_outcome_id`), or the retirement is void and must be re-earned on a new held-out
  subject.
