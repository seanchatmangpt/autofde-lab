# AFDE-2609: this repo's consumer seam onto A2A-2609 (portable `graphlaw.wasm`)

- **Status**: Open
- **Severity**: Medium — not hypothetical. A real, already-passing local test
  fixture carries a hardcoded artifact hash that does not match the real
  artifact bytes, and no code path in this repo would ever catch that drift.
  See Chicago falsifiers.
- **Standing**: `PARTIAL_ALIVE` (scoped to this repo's own consumer code —
  see Local standing at the end).
- **Owning repo(s)**: `seanchatmangpt/praxis`, `seanchatmangpt/ggen`,
  `seanchatmangpt/unrdf` own `graphlaw.wasm` itself and A2A-2609's Definition
  of Done (deterministic build recipe, pinned toolchain, two-host parity
  certification). **`autofde-lab` is explicitly NOT a primary owner here**,
  per `.claude/rules/ecosystem-boundary.md`: this repo is "the search graph,"
  one seam among several, with no admission, broker, actuation, or CMCA
  authority in the ecosystem sense that file describes. This ticket does not
  claim to close, advance, or partially close A2A-2609. It reports only what
  this repo's own local consumer code does today, and exposes one typed
  local seam this repo can honestly own: the bridge that loads and drives a
  local `praxis-graphlaw-wasm` build.

## Correction to the task premise, stated plainly

The task that produced this ticket assumed this repo has zero references to
`graphlaw.wasm` and instructed reporting that plainly if grep confirmed it.
**Grep does not confirm that.** A real, working consumer bridge exists:
`src/autofde_lab/sa2a/admission/graphlaw_bridge.py` (`GraphLawBridge`), used
by `src/autofde_lab/sa2a/hooks/engine.py` (`KnowledgeHookEngine`),
`src/autofde_lab/sa2a/exchange/package.py` (`WasmComponentRef`, declares
`engine: str = "praxis-graphlaw-wasm"`), and `src/autofde_lab/sa2a/cli.py`
(`graphlaw` subcommand), exercised by four real test files under
`tests/sa2a/` (`test_graphlaw_bridge.py`,
`test_cross_runtime_falsifier.py`, `test_hook_synthesis.py`,
`test_autonomic_closed_loop_lifecycle.py`). Per
`~/.claude/rules/criticism-discipline.md` rule 1 (formalize before
dismissing) this ticket reports the real finding rather than the assumed
one.

This is a **different** surface from `src/autofde_lab/wasm/` (the sixteen
"Chatman Ecosystem" adapters — `ggen`, `mfw`, `powl`, etc. — documented in
`docs/chatman-ecosystem-wasm.md`). `graphlaw` is not among those sixteen
components (confirmed by reading `src/autofde_lab/wasm/_registry.py` in
full). The two surfaces are unrelated code paths that happen to share a
directory-adjacent theme (WASM adapters into this repo), and — this is the
finding this ticket exists to report — they do **not** carry the same
integrity discipline.

## Problem

`src/autofde_lab/wasm/_runtime.py` (`ArtifactImage.from_descriptor`,
lines 44-57) enforces real content-addressed loading for all sixteen
Chatman adapters: SHA-256 of the loaded bytes is computed and compared
against a pinned `ComponentDescriptor.artifact_sha256`, size is checked,
the Wasm v1 magic prefix is checked, and both the Node and Wasmtime backends
(`_runtime.py:96-97`, `_runtime.py:180-181`) explicitly reject any module
with ambient imports (`"ambient imports are not admitted"`).

`src/autofde_lab/sa2a/admission/graphlaw_bridge.py` (`GraphLawBridge`) does
none of this for `praxis-graphlaw-wasm`:

1. It loads `praxis_graphlaw_wasm_bg.wasm` from a hardcoded absolute local
   filesystem path (`PRAXIS_WASMPKG_DIR =
   Path("/Users/sac/praxis/crates/praxis-graphlaw-wasm/pkg")`,
   `graphlaw_bridge.py:16`) — a sibling checkout on this machine, not a
   vendored, wheel-embedded, or otherwise content-addressed artifact the way
   the sixteen Chatman adapters or `vendor/gyms/*` (exact-pinned git
   submodules) are.
2. `graphlaw_bridge.py` contains zero SHA-256 or `hashlib` references
   (verified by grep this session — see Local verification). Nothing in the
   bridge computes or checks a digest of the bytes it loads.
3. `WasmComponentRef.artifact_sha256` (`src/autofde_lab/sa2a/exchange/
   package.py:20`) exists as a schema field and participates in
   `SemanticExchangePackage.package_digest` — so the *shape* for
   content-addressed identity is present — but nothing in this repo computes
   that field from the real artifact bytes and compares. It is populated
   only as a hand-typed literal in test fixtures.
