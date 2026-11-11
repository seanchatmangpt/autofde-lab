# Skip Audit L11

Standing: PARTIAL

Subject: `/Users/sac/autofde-lab/tests`, Python 3.13.9 venv, 2026-11-11. Read-only lane: no
test or source edited, no git state commands. Raw per-directory output: `/tmp/l11/*.out`
(`b_*.out` for the second pass). Command per directory (parallel, 6 at a time):
`timeout 900 .venv/bin/python -m pytest tests/<dir> -p no:cacheprovider -rsx -q`.

## Coverage and caveats

- Static census: 249 lines match `pytest.skip|mark.skip|skipif|importorskip|xfail`
  (92 hard/xfail, 114 `skipif`); the lane brief's 188/157 figures do not match this count.
- `-rs` run: 47 of 48 top-level dirs finished. Dirs with zero firing skips and `rc=0`:
  aaif adapters agent aloop autocast autofde beam case_library companion e2e eds evidence
  factory flight_planning fortune5 forwardbench interchange lab ontology ptd ptd_exp reflex
  sa2a scanner semantic_parts simulation sregym_sota (and others with no SKIPPED lines).
- UNVERIFIED (not censused): `tests/solvers/python` (timeout 900s, rc=124, no summary),
  `tests/ecosystem` (no summary captured; still running at last read).
  `tests/solvers/cpp` rc=0, no skips.
- `tests/fabric` exited rc=139 (segfault) after printing its skips; the skips below are
  those printed, the tail of the dir after the crash is unverified.
- First-pass collection errors in domains/solvers (`pyarrow`, `pyRDDLGym`, `pyRDDLGym_jax`,
  `ray.tune`) were install churn: a re-collect (`--co`) afterwards left only the errors
  below. Remaining collection errors (4):
  - `tests/solvers/python/openevolve/test_openevolve_{api_extraction,public_proxy,solver}.py`:
    `ModuleNotFoundError: No module named 'openevolve'`.
  - `tests/sota/test_crown_receipt_live_chicago.py`: `Failed: standing 'LOCAL...` raised at
    collection.
- Non-skip red seen (not skips, listed for lane assignment): `tests/domains` has 122
  error/failed lines, e.g. `RuntimeError: gymact bridge subprocess failed`; `tests/scheduling`
  `minizinc.error.MiniZincError: minimum of empty set is undefined`; `rc=1` in benchmarks,
  iec, planner_league, semantic_models, wd_fa, reasoning (cause not triaged).
- Classes: 1 = installable declared extra, 2 = local binary/corpus present or buildable here,
  3 = truly external, 4 = retired/disabled with recorded reason.

## Firing skips, grouped by directory

### tests/cmca (5 skips)

| test file:line | reason | class | remedy |
|---|---|---|---|
| tests/cmca/test_bcinr_wasm_bridge.py:58,84,96,126,152 | wasmtime runtime or `bcinr_cmca_wasm.wasm` absent | 1 (+ build) | `uv pip install "wasmtime>=48"` (extra `bcinr-wasm`); wasm artifact build per `wasm/README.md` (UNVERIFIED whether artifact exists) |

### tests/fabric (rc=139, partial)

| test file:line | reason | class | remedy |
|---|---|---|---|
| test_afde_2611_shllm_bounded_tier_closure.py:140; test_dspy_mcp_planner_loop_chicago.py:60 | `~/turbo-fieldfare/.build/release/TurboFieldfareServer` and `scratch/gemma4.gturbo` absent (both confirmed missing by `ls`) | 3 (model weights) / 2 for binary | `cd ~/turbo-fieldfare && swift build -c release` (binary); weights external |
| test_optional_dependencies.py:16 | `No module named 'a2a'` | 1 | no `a2a` entry in pyproject extras (grep); needs the `a2a-sdk` package: `uv pip install a2a-sdk` (package name UNVERIFIED) |
| test_phi_dispatch_chicago.py:177,238 | `cmca_rank_cli` not resolvable (`CMCA_RANK_CLI_BIN`, `$BCINR_HOME/target/debug`) | 2 | `~/bcinr` exists; `cd ~/bcinr && cargo build -p <cmca_rank_cli crate>`, export `CMCA_RANK_CLI_BIN` |
| test_platform_console_capability_plan_chicago.py:229; test_platform_console_full_capability_suite_chicago.py:645 | `PLATFORM_CONSOLE_BASE_URL`/`CAPABILITY_STATE_SNAPSHOT_SECRET`/`PLATFORM_CONSOLE_API_KEY` unset | 3 | needs a live console deployment + secret |
| test_platform_console_full_capability_suite_chicago.py:210,218,224,404 (x42),415 (x42),458 (x42),484 (x42) | `gymact.gyms.platform_console_ontology_provider` or `~/gymact/.../ontology.ttl` unavailable; `gymact` imports fine in venv | 2 | find the provider module under `~/gymact` (`ls ~/gymact/src/gymact/gyms`), align the vendored pin/path; UNVERIFIED which of the two is missing |

