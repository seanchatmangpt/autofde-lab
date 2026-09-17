# AFDE-2607: this repo's typed seam for A2A-2607 (Blue River Dam cross-repo closure)

- **Status**: Open
- **Severity**: Low (local scope only — see Standing)
- **Standing**: `PARTIAL_ALIVE`
- **Owning repo(s)**: `seanchatmangpt/ggen`, `seanchatmangpt/ash_a2a`,
  `seanchatmangpt/unrdf`, `seanchatmangpt/affidavit` own A2A-2607 itself.
  **`autofde-lab` is explicitly NOT a primary owner of that closure.**
  `.claude/rules/ecosystem-boundary.md` frames this repo as one typed seam —
  "the search graph" — in a six-repo division of labour
  (`ggen-create` / `ggen` / `autofde-lab` / `bcinr-powl` / `mfw` /
  `ggen-legacy`), never the controller admitting, authorizing, or receipting
  a cross-repo flow. This ticket exists only to confirm this repo's own
  locally-exposed seam stays inside that boundary; it is not a contribution
  to the Dam's admission/CMCA/BRCE topology A2A-2607 actually describes.

## Problem

A2A-2607 requires every participant in the target topology
(`O -> O* -> classify -> CMCA -> {deterministic | SHLLM | idle estate |
frontier} -> candidate result -> admission -> construct -> authority ->
BRCE/DO -> receipt -> standing`) to expose a typed seam rather than prose
integration instructions, and (Law 3) that "no execution substrate may mint
authority." `autofde-lab` is a candidate execution substrate in that sense
(it computes candidate plans via `fabric/pddl_engine.py` and exposes an
external-tool surface via `openclaw_bridge.py`). The open question this
ticket answers locally: do either of those two modules, in their own source,
claim admission, authority, or receipt (in the admission-grade sense) for
themselves? If they did, that would be a live violation of A2A-2607 Law 3 and
of this repo's own `.claude/rules/actuation-boundary.md` and
`.claude/rules/ecosystem-boundary.md`.

## Required change (scoped to what this repo can honestly contribute)

None, as a code change — this ticket is a verification/confirmation pass, not
a remediation. The only artifact this repo can honestly produce toward
A2A-2607 is: (1) evidence that its own exposed seam (`pddl_engine.py`,
`openclaw_bridge.py`) is typed and non-consequence-bearing, run and pasted
this session, and (2) an honest note of any wording that risks drifting
readers toward admission semantics, even where the underlying code carries
none. This repo cannot contribute the cross-repo contract, the CMCA router,
or the BRCE/DO/receipt chain A2A-2607's Definition of Done actually requires
— those live in `mfw`, `ggen`, `bcinr-powl`, `ggen-legacy`, none of which
this session touched.

## Laws that actually apply locally

Restated from `.claude/rules/actuation-boundary.md` and
`.claude/rules/ecosystem-boundary.md` (this repo's own vocabulary for
A2A-2607 Law 3 and Law 4):

1. A planner result computed by `fabric/pddl_engine.py` is a candidate plan
   only — "performs no admission, emits no receipt, and actuates nothing"
   (module docstring, `pddl_engine.py:43-46`).
2. `openclaw_bridge.py` / `openclaw_runtime.py` emit a `receipt()` that is a
   SHA-256 **call-integrity digest** over canonicalized input/output JSON
   (`openclaw_runtime.py:71-93`: `receipt_id`, `timestamp`, `operation`,
   `subject`, `status`, `input_sha256`, `output_sha256`, `duration_ms`,
   `pid`, `python`) — no `authority`, `admitted`, or capability-grant field
   exists on that object. `src/autofde_lab/CLAUDE.md`'s own Non-authority
   section names this distinction explicitly: "Do not let the word 'receipt'
   in these modules drift into admission semantics."

## Chicago falsifiers

None added locally — this ticket makes no functional claim eligible for a
Chicago-style `solve()` falsifier per `.claude/rules/testing-chicago-style.md`.
The nearest real falsifier already exists upstream and was not re-run this
session: `integrations/openclaw/test/contract.test.mjs`, which exercises the
real compiled plugin end-to-end and asserts `REFUSED:*` typed statuses on
every failure branch (cited in `.claude/rules/actuation-boundary.md`).

## Definition of done (typed seam only, not cross-repo closure)

- [x] Read `.claude/rules/ecosystem-boundary.md` before writing any standing
      claim in this document.
- [x] Read `src/autofde_lab/fabric/pddl_engine.py` and
      `src/autofde_lab/openclaw_bridge.py` in full.
- [x] Ran the real grep below and pasted its real output.
- [x] Classified whether any matched line is a semantic-drift risk, named
      exactly.