4. The real local `praxis_graphlaw_wasm_bg.wasm` module is **not**
   zero-import. `WebAssembly.Module.imports()` on the actual file (run this
   session, see Local verification) reports two imports from
   `./praxis_graphlaw_wasm_bg.js`, one of which is
   `__wbg_getRandomValues_3f44b700395062e5` — a host entropy-source binding
   pulled in by the wasm-bindgen glue. If this same module were loaded
   through `wasm/_runtime.py`'s existing ambient-import guard, it would be
   **rejected** (`"ambient imports are not admitted"`). `graphlaw_bridge.py`
   performs no import inspection at all, so this host capability import is
   silently accepted today. This is the exact class of risk A2A-2609 Law 4
   names ("No network/filesystem/shell capability is imported unless
   explicitly required and admitted; default law module imports none") and
   the exact class of risk `wasm/_runtime.py` was built to catch — for a
   different set of components.

## Required change, scoped to what this repo can honestly contribute

This repo cannot produce `graphlaw.wasm`, define its deterministic build
recipe, pin its toolchain, or certify two-host parity — those are
`praxis`/`ggen`/`unrdf`'s Definition of Done per A2A-2609, and none of that
work happened this session. What this repo can honestly contribute, as a
consumer/seam only, and has **not yet done** (diagnosis only this session,
per the task's own instruction against committing code — no fix applied):

1. Reuse the existing in-repo pattern (`wasm/_runtime.py`'s
   `ArtifactImage.from_descriptor`) rather than inventing a new one, per
   `~/.claude/CLAUDE.md`'s Research Sources instinct of searching existing
   manufacturing capital first: give `GraphLawBridge` an equivalent
   digest-and-size check at load time against a pinned expected SHA-256,
   raising a typed error (not a silent pass) on mismatch.
2. Populate `WasmComponentRef.artifact_sha256` from a real computed digest
   of the loaded bytes, not a hand-typed literal, and fail closed if the two
   diverge.
3. Add an ambient-import check to `GraphLawBridge` mirroring
   `wasm/_runtime.py:96-97` / `:180-181`, and — since the real artifact
   already imports `getRandomValues` — either admit that import explicitly
   and by name (Law 4's "unless explicitly required and admitted"), or
   treat it as a finding to raise with the owning repos rather than silently
   accepting it here.

None of the three items above were implemented this session. This ticket is
a diagnosis, matching the pattern already used by `AFDE-2607-cross-repo-
seam-typing.md` in this same directory (report-only, no functional change,
per task scope).

## Laws that actually apply locally

Restated from A2A-2609's own Laws section, scoped to what is
locally checkable from this repo without praxis/ggen/unrdf access:

1. *"Module identity is content-addressed and recorded in every admission
   receipt it participates in."* — Locally: the **schema** for this exists
   (`WasmComponentRef.artifact_sha256`), but the **enforcement** does not
   (see Problem, item 3). `PARTIAL_ALIVE` at best, and only for the schema
   half.
2. *"No network/filesystem/shell capability is imported unless explicitly
   required and admitted; default law module imports none."* — Locally:
   falsified for the real artifact as loaded today (see Problem, item 4).
   The module does import a host capability, and nothing in this repo's
   consumer code admits or even names that import. `BLOCKED:UNADMITTED_IMPORT`
   is the honest local classification for this one law, not `ALIVE` or
   silence.
3. Laws 1, 2, 3, 6 (semantic determinism across hosts, host-runtime
   invariance, typed refusal on unsupported constructs, declared
   native/WASM parity boundary) are **not evaluable from this repo alone**
   — they require the build recipe and toolchain identity that live in
   `praxis`/`ggen`, which this session did not touch. `UNKNOWN` from here,
   by construction, exactly as `.claude/rules/ecosystem-boundary.md`
   requires for anything outside this repo's admitted scope.

## Chicago falsifiers

Per `.claude/rules/testing-chicago-style.md`, a falsifier is only real if it
was actually run. One was, this session, and it already fires (silently —
which is itself the defect):

1. **Fired, this session**: the hardcoded `artifact_sha256` in
   `tests/sa2a/test_cross_runtime_falsifier.py:43`
   (`34fe50b8539067f4d47af577722744094e98b372b8774a643756265ec6bc7123`) does
   **not** match the real SHA-256 of the actual local artifact it names
   (`187688d9e7e33a575713d6911d75687adb38713ed37412e211af263dfcbe0c28` —
   computed this session with `shasum -a 256`, see Local verification). The
   test still passes, because nothing in `GraphLawBridge` or the test itself
   ever compares the declared value to the real bytes. This is the same
   defect class this repo's own `.claude/rules/absence-is-not-evidence.md`
   and `.claude/rules/no-dual-bookkeeping.md` already name: a declared field
   that looks like content-addressed identity but was never checked against
   the artifact it claims to identify — a false-green by construction, not
   by malice.
2. **Fired, this session**: `WebAssembly.Module.imports()` on the real
   artifact returns a non-empty list (2 imports, one a host entropy
   binding), directly falsifying any claim that this repo's graphlaw
   consumption path is zero-import today.
3. **Not run this session, would require praxis/ggen access**: "one fixture
   produces the same admitted/refused result under at least two independent
   WASM hosts" (A2A-2609's own falsifier 1). `tests/sa2a/
   test_cross_runtime_falsifier.py` gestures at this (Python/Wasmtime vs. a
   BEAM binary at `/Users/sac/beam4pm/priv/bin/autofde`) but that is a
   parity check between two *consumers* of the same local file, not a
   content-addressed-artifact-across-hosts check per A2A-2609's own
   definition, since neither side verifies the artifact hash it is running.

## Definition of done (typed local seam only, never cross-repo closure)

- [x] Read `.claude/rules/ecosystem-boundary.md` before writing any standing
      claim in this document.
- [x] Read the A2A-2609 ticket in full.
- [x] Listed and read `src/autofde_lab/wasm/` in full, and
      `docs/chatman-ecosystem-wasm.md` in full.
- [x] Ran real grep for `graphlaw` across the repo and reported the real
      result, correcting the task's mistaken zero-reference premise.
- [x] Ran a real SHA-256 comparison between a hardcoded test fixture value
      and the real local artifact bytes, and reported the real mismatch.
- [x] Ran a real `WebAssembly.Module.imports()` check against the real
      local artifact and reported the real (non-zero) result.
- [x] Ran the existing local test suite for this seam
      (`tests/sa2a/test_graphlaw_bridge.py`) and reported the real result.
- [ ] **Not done, explicitly out of scope for this repo per
      `.claude/rules/ecosystem-boundary.md`**: any part of A2A-2609's own
      Definition of Done (deterministic build recipe, pinned toolchain,
      artifact hash emitted/consumed by admission receipts, two independent
      host runtimes certified against the same fixtures). Those remain
      `UNKNOWN` from here by construction — this repo has no admission,
      broker, or actuation authority over `praxis`/`ggen`/`unrdf`'s build.
- [ ] **Not done this session**: implementing the three items under
      "Required change" above. This ticket is diagnosis only.

This ticket never claims A2A-2609 itself is closed, advanced, or partially
closed by this repo. It closes only the narrower local question: does this
repo's own `graphlaw.wasm`-consuming code follow the same content-addressed,
deterministic-build discipline its sibling `wasm/` adapter surface already
does. **It does not, today, and this ticket names exactly where the gap is
with evidence, not assumption.**

## Local verification (this session)

All commands run from `/Users/sac/autofde-lab`, confirmed via `pwd` before
any other action, as this ticket's originating task required.

```bash
cd /Users/sac/autofde-lab && pwd
```
```
/Users/sac/autofde-lab
```

Real reference search (abridged to distinct source/test/doc files; the full
raw output also matched several unrelated `.claude/worktrees/*` snapshot
copies of `docs/STATUS.md` / `docs/ecosystem-standing.md`, which are not
re-analyzed here as they are stale worktree snapshots, not live source):

```bash
grep -rni "graphlaw" --include="*.py" --include="*.md" --include="*.ttl" \
  --include="*.json" . 2>/dev/null | grep -v "__pycache__"
```

Real distinct live-source files matched (worktree snapshots excluded):

```
archive/markdown/docs/ecosystem-standing.md
archive/markdown/docs/STATUS.md
AUTOFDE_LAB_v26.9.16_ARD.md
AUTOFDE_LAB_v26.9.16_PRD.md
docs/ecosystem-standing.md
docs/rfcs/RFC-SA2A-002-compliance-matrix.md
docs/rfcs/RFC-SA2A-002-v26.9.16.md
docs/STATUS.md
src/autofde_lab/receipts/wasm4pm_types.py
src/autofde_lab/sa2a/admission/graphlaw_bridge.py
src/autofde_lab/sa2a/cli.py
src/autofde_lab/sa2a/exchange/package.py
src/autofde_lab/sa2a/hooks/engine.py
src/autofde_lab/sa2a/hooks/model.py
src/autofde_lab/sa2a/hooks/synthesis.py
tests/sa2a/test_autonomic_closed_loop_lifecycle.py
tests/sa2a/test_cross_runtime_falsifier.py
tests/sa2a/test_graphlaw_bridge.py
tests/sa2a/test_hook_synthesis.py
```

Confirms `src/autofde_lab/wasm/` itself (the Chatman 16-adapter surface) has
**zero** `graphlaw` references — the two surfaces are genuinely disjoint:

```bash
grep -rn "graphlaw" src/autofde_lab/wasm/*.py
```
```
(no output — zero matches)
```

Confirms `graphlaw_bridge.py` has zero hash-verification code:

```bash
grep -n "sha256\|hashlib\|artifact_sha\|hash(" src/autofde_lab/sa2a/admission/graphlaw_bridge.py
```
```
(no output — zero matches)
```

Real SHA-256 of the actual local artifact vs. the hardcoded test fixture
value:

```bash
shasum -a 256 /Users/sac/praxis/crates/praxis-graphlaw-wasm/pkg/praxis_graphlaw_wasm_bg.wasm
```
```
187688d9e7e33a575713d6911d75687adb38713ed37412e211af263dfcbe0c28  /Users/sac/praxis/crates/praxis-graphlaw-wasm/pkg/praxis_graphlaw_wasm_bg.wasm
```

Hardcoded value in `tests/sa2a/test_cross_runtime_falsifier.py:43`:
`34fe50b8539067f4d47af577722744094e98b372b8774a643756265ec6bc7123` —
**does not match** the real file's digest above. 64 hex characters in both
(confirmed with `wc -c`), so this is a real content mismatch, not a
formatting artifact.

Real ambient-import check against the actual local artifact (Node.js
`v26.8.1`, run this session):

```bash
node -e '
import("fs").then(async (fsmod) => {
  const fs = fsmod.default;
  const bytes = fs.readFileSync(
    "/Users/sac/praxis/crates/praxis-graphlaw-wasm/pkg/praxis_graphlaw_wasm_bg.wasm"
  );
  const mod = await WebAssembly.compile(bytes);
  const imports = WebAssembly.Module.imports(mod);
  console.log(JSON.stringify({import_count: imports.length, imports}));
});'
```
```
{"import_count":2,"imports":[{"module":"./praxis_graphlaw_wasm_bg.js","name":"__wbindgen_object_drop_ref","kind":"function"},{"module":"./praxis_graphlaw_wasm_bg.js","name":"__wbg_getRandomValues_3f44b700395062e5","kind":"function"}]}
```

Existing local test suite for this seam, run this session:

```bash
.venv/bin/python -m pytest tests/sa2a/test_graphlaw_bridge.py -v
```
```
collected 2 items
tests/sa2a/test_graphlaw_bridge.py ..                                    [100%]
============================== 2 passed in 1.18s ===============================
```

This confirms `GraphLawBridge` itself is genuinely `ALIVE` locally today
(real Node.js subprocess, real local `praxis-graphlaw-wasm` build, real
BLAKE3 hash and validation output observed) — the defect this ticket reports
is not that the bridge is broken, but that its artifact-identity discipline
is absent while its functional behavior works.

Content-addressing code that **does** exist in this repo, for comparison
(the sixteen Chatman adapters, not graphlaw):

```bash
sed -n '38,57p' src/autofde_lab/wasm/_runtime.py
```
```
@dataclass(frozen=True, slots=True)
class ArtifactImage:
    filename: str
    sha256: str
    data: bytes

    @classmethod
    def from_descriptor(cls, descriptor: ComponentDescriptor, data: bytes) -> "ArtifactImage":
        digest = hashlib.sha256(data).hexdigest()
        if digest != descriptor.artifact_sha256:
            raise ArtifactIntegrityError(
                f"{descriptor.name} artifact digest mismatch: expected {descriptor.artifact_sha256}, observed {digest}"
            )
        if len(data) != descriptor.artifact_size:
            raise ArtifactIntegrityError(
                f"{descriptor.name} artifact size mismatch: expected {descriptor.artifact_size}, observed {len(data)}"
            )
        if not data.startswith(b"\x00asm\x01\x00\x00\x00"):
            raise ArtifactIntegrityError(f"{descriptor.name} is not a WebAssembly v1 module")
        data
```

### Local standing, scoped

- **`graphlaw_bridge.py` functional claim** ("the bridge drives a real
  local `praxis-graphlaw-wasm` build and produces real hook/validation
  output"): `ALIVE` — real command, real output, this session
  (`tests/sa2a/test_graphlaw_bridge.py`, 2 passed).
- **Content-addressed artifact-identity claim for the graphlaw seam**
  ("this repo verifies the graphlaw wasm module it loads matches a pinned
  hash before use"): **false**, confirmed by a real, currently-silent
  mismatch (see Chicago falsifiers, item 1). Not `PARTIAL_ALIVE` — this is
  a `BUILD_BROKEN`-in-spirit gap in a piece of state that currently reports
  no error at all, which is worse than a loud failure per
  `.claude/rules/absence-is-not-evidence.md`.
- **Zero-import / no-silent-host-authority claim for the graphlaw seam**:
  **false**, confirmed directly (see Chicago falsifiers, item 2). Honest
  classification: `BLOCKED:UNADMITTED_IMPORT` for this one law, locally.
- **A2A-2609 itself** (portable, content-addressed `graphlaw.wasm` across
  the ecosystem): `UNKNOWN` from this repo, by construction —
  `.claude/rules/ecosystem-boundary.md` gives this repo no admission,
  broker, or actuation authority to establish that claim, and this session
  touched no other repo in A2A-2609's owning list.

## Local closure work (fix implemented)

**Status change**: the "Required change" items 1 and 3 (item 2 — populating
`WasmComponentRef.artifact_sha256` from a real computed digest rather than a
hand-typed literal — remains a schema-level gap; see Remaining gap below) were
implemented this session, in `/Users/sac/autofde-lab` (confirmed via `pwd`
before any other action). This section documents the real fix, run this
session, not a plan.

### What changed

`src/autofde_lab/sa2a/admission/graphlaw_bridge.py`:

1. `EXPECTED_ARTIFACT_SHA256 = "187688d9e7e33a575713d6911d75687adb38713ed37412e211af263dfcbe0c28"`
   and `EXPECTED_ARTIFACT_SIZE = 3249361` are now pinned module constants —
   the real, confirmed digest and size of the local
   `praxis_graphlaw_wasm_bg.wasm` artifact.
2. `GraphLawBridge.__init__` now calls a new `_verify_artifact_integrity()`
   method, mirroring `wasm/_runtime.py`'s `ArtifactImage.from_descriptor`
   pattern rather than inventing a new one: computes the real SHA-256 of the
   loaded bytes, compares against `EXPECTED_ARTIFACT_SHA256`, checks
   `len(data)` against `EXPECTED_ARTIFACT_SIZE`, and checks the WebAssembly
   v1 magic prefix (`\x00asm\x01\x00\x00\x00`). Any mismatch raises a new
   typed `GraphLawArtifactIntegrityError` (a `RuntimeError` subclass) — a
   refusal, not a silent load. On success the verified digest is stored as
   `GraphLawBridge.artifact_sha256` (an actual computed value, available to
   any caller — e.g. for populating `WasmComponentRef.artifact_sha256` from
   a real bridge instance instead of a hand-typed literal).
3. `_verify_artifact_integrity()` also calls a new
   `_verify_ambient_imports()` method: it compiles the loaded bytes via a
   real Node.js subprocess (`WebAssembly.Module.imports()`, the same API
   used for the diagnosis in this ticket's Local verification section) and
   compares the real declared `(module, name)` import pairs against a new
   `ADMITTED_IMPORTS` frozenset, which explicitly and narrowly names the two
   real imports this artifact declares —
   `("./praxis_graphlaw_wasm_bg.js", "__wbindgen_object_drop_ref")` (wasm-
   bindgen glue) and
   `("./praxis_graphlaw_wasm_bg.js", "__wbg_getRandomValues_3f44b700395062e5")`
   (the host entropy-source binding named in this ticket's Problem section,
   item 4). Any import outside that set raises a new typed
   `GraphLawUnadmittedImportError` — so a future artifact rebuild that adds
   an unreviewed ambient capability (filesystem, network, shell) is refused
   rather than silently accepted, per A2A-2609 Law 4.

`tests/sa2a/test_cross_runtime_falsifier.py`: the hardcoded
`artifact_sha256="34fe50b8539067f4d47af577722744094e98b372b8774a643756265ec6bc7123"`
fixture value (falsified in this ticket's own Chicago falsifiers, item 1) was
corrected to the real, confirmed digest
(`187688d9e7e33a575713d6911d75687adb38713ed37412e211af263dfcbe0c28`), with a
docstring note on both the module and the changed line explaining why —
per this repo's fix-forward git workflow, the test was not weakened,
deleted, or had its rigor reduced; it now asserts a true fact instead of an
unchecked one, and would fail loudly (via `GraphLawBridge.__init__` raising
`GraphLawArtifactIntegrityError` before any assertion in the test body ever
ran) if it still carried the old, wrong value, since `GraphLawBridge()` is
now constructed with the real integrity check active.

`tests/sa2a/test_graphlaw_bridge.py`: one new falsifier test,
`test_graphlaw_bridge_refuses_tampered_artifact`, added (not replacing
either existing test). It performs a real `shutil.copytree` of the real
`PRAXIS_WASMPKG_DIR` into a pytest `tmp_path`, flips one real byte in the
copied `.wasm` file's real bytes (`bytearray` mutation + `write_bytes`, no
mocking), and asserts `GraphLawBridge(wasm_pkg_dir=tampered_pkg_dir)` raises
`GraphLawArtifactIntegrityError` matching `"digest mismatch"`.

### Remaining gap (not closed this session, named honestly)

`WasmComponentRef.artifact_sha256` (`src/autofde_lab/sa2a/exchange/
package.py:20`) is still a plain dataclass field with no automatic
population from a real `GraphLawBridge.artifact_sha256` value — nothing in
`SemanticExchangePackage` construction paths calls the bridge to populate it.
The bridge now *exposes* the real computed digest
(`GraphLawBridge(...).artifact_sha256`), which callers can use to populate
`WasmComponentRef` correctly, but no call site does so today (both
`test_graphlaw_bridge.py`'s existing tests and `test_cross_runtime_falsifier.py`
still hand-supply the digest as a literal — now the *correct* literal, not
an automatically-derived one). Wiring `SemanticExchangePackage` construction
to pull `artifact_sha256` from a live `GraphLawBridge` instance was out of
scope for this session's assigned fix (graphlaw_bridge.py + the two named
test files only) and is named here so it is not silently assumed closed.

### Local verification (this session)

```bash
cd /Users/sac/autofde-lab && pwd
```
```
/Users/sac/autofde-lab
```

Real grep for banned mock tokens over both touched test files — zero matches:

```bash
grep -rn "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" tests/sa2a/test_graphlaw_bridge.py tests/sa2a/test_cross_runtime_falsifier.py
```
```
(no output — zero matches, exit code 1)
```

Sanity check that the real bridge still constructs against the real local
artifact after the fix (real construction, real computed digest returned):

```bash
.venv/bin/python -c "
from autofde_lab.sa2a.admission.graphlaw_bridge import GraphLawBridge
b = GraphLawBridge()
print('artifact_sha256:', b.artifact_sha256)
"
```
```
artifact_sha256: 187688d9e7e33a575713d6911d75687adb38713ed37412e211af263dfcbe0c28
```

Required verification run, this session, real output:

```bash
.venv/bin/python -m pytest tests/sa2a/test_graphlaw_bridge.py tests/sa2a/test_cross_runtime_falsifier.py -v
```
```
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
plugins: anyio-4.14.0, nbmake-1.5.5, cov-7.1.0, xdist-3.8.0, timeout-2.4.0, cases-3.10.1
collected 4 items

tests/sa2a/test_graphlaw_bridge.py ...                                   [ 75%]
tests/sa2a/test_cross_runtime_falsifier.py .                             [100%]

============================== 4 passed in 2.77s ===============================
```

(`addopts = "-ra -q"` in `pyproject.toml` nets out the explicit `-v` to dot
output rather than per-test names — verified this is the repo's standing
pytest config, not a suppression introduced this session. 4 collected, 4
passed: the two pre-existing `test_graphlaw_bridge.py` tests, the new
`test_graphlaw_bridge_refuses_tampered_artifact` falsifier, and the corrected
`test_dual_runtime_falsifier_mutual_byte_verification`.)

### Local standing, scoped (this fix)

- **Content-addressed artifact-identity claim for the graphlaw seam**
  ("this repo verifies the graphlaw wasm module it loads matches a pinned
  hash before use"): `ALIVE` — real code path
  (`GraphLawBridge._verify_artifact_integrity`), real pinned digest, real
  refusal path exercised by a real tampered-byte falsifier test, all run
  this session (`test_graphlaw_bridge_refuses_tampered_artifact`, passed).
- **Zero-silent-ambient-import claim for the graphlaw seam** ("this repo
  refuses an artifact that declares an import outside an explicitly
  admitted set"): `PARTIAL_ALIVE` — the refusal code path
  (`_verify_ambient_imports`, `GraphLawUnadmittedImportError`) exists and is
  exercised on every `GraphLawBridge()` construction against the real
  artifact this session (both `test_graphlaw_bridge.py` and
  `test_cross_runtime_falsifier.py` construct real bridges that pass through
  this check without raising, confirming the admitted set is correct for the
  real artifact). Not full `ALIVE` for the *refusal* branch specifically:
  no falsifier test this session constructs a real WASM module with a
  genuinely unadmitted import and confirms `GraphLawUnadmittedImportError`
  fires (only the digest-mismatch refusal branch has a dedicated falsifier,
  per the assigned scope). Naming this gap rather than silently claiming
  full coverage, per `.claude/rules/absence-is-not-evidence.md`.
- **`WasmComponentRef.artifact_sha256` auto-population claim**: still
  `false`/not implemented — see Remaining gap above. Unchanged from the
  original ticket's diagnosis for this one item.
- **A2A-2609 itself**: still `UNKNOWN` from this repo, by construction,
  unchanged — this session touched no other repo in A2A-2609's owning list
  (`praxis`, `ggen`, `unrdf`).

## Local closure work, pass 2 (this session, 2026-09-16)

This pass closes both gaps named at the end of "Local closure work" (pass 1)
above: the missing `GraphLawUnadmittedImportError` falsifier, and
`WasmComponentRef.artifact_sha256` never being populated from a real
`GraphLawBridge` instance anywhere.

### Gap 1: `GraphLawUnadmittedImportError` falsifier

The real local artifact declares exactly the two imports already in
`ADMITTED_IMPORTS`, so no real artifact today trips the refusal branch
end-to-end through `GraphLawBridge()` alone. Per `.claude/rules/
testing-chicago-style.md` (monkeypatch/mock banned), the fix is not a fake --
it is a real, narrow refactor: `GraphLawBridge._verify_ambient_imports`
(`src/autofde_lab/sa2a/admission/graphlaw_bridge.py`) now takes an `admitted:
frozenset[tuple[str, str]] = ADMITTED_IMPORTS` parameter instead of reading
the module constant directly. The default preserves the exact existing
behavior for every current call site (`_verify_artifact_integrity` still
calls it with no override). A new test,
`test_graphlaw_bridge_refuses_unadmitted_import`
(`tests/sa2a/test_graphlaw_bridge.py`), builds a real, fully-constructed
`GraphLawBridge()` against the real artifact, reads the real artifact bytes
from disk, and calls the real `_verify_ambient_imports` method directly with
a real, hand-built `frozenset` that excludes one of the two real declared
imports (`__wbg_getRandomValues_3f44b700395062e5`). The real Node.js
subprocess really compiles the real bytes and really reports the real
imports; the observed-minus-admitted set is genuinely non-empty against that
narrowed set, and `GraphLawUnadmittedImportError` fires for real. No mocking
of the bridge, the subprocess, or the import list.

### Gap 2: `WasmComponentRef.artifact_sha256` auto-population

Real grep across `src/` and `tests/` for `WasmComponentRef(` found exactly
two constructor references in the whole repository:

```bash
grep -rn "WasmComponentRef(" --include="*.py" src/ tests/ | grep -v __pycache__
```
```
src/autofde_lab/sa2a/exchange/package.py:88:        wasm_ref = WasmComponentRef(**raw.get("wasm_component", {}))
tests/sa2a/test_cross_runtime_falsifier.py:51:        wasm_component=WasmComponentRef(
```

`package.py:88` is inside `SemanticExchangePackage.from_json`, a generic
deserializer over arbitrary JSON -- it does not construct a ref "for this
artifact"; it reconstructs whatever `artifact_sha256` was already present in
the JSON it is given. **No call site in `src/` constructs a fresh,
concrete `WasmComponentRef` for the praxis-graphlaw-wasm artifact with real
field values.** Stated honestly, per the task's own instruction, rather than
inventing one: this repo's production code has no such call site today.

The one real call site in the entire repository that does construct a
concrete `WasmComponentRef` for this artifact is
`tests/sa2a/test_cross_runtime_falsifier.py`
(`test_dual_runtime_falsifier_mutual_byte_verification`) -- exactly the
fixture the ticket's own "Remaining gap" note (pass 1, above) named as still
hand-supplying the digest as a literal. That is the call site this pass
wires: `GraphLawBridge()` is now constructed first in the test, and
`WasmComponentRef(..., artifact_sha256=py_bridge.artifact_sha256)` sources
the digest from the real, verified `GraphLawBridge.artifact_sha256` computed
against the real artifact bytes this test run, not a hand-typed literal. A
new assertion (`pkg.wasm_component.artifact_sha256 ==
py_bridge.artifact_sha256`) makes the wiring itself a checked, state-based
fact rather than an unverified refactor.

### Verification (this session)

```bash
cd /Users/sac/autofde-lab && pwd
```
```
/Users/sac/autofde-lab
```

Real grep for banned mock tokens over both touched test files -- zero
matches (first pass caught a false positive from this session's own
docstring literally containing the word "monkeypatch" while explaining it is
banned; reworded to avoid the literal token, since the grep is a blunt
string match and the repo convention is to say "no mocking" in prose, never
the banned token itself):

```bash
grep -rn "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" tests/sa2a/test_graphlaw_bridge.py tests/sa2a/test_cross_runtime_falsifier.py
```
```
(no output -- zero matches, exit code 1)
```

Required verification run, this session, real output:

```bash
.venv/bin/python -m pytest tests/sa2a/test_graphlaw_bridge.py tests/sa2a/test_cross_runtime_falsifier.py -v --basetemp=/tmp/afl_finishF
```
```
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
plugins: langsmith-0.12.1, anyio-4.14.0, nbmake-1.5.5, cov-7.1.0, xdist-3.8.0, timeout-2.4.0, Faker-40.36.0, cases-3.10.1
collected 5 items

tests/sa2a/test_graphlaw_bridge.py ....                                  [ 80%]
tests/sa2a/test_cross_runtime_falsifier.py .                             [100%]

============================== 5 passed in 3.64s ===============================
```

5 collected/passed (was 4 at end of pass 1): the two original
`test_graphlaw_bridge.py` tests, the pass-1
`test_graphlaw_bridge_refuses_tampered_artifact` falsifier, this pass's new
`test_graphlaw_bridge_refuses_unadmitted_import` falsifier, and the
`test_cross_runtime_falsifier.py` dual-runtime test (now wired to the real
bridge digest).

Regression check across the full `tests/sa2a/` tree (broader than the
task's required command, run for verification discipline -- distinguishing
pre-existing failures from anything this session introduced):

```bash
.venv/bin/python -m pytest tests/sa2a/ -v --basetemp=/tmp/afl_finishF_full
```
```
FAILED tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py::test_mutation_a_admission_content_not_bound_to_actuated_action_target
FAILED tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py::test_mutation_b_replay_reauthorized_for_different_action_returns_stale_receipt
FAILED tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py::test_mutation_c_execute_admitted_admission_gate_bypassed_on_replay
======================== 3 failed, 289 passed in 11.65s ========================
```

These 3 failures are **pre-existing, unrelated to this session's changes**:
`tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py` is
an untracked file that already existed at the start of this session (`git
status` at session start showed it `??`, and `src/autofde_lab/sa2a/brce/
boundary.py` already `M`, both from a prior session's uncommitted work on a
different subsystem -- the `ConsequenceBoundary`/BRCE admission gate, not
`graphlaw_bridge.py` or `exchange/package.py`). `git diff --stat` this
session touched only `src/autofde_lab/sa2a/admission/graphlaw_bridge.py`,
`tests/sa2a/test_graphlaw_bridge.py`, and `tests/sa2a/
test_cross_runtime_falsifier.py`; neither `boundary.py` nor the conformance
test file were read or edited this session. These 3 read as deliberately-red
mutation falsifiers documenting a real, separately-tracked admission-gate
defect (per their own assertion messages), not a build break this pass
caused.

### Local standing, scoped (pass 2)

- **`GraphLawUnadmittedImportError` refusal-branch claim** ("this repo
  refuses a real artifact declaring an import outside an explicitly admitted
  set, exercised by a dedicated falsifier"): `ALIVE` -- real bridge, real
  artifact bytes, real Node subprocess, real narrowed `admitted` frozenset,
  real refusal observed, this session (`test_graphlaw_bridge_refuses_
  unadmitted_import`, passed). The digest-mismatch and unadmitted-import
  refusal branches now both carry a dedicated falsifier; the gap named at
  the end of pass 1 is closed.
- **`WasmComponentRef.artifact_sha256` auto-population claim**: `PARTIAL_ALIVE`,
  scoped honestly. `ALIVE` for the one real call site that exists in the
  repository (`tests/sa2a/test_cross_runtime_falsifier.py`), now wired to a
  real `GraphLawBridge.artifact_sha256` and verified by a real passing
  assertion. Not `ALIVE` for a production (`src/`) call site, because none
  exists -- confirmed by real grep, not assumed. If a `src/` code path is
  later added that constructs a `SemanticExchangePackage`/`WasmComponentRef`
  for this artifact outside tests, it must be wired the same way; nothing
  currently does.
- **Pre-existing `tests/sa2a/conformance/test_afde_2604_...` failures**:
  `BUILD_BROKEN` for that file specifically, `UNKNOWN` cause from this
  session's scope (not investigated -- out of this task's assigned scope,
  named here only so it is not silently conflated with this pass's result).
- **A2A-2609 itself**: still `UNKNOWN` from this repo, by construction,
  unchanged -- this session touched no other repo in A2A-2609's owning list
  (`praxis`, `ggen`, `unrdf`).

## See also

- `/private/tmp/claude-501/-Users-sac-autofde-lab/805b2d1b-7d56-456a-b169-7ab879cabf6b/scratchpad/ash_a2a_tickets/A2A-2609-portable-graphlaw-wasm.md`
  — the remote ticket this document responds to; not owned by this repo.
- `AFDE-2607-cross-repo-seam-typing.md` (same directory) — the report-only,
  no-functional-change ticket pattern this document follows.
- `.claude/rules/ecosystem-boundary.md` — the boundary this ticket is
  scoped inside.
- `.claude/rules/standing-law.md` — the status vocabulary used in this
  document.
- `.claude/rules/absence-is-not-evidence.md`,
  `.claude/rules/no-dual-bookkeeping.md` — the local doctrine the Chicago
  falsifiers above are instances of (a declared field that was never
  checked against the thing it claims to identify).
- `docs/chatman-ecosystem-wasm.md`, `src/autofde_lab/wasm/_runtime.py`,
  `src/autofde_lab/wasm/_registry.py` — the sibling in-repo surface that
  already has the discipline this ticket says the graphlaw seam lacks; the
  Required change section proposes reusing this pattern rather than
  inventing a new one.
