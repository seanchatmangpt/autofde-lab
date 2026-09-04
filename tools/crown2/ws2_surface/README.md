# WS2 Repo Action-Surface Discovery

Projects a repository's declared build/CI/infra surface to `CandidateCapability[]`
so the Crown-2 authority plane can decide what may run, how, and how it is qualified.
Stdlib-only Python 3.11+ (`tomllib`). Status: LAB_PROVEN = PARTIAL until Crown-2
evidence promotes it.

## Run

```bash
cd tools/crown2/ws2_surface
python3 discover.py /path/to/repo --out surface.json [--run-help --scratch DIR] [--ocel log.ocel.json]
python3 test_ws2_surface.py -v
```

Discovery never executes anything inside the target repo. `--run-help` runs
`<bin> --help` only for binaries already on PATH, from `--scratch`, and only for
non-system tool binaries (coreutils/shell words are denylisted in `extractors.py`).

## Files

- `model.py` — `CandidateCapability` / `RepoSurface` schema (validated on dump).
- `rules.json` — ordered authority rules (READ < REVERSIBLE_BUILD < NETWORK_FETCH <
  CONSEQUENTIAL < DESTRUCTIVE), reversibility, effects, qualification strategy per class.
- `classify.py` — line splitting, first-match-per-line, max over lines, dependency
  inheritance (justfile/Makefile/Taskfile `depends_on`).
- `extractors.py` — justfile, Makefile, Taskfile.yml, package.json scripts, mix.exs
  (deps/aliases), Cargo.toml (+workspace members, `[[bin]]`/`profile.release` ->
  `cargo build --release`, cdylib -> wasm target), `.cargo/config` aliases, pyproject
  scripts/entry-points/pytest/poe, GitHub Actions `run:` steps + `workflow_dispatch`,
  Dockerfile stages, compose services, Terraform dirs, `--help` probes.
- `discover.py` — walker + JSON dump + OCEL emission (Action objects via
  `tools/ocel_v2/emitter.py`, no schema extension needed).
- `surfaces/` — real outputs for `autofde-lab` (this worktree) and `beam4pm`
  (canonical checkout, read-only), plus the merged `ws2.ocel.json`.

## Falsifiers (all in `test_ws2_surface.py`)

F1 `mix deps.get` + rf1 `cargo build --release`; F2 every justfile recipe present
(cross-checked with `just --summary --justfile ... --working-directory <scratch>`);
F3 `git push` CONSEQUENTIAL, `git push --force` / `rm -rf` / `terraform destroy`
DESTRUCTIVE, dependency-only recipes inherit; F4 synthetic on-disk fixture covers
all 13 source kinds; F5 OCEL emission validates green.

## Known limits

- YAML handling is a minimal indentation walker (block scalars, quoted scalars,
  6/8-space step indentation); exotic workflow layouts fall back to fewer steps.
- Effects for `bash script.sh` / `python3 x.py` are UNKNOWN by design (script bodies
  are not read); classification of those is the rules.json default.
