# WS4 — Gap -> ggen Manifest Stub

Turns a `GapDiagnosis` + `CapabilityRequirement` into a `GGenManifestStub` in the
real `ggen.toml` format used by `/Users/sac/crown-2-orthogonal/ggen.toml` and the
marketplace packs (`[project]`, `[ontology]` + `imports` + `prefixes`,
`[generation]`, `[[generation.rules]]` with `query = { file }`,
`template = { file }`, `output_file`, `mode`).

## Files

- `requirement.py` — `GapDiagnosis`, `TemplateBinding`, `CapabilityRequirement`
  (needed transition, pre/post conditions, authority class, qualification
  strategy, semantic anchors as ontology IRIs); JSON round-trip; two fixtures.
- `packs.py` — admitted-pack registry read from `~/ggen-marketplace/packs`
  (admitted = `pack.toml` + `ggen.toml` + templates + queries; 30 today).
- `manifest.py` — `build_stub()` binds each requirement by pack/template/query
  name, vendors the bound pack files (ggen runs in Docker with `$PWD` mounted at
  `/workspace`, so paths must be relative), projects requirements to
  `ontology/requirements.ttl`, and produces a preservation report: every
  requirement field is MAPPED to a named target or UNMAPPED with a reason.
- `queries/ws4-requirement.rq`, `templates/ws4-requirement.json.tera` — the
  ws4-owned re-projection rule that carries every field through `ggen sync`.
- `validate_cli.py` — real `ggen graph validate --files` + `ggen sync run --dry-run`.
- `ocel_emit.py` — records the stub on the OCEL plane using existing types
  (GapDiagnosis, Plan, Receipt; PlanProduced, ReceiptIssued).
- `test_ws4_manifest.py` — 10 Chicago-style tests (real registry, real ggen, real emitter).

## Run

```bash
cd /Users/sac/crown-2-orthogonal/tools/crown2/ws4_manifest
python3 test_ws4_manifest.py
python3 validate_cli.py            # fixtures, or: validate_cli.py reqs.json
```

## ggen CLI contract discovered (26.8.28)

No `--manifest`; `ggen.toml` from cwd only; `graph validate --files a,b`;
`sync run --dry-run --format json` prints `written/decisions/closure`.
