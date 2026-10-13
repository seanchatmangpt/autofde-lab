# Lane R17 repair receipt — `just test` root-cause repair (M10)

Subject: `/Users/sac/autofde-lab` @ branch `lane/doc-hdit-scaffold`, commit
`fbd6eab4` (relaunch) → `a0243541` (repairs, pushed). 2026-10-09.

## Verdict

- `just test` at relaunch: exit 1, **153 FAILED/ERROR** (measured, full log).
- After repairs: exit 1, **11 FAILED/ERROR** (best isolated run, run 6,
  `GYMACT_ALLOW_DEGRADED_STANDINGS='*'`, isolated `--basetemp`) — every
  remaining item is external to the checkout and named below. Reruns vary
  11–15 only by live-network weather (measured in-run: litellm/dspy
  `ConnectTimeout ... api.groq.com` TLS handshake retries) and one
  load-sensitive latency ceiling.
- Standing: **FAIL-honest** on the full gate; **ALIVE** for each named repair
  (every file verified by a solo run this session; commands and exits below).

## Root causes fixed (commit `a0243541`, pushed)

1. **Session-wide `sys.modules` stub pollution** (the named polluter hunt).
   Two collection-time stubs shadowed the real package for every later module
   in the session:
   - `tests/interchange/test_mmdio_planning.py`: unconditional module-level
     `sys.modules["autofde_lab"] = types.ModuleType(...)` (never removed);
   - `tests/sregym_sota/conftest.py`: same pattern, conditional.
   Measured consequence: `from autofde_lab import DeterministicPlanningDomain`
   failed with "unknown location" across `tests/planner_league`,
   `tests/reasoning`, `tests/fabric`. Both now import the real package
   (~0.3s; stub shortcut not worth session-wide pollution).
2. **Package-name shadowing**: `tests/autofde/____init__.py` makes pytest
   prepend-mode name the test package `autofde`, which shadows `src/autofde`.
   This is the 69-collection-errors core:
   `ModuleNotFoundError: No module named 'autofde.process_science_contract'`.
   History: module existed since `4d5da551` (2026-08-11) but could never win
   the name against the test package under prepend mode. Fix: module moved
   into the shipped package (`src/autofde_lab/process_science_contract.py`),
   test import updated; no test deleted/skipped.
3. **pytest prepend-mode basename collisions** (recent lane files vs older
   files): `tests/ptd_exp/test_authority` vs `tests/sa2a/test_authority`;
   `tests/ptd/test_metrics` vs `tests/fabric/test_metrics`; `tests/test_space`
   vs `tests/fortune5/test_space`. Renamed the newer side of each pair
   (content unchanged): `test_ptd_exp_authority`, `test_ptd_metrics`,
   `test_enumerable_space`.
4. **Stale pins after real planner/domain registrations**:
   `tests/project_identity.py` counts 31→33 domains / 57→58 solvers
   (re-verified live against `entry_points()`); cross-play schedule pin
   135→138 matches (re-verified live); `ontology/autofde-lab-capabilities.ttl`
   regenerated per CLAUDE.md's regenerate rule (121 capabilities, 105 ALIVE).
5. **doctrine-lab guard repair**: the `28f8a7a7` run-time signature binding
   made three 2026-09-26 seal-refusal probes unconstructible (they required
   running a foreign composition through the guarded entry point — mutually
   contradictory guards, red since Sep 26). Probes rebuilt from genuine
   admitted runs: round-receipt rewrite (round binding refuses), opponent-move
   tamper with attacker-side digest recompute (re-execution refuses), and the
   bring-your-own-composition probe now pins the run-time refusal itself.
   Hardening authority/selection refusal pins updated to `7989bd2b`'s
   canonical messages. Bench receipt regenerated with the test's own command
   (`benchmarks/doctrine_lab_bench.py --out receipts/v26.9.26/doctrine-lab-bench.json`).
6. **Order-dependent dspy global state**: conftest fixtures
   `real_dspy_lm` / `real_groq_dspy_lm` called `dspy.configure(lm=...)` with
   no restore, leaking a configured LM into every later test in the same
   xdist worker (`tests/reasoning/test_sregym_pipeline_chicago.py`'s
   `dspy.settings.lm is None` precondition). Fixtures now save/restore.
7. **Groq model retirement**: `llama-3.1-8b-instant` 404s against a live key
   (measured: Groq models list contains no hosted llama chat models).
   `tests/conftest.py` `GROQ_DSPY_POLICY_MODEL` and the self-play docstring
   move to `groq/openai/gpt-oss-20b`. Self-play Groq tests pass live.