### tests/iec (11 skips, all one cause)

| test file:line | reason | class | remedy |
|---|---|---|---|
| tests/iec/test_tlc_court.py:58,88(x4),112,124,136,143,164,183,203; tests/iec/test_tlc_delegation_admission.py:48,67(x4) | `UNSUPPORTED:TLC_TOOLCHAIN_ABSENT`: `~/.cache/autofde-lab/tla2tools/1.7.4/tla2tools.jar` missing | 2 | `scripts/fetch_tla2tools.sh` exists (digest in `tools/tla/tla2tools-1.7.4.sha256`); `java` present at `/usr/bin/java`. Network needed to fetch; a `tla2tools.jar` also exists under `~/ash_pplan/tmp/...` (digest not checked, do not reuse unverified) |

### tests/planner_league (5 skips)

| test file:line | reason | class | remedy |
|---|---|---|---|
| test_heterogeneity_benchmark.py:6; test_policy_ecology.py:6; test_policy_ecology_experiment.py:6; test_policy_ecology_sweep.py:6; test_temperament_design_bridge.py:6 | `gymact.policy_ecology` absent from admitted gymact pin | 2 | `ls ~/gymact/src/gymact` shows a gymact checkout; check whether `policy_ecology` exists there and advance the installed gymact (`uv pip install -e ~/gymact`) |

### tests/planning, tests/ocel, tests/reasoning (wasm4pm / oracles)

| test file:line | reason | class | remedy |
|---|---|---|---|
| tests/planning/test_planner_powl_ocel_proof_chicago.py:310; test_planner_powl_ocel_proof_scaled_chicago.py:203; tests/ocel/test_wasm4pm_bridge.py:40; tests/reasoning/test_drift_architecture_change_trigger_chicago.py:39 | no built `wpm` (`$WASM4PM_CLI`, `~/wasm4pm/target/{debug,release}/wpm`; `~/wasm4pm/target` absent) | 2 | `cd ~/wasm4pm && cargo +nightly-2026-04-15 build -p wasm4pm-cli`; export `WASM4PM_CLI` |
| tests/ocel/test_oracle_differential.py:145 (x4), :151 (x4) | `RF2/RF3_ORACLE_BINARY_ABSENT` | 2 | `CARGO_TARGET_DIR=/tmp/autofde-oracle-target cargo build --release` in `~/beam4pm/native/rf2-conformance-oracle` and `.../rf3-ocel-oracle` |
| tests/ocel/test_alternative_ocel_ecosystem.py:73 | polars or duckdb unavailable | 1 | `uv pip install "polars>=1.0.0" "duckdb>=1.0.0"` (extra `ocel-ecosystem`) |
| tests/ocel/test_opql_and_ocelescope_integration.py:51,65 | `ocelescope`, OPQL required | 1 | `uv pip install "ocelescope>=0.7.0"` (extra `ocel-ecosystem`, pyproject line 256) |
| tests/reasoning/test_gepa_train_chicago.py:220,245 | Hard-disabled: real `dspy.GEPA` compile makes billed LM calls | 4 | recorded user instruction in skip message; re-enable only on user say-so |
| tests/reasoning/test_sregym_pipeline_chicago.py:422 | `kubectl cluster-info` fails (`kubectl` present, `127.0.0.1:54751` connection refused) | 3 (cluster) | start a local cluster (kind/minikube) that the kubeconfig points at |

### tests/powl (3), tests/semantic_models (2), tests/sota_factory (5), tests/scripts (3), tests/wasm (1)

| test file:line | reason | class | remedy |
|---|---|---|---|
| tests/powl/test_soundness_bridge_chicago.py:77,100,112 | `BLOCKED:BCINR_SOUNDNESS_CLI_BINARY_NOT_FOUND` | 2 | build the soundness CLI in `~/bcinr` with cargo (crate name UNVERIFIED) |
| tests/semantic_models/test_tiny_runtime.py:187,205 | `No module named 'sklearn'` | 1 | `uv pip install scikit-learn` (no pyproject extra lists it, grep returned none; add one) |
| tests/sota_factory (5, via `_pytest/python.py:149`) | async test functions, no async plugin | 1 | `uv pip install pytest-asyncio` (not installed; anyio is, and is not a substitute without a pytest plugin config); also add to `test` extra |
| tests/scripts/test_k8s_deploy_deadend_guard_chicago.py:76,82,122 | no reachable Kubernetes cluster | 3 | local kind/minikube cluster |
| tests/wasm/test_dspy_wasm.py:135 | wasm/dspy-wasm npm deps not materialized | 2 | `cd wasm/dspy-wasm && npm install` |