- [ ] **Not done, out of scope for this repo**: the cross-repo machine-readable
      contract, the CMCA router, and the BRCE/DO/receipt chain A2A-2607's own
      Definition of Done requires. Those remain `UNKNOWN` from here by
      construction (`.claude/rules/ecosystem-boundary.md`; this repo has no
      admission, broker, or actuation authority to close them with).

This ticket never claims A2A-2607 itself is closed, advanced, or partially
closed by this repo. It closes only the narrower local question: is this
repo's own exposed seam typed and non-consequence-bearing, as A2A-2607 Law 3
requires of every participant.

## Local verification (this session)

Verification command (run from `/Users/sac/autofde-lab`, confirmed via `pwd`
before any other action):

```bash
grep -rn "authority\|admit\|receipt(" src/autofde_lab/fabric/ src/autofde_lab/openclaw_*.py
```

Real output (abridged to the two files this ticket scopes to — the fabric/
directory produced ~140 additional matches across other fabric modules
(`fde.py`, `brce.py`, `handoff.py`, `causal_placement.py`, `protocol_space.py`,
etc.) that are out of scope for this ticket and were not audited here; the
full raw output was inspected this session and none of the other fabric
modules were required reading by the task, so they are not re-analyzed
individually in this document):

```
src/autofde_lab/fabric/pddl_engine.py:9:(``mfw-planner/src/config.rs``) admits external planning engines under a
src/autofde_lab/fabric/pddl_engine.py:18:solver, so that a scikit-decide planner can be admitted the way any other
src/autofde_lab/fabric/pddl_engine.py:87:#: refusing, because a wrong plan can be admitted downstream. Refusing here
src/autofde_lab/openclaw_runtime.py:71:def receipt(
src/autofde_lab/openclaw_runtime.py:385:            "receipt": receipt(
src/autofde_lab/openclaw_runtime.py:400:            "receipt": receipt(
src/autofde_lab/openclaw_runtime.py:421:            "receipt": receipt(
src/autofde_lab/openclaw_bridge.py:282:            "receipt": runtime.receipt(
src/autofde_lab/openclaw_bridge.py:297:            "receipt": runtime.receipt(
src/autofde_lab/openclaw_bridge.py:312:            "receipt": runtime.receipt(
```

### Reading of the real output