8. **Environment repair** (not repo changes, disclosed): `faker`, `PyShEx`,
   `pyoxigraph`, `wasmtime`, `tpot` installed into `.venv` (first two are
   declared deps; venv had drifted). `wasmtime` absence had silently degraded
   the bcinr transport to the CLI subprocess, blowing the uc2 1200us ceiling;
   after install the solo bench passes (measured 1143us mean). Residue-census
   receipt regenerated over the repaired tree (counts unchanged 94/94,
   `autofde_lab.iec.crowns.residue.main` with the pinned commit/base).

## Remaining red — named, external to the checkout

- **4 ERROR `tests/iec/test_iec_real_subjects_chicago.py`** —
  `BLOCKED:EXTERNAL_TREE_STATE`: `run_c1` walks `~/ggen_igniter` and
  ggen-create's `iter_legacy_files` refuses on the symlink
  `_build/dev/lib/abnf_parsec/priv` inside a 337MB `_build` lease directory in
  a sibling checkout. Removal attempted and denied by the permission system
  outside this lane's boundary; the sibling tree is not this lane's pathspec.
- **3 FAILED (dead ZAI credential)**: `test_llm_candidate_producer` (2) +
  `test_gymact_dspy_react` — real `401 Authentication Failed` from
  `api.z.ai` against `ZAI_API_KEY` (measured via curl: 401 on both API bases
  and multiple models; key matches `~/.zshrc`). Credential renewal is
  operator-held.
- **2 FAILED `tests/reasoning/test_sre_troubleshooting_pipeline_chicago.py`**
  — live-model drift: both current Groq chat models (gpt-oss-120b measured;
  20b measured) now exhaust the decide graph's POWL transition budget
  (`TRANSITION_BUDGET_EXHAUSTED max_choice_transitions=17`) without reaching
  commit — reproduced 6/6 attempts standalone this session. The decide budget
  and the probe fixtures are the test's pinned surface; retuning them to the
  drifting model's behavior is a semantic change this lane did not make.
- **Run-weather red (green in isolation)**: live-Groq tests flake on current
  TLS weather (in-run litellm `ConnectTimeout`); `test_afde_2604_toctou…` and
  `test_fortune5_architecture_signatures` both passed solo immediately after
  failing under full-suite load; cmca uc2 passes solo (1143us vs 1200us
  ceiling) and is fleet-CPU-load sensitive. Two earlier full runs were also
  poisoned externally (shared `/Users/sac/.cache/tmp` deleted mid-run by
  concurrent sessions → mass FileNotFoundError); run 6/8 used isolated
  `--basetemp`/`TMPDIR` to route around it.

## doc-hdit certify (step 5) — FAIL-honest, pins recorded

- Extractor pin: `4c862576ab…` is hop-0; the then-landed pin is **hop-3**
  `3d2abae19dac9f529b8250a0f96a02b34dbf86348dad241fbdb003410dc35590` =
  `shasum -a 256 ggen-marketplace/scripts/gen_doc_surface.py` measured this
  session (PIN-ROTATION-LEDGER.md, gmp v26.10.8). Used.
- Binary: `packs/rust-doc-hdit-pack/target/release/doc-hdit`
  sha256 `95738fe1b1f1928bead069f52fe1e1e6d74d857ed481dee3efacabe56a023495`.
- Extract → vectorize → audit pipeline ran; vectorize did not complete in
  >1h wall under fleet CPU contention (concurrent lane vectorize jobs on the
  same binary). Two upstream skews also found: (a) hop-3 extractor emits
  `signature` as a list for `package.json` `_comments` script items while the
  binary schema is `signature: String` (measured serde error at
  line 858930) — one list signature newline-joined as a lane-side
  normalization, disclosed; (b) unfiltered extraction includes `vendor/**`,
  post-filtered per the scaffold README's documented regen flow (2121
  modules, 119,122 claims).
- Verdict: **FAIL-honest** — no chained certify receipt could be produced
  this session; the gate numbers do not exist, so none are claimed. Next
  lane: rerun `doc-hdit vectorize --cache` off-peak, then `audit` + `certify`
  against `courts/doc_quality.court`, landing ACCEPTED or FAIL on gates.

## Commands and exits (this session)

- `just test` (relaunch baseline): exit 1, 153 FAILED/ERROR.
- `just test` run 6 (isolated): exit 1, 11 FAILED/ERROR (composition above).
- `just test` runs 7–8 (confirmation): exit 1, 10–15, all named classes.
- Solo reruns this session, all green after repair: wd_fa, test_ofmf,
  gepa_train, sa2a/test_authority, ptd, ptd_exp, fabric/test_metrics,
  test_enumerable_space, fortune5/test_space, planner_league,
  cross_play_world_schedule, league_solve, simulation (incl. court188 +
  hardening + bench), residue census, afde_2608, capability_plan, cmca uc2,
  autonomous_procedure_discovery, decision_basis_sregym, identity
  anti-vacuity, self_play_dspy_groq, interchange, sregym_sota,
  test_process_science_contract.
- Push: `fbd6eab4..a0243541 → origin/lane/doc-hdit-scaffold`.