### tests/domains (second pass, rc=1)

| test file:line | reason | class | remedy |
|---|---|---|---|
| tests/domains/python/test_tpddl_domain.py:276,294,310,326,342,365,401,442 | `z3-solver not installed` | 1 | `uv pip install z3-solver` (extra `pddl`, pyproject line 157) |
| tests/domains/python/test_fix_git_domain.py:115 | `vendor/gyms/terminal-bench` submodule not initialized (dir is empty) | 2 | `git submodule update --init vendor/gyms/terminal-bench` (coordinator-owned git transition) |
| tests/domains/python/test_plado_domain.py:320 (x8) | discrete action encoding not tractable for agricola | 4 | recorded in skip reason; domain-size limit |
| tests/domains/python/test_up_bridge_domain.py:136 | libomp segfault on macOS | 3 (platform) | none on this host without a libomp fix |
| tests/domains/python/test_htn_stub_closure_l3_chicago.py:174 | up-aries `INTERNAL_ERROR: Real types are not supported` | 3/UNVERIFIED (solver limitation; installed `up-aries` is present) | model without real types or file upstream |
| tests/domains/python/test_level4_crown_false_greens_chicago.py:197 | no local LM server on 127.0.0.1:8080 | 3 | needs an LM server (e.g. turbo-fieldfare, see fabric) |
| tests/domains/python/test_level4_crown_unmodellable_trial_chicago.py:66 | `RETIRED 2026-09-01 (G04 backlog item 6)` | 4 | retired pin; delete or re-pin test |

### tests/sota (second pass, rc=1)

| test file:line | reason | class | remedy |
|---|---|---|---|
| tests/sota/test_sregym_autofde_planner_decision_chicago.py (34 skips, lines 238-532) | `BLOCKED:SREGYM_AUTOFDE_PLANNER_DRIVER_ABSENT`: `vendor/gyms/sregym/clients/autofde_lab_planner/driver.py` absent (dir listing shows the package present, `driver.py` not checked individually) | 2 | create/restore `driver.py` under the vendored client (vendor path is off-limits to this lane; coordinator) |
| tests/sota/test_m1_environment_dependencies.py (2) | `BLOCKED:SREGYM_VENDOR_DEPENDENCY_ABSENT` (importing `sregym.conductor.problems.registry` needs a missing module; name truncated in my capture) | 1 | read `/tmp/l11/b_sota.out` for the module, then `uv pip install` it |
| tests/sota/test_m3_sregym_ocel_telemetry_chicago.py | `BLOCKED:MCP_SERVER_UNREACHABLE (127.0.0.1:9954)`, no live SREGym cluster | 3 | live cluster + MCP server |
| tests/sota/test_decision_basis_harbor_chicago.py | `BLOCKED:REAL_TRIAL_ARTIFACT_ABSENT` under `vendor/gyms/harbor/jobs/` | 3 | requires a real harbor trial run |

## Summary of remedies by class

- Class 1 (installable): `wasmtime>=48`, `polars>=1.0.0`, `duckdb>=1.0.0`, `ocelescope>=0.7.0`,
  `z3-solver`, `openevolve>=0.2.11` (extra `solvers`, pyproject line 154, unblocks 3
  collection errors), `scikit-learn`, `pytest-asyncio`, `a2a-sdk` (names for the last three
  are not in pyproject and are UNVERIFIED).
- Class 2 (local build/path): `tla2tools.jar` fetch, `wpm`, rf2/rf3 oracles, `cmca_rank_cli`,
  bcinr soundness CLI, TurboFieldfareServer, gymact modules, `vendor/gyms` submodules,
  `npm install` in `wasm/dspy-wasm`. `ggen`, `b3sum`, `minizinc`, `java`, `cargo`, `docker`
  exist on PATH; `mfw` and `tlc` do not. No firing skip named `ggen`/`b3sum`/`minizinc`.
- Class 3 (external): platform-console env vars, model weights, K8s/SREGym cluster, LM
  server, harbor trial artifacts, macOS libomp.
- Class 4 (retired/disabled): GEPA billed-call skips, plado agricola limit, RETIRED G04 pin.