- **`pddl_engine.py`**: all three `admit`-family hits describe an *external*
  system (`~/mfw`'s planner runner) admitting this engine's output — never
  this module admitting anything itself. No `authority` or `receipt(` token
  appears in this file at all. Consistent with its own docstring
  (`pddl_engine.py:43-46`): "performs no admission, emits no receipt, and
  actuates nothing." **No drift found.**
- **`openclaw_runtime.py` / `openclaw_bridge.py`**: zero `authority` or
  `admit` hits in either file. Every `receipt(` hit is a call to the same
  documented call-integrity digest function (`openclaw_runtime.py:71-93`),
  which carries `receipt_id`/`input_sha256`/`output_sha256`/`status`/
  `duration_ms` — no authority or admission field exists on the object.
  **No code-level drift found.**
- **One real, narrower wording risk, found by reading `openclaw_bridge.py`
  in full (not caught by the grep itself, since it doesn't match
  `receipt(`)**: the MCP `initialize` response's `instructions` string,
  `openclaw_bridge.py:162`, reads verbatim:

  ```python
  "instructions": (
      "Use registered subjects only; every call returns a receipt."
  ),
  ```

  This string is sent to any external MCP client that connects to this
  bridge. Read in isolation, "every call returns a receipt" carries no
  qualifier distinguishing a call-integrity digest from an admission-grade
  receipt — exactly the drift `src/autofde_lab/CLAUDE.md`'s Non-authority
  section warns against ("Do not let the word 'receipt' in these modules
  drift into admission semantics"). The underlying object itself is clean
  (no authority/admitted field, confirmed above); this is a documentation/
  protocol-wording risk for an external reader, not a functional defect. Not
  fixed in this session — out of scope (report-only ticket, no commits per
  task instructions) — flagged here as the one concrete finding.

### Local standing, scoped

- **Code-level claim** ("neither module claims admission, authority, or
  receipt semantics for itself"): `ALIVE` — real command, real output, read
  in full, zero contradicting lines found in either named file.
- **Wording-level risk** (external-facing `instructions` string undersells
  the call-integrity/admission distinction): open finding, unresolved this
  session → overall ticket standing `PARTIAL_ALIVE`, not `ALIVE`, until that
  string is qualified or a future pass explicitly accepts the risk as
  negligible.
- **A2A-2607 itself** (the cross-repo Dam closure): `UNKNOWN` from this repo,
  by construction — `.claude/rules/ecosystem-boundary.md` gives this repo no
  admission, broker, or actuation authority to establish that claim, and
  this session touched no other repo in the owning list.

## Closure update (2026-09-16) — wording-level finding resolved

The one open finding above (the MCP `initialize` response's `instructions`
string lacking a call-integrity qualifier) is now fixed forward. This
section documents the fix; the original finding above is left intact per
`docs/CLAUDE.md` invariant 2 ("historical corrections stay visible") — it is
not edited away, only superseded.

**Change made** (`src/autofde_lab/openclaw_bridge.py`, `_mcp_response`,
`initialize` branch — only this string was touched, nothing else in the
module):

```python
"instructions": (
    "Use registered subjects only; every call returns a receipt "
    "(a SHA-256 call-integrity digest over input/output, not an "
    "admission or authority grant)."
),
```

This restates, in the client-facing string itself, the exact distinction
`src/autofde_lab/CLAUDE.md`'s Non-authority section already required of the
underlying code ("Do not let the word 'receipt' in these modules drift into
admission semantics") — previously that distinction existed only in this
repo's own docs, not in the string an external MCP client actually receives.

**Test added** (fix-forward; no existing test asserted on this string's
content, so none needed to be changed — a new one was added):
`tests/test_openclaw_bridge.py::test_initialize_instructions_qualify_receipt_as_call_integrity_only`,
asserting the real, live `initialize` response's `instructions` field
contains `"call-integrity digest"` and `"not an admission or authority
grant"`, not merely that it mentions a receipt.

**Real verification, this session** (from `/Users/sac/autofde-lab`, `pwd`
confirmed before any other action):

```bash
grep -n "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" \
    tests/test_openclaw_bridge.py tests/test_openclaw_bridge_aliases.py
# exit 1 (zero matches) — Chicago-style discipline holds, no test doubles used

.venv/bin/python -m pytest tests/test_openclaw_bridge.py \
    tests/test_openclaw_bridge_aliases.py -v
# ============================== 25 passed in 1.17s ===============================
# (verbose per-test names, addopts cleared for the readback:)
# tests/test_openclaw_bridge.py::test_catalog_and_receipt_are_deterministically_shaped PASSED
# tests/test_openclaw_bridge.py::test_unregistered_subject_is_a_typed_refusal PASSED
# tests/test_openclaw_bridge.py::test_match_uses_only_registered_subjects PASSED
# tests/test_openclaw_bridge.py::test_direct_run_constructs_solves_and_rolls_out PASSED
# tests/test_openclaw_bridge.py::test_mcp_lifecycle_and_tool_call PASSED
# tests/test_openclaw_bridge.py::test_initialize_instructions_qualify_receipt_as_call_integrity_only PASSED
```

**Scope discipline**: only the `instructions` string in
`src/autofde_lab/openclaw_bridge.py` and the new test in
`tests/test_openclaw_bridge.py` were touched. No admission-boundary files
(`src/autofde_lab/sa2a/brce/boundary.py`,
`src/autofde_lab/sa2a/hooks/reactive_loop.py`, `src/autofde_lab/sa2a/cli.py`,
`src/autofde_lab/sa2a/brce/receipts.py`) were read for edit or modified —
that work stays a separate, paused decision. No commit, push, or PR was made
this session; this is a local file edit and local test run only, per task
instructions.

**Updated local standing**:

- **Wording-level risk**: resolved. The `instructions` string now carries
  the qualifier this section documents, verified by a real passing test
  this session.
- **Code-level claim** (unchanged from above): `ALIVE`.
- **A2A-2607 itself** (cross-repo Dam closure): still `UNKNOWN` from this
  repo, unchanged — this closure touched only this repo's own local seam
  wording, not any cross-repo contract, CMCA router, or BRCE/DO/receipt
  chain.
- **Overall ticket standing**: `ALIVE` for the narrower local question this
  ticket actually scopes to ("is this repo's own exposed seam typed,
  non-consequence-bearing, and honestly worded"). Still explicitly not a
  claim that A2A-2607 itself is closed, advanced, or partially closed by
  this repo — see "Definition of done" above, unchanged.

## See also

- `A2A-2607-blue-river-dam-cross-repo-closure.md` (remote ticket this
  document responds to; not owned by this repo).
- `.claude/rules/ecosystem-boundary.md` — the boundary this ticket is scoped
  inside.
- `.claude/rules/actuation-boundary.md` — the `receipt()` call-integrity vs.
  admission distinction cited above.
- `.claude/rules/standing-law.md` — the status vocabulary used in this
  document.
- `src/autofde_lab/CLAUDE.md` — Non-authority section, source of the "do not
  let the word receipt drift" warning verified here.
