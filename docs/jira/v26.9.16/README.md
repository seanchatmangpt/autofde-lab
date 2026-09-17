# autofde-lab v26.9.16 — AFDE local-closure ticket set

This directory turns the 2026-09-16 `A2A-26xx` cross-repository implementation
audit (the upstream ticket set at
`ash_a2a_tickets/README.md`) into a **local** ticket set — `AFDE-26xx` — scoped
to what this repository (`autofde-lab`) actually owns and can evidence.

`.claude/rules/ecosystem-boundary.md` is the reason these tickets are split
the way they are: this repo is "the search graph, nothing more" — candidate-plan
computation only. It has no admission, broker, actuation, or receipt authority
over anything outside its own process. So every `AFDE-26xx` ticket below is one
of two kinds, never a third thing that blends them:

1. A **real local closure surface** — the upstream `A2A-26xx` law has a genuine,
   testable analogue *inside this repo's own code*, and this session built,
   ran, and pinned a Chicago-style test against it.
2. A **thin consumer/seam ticket** — the upstream surface is owned by another
   repo (`ggen`, `mfw`, `bcinr`, `praxis`, `unrdf`, `ash_a2a` itself, or a
   cross-repo closure with no single owner), and this repo's role is limited to
   confirming what it does and does not claim about that surface from its own
   consumer position.

Collapsing that distinction — presenting all 9 tickets as equally-weighted
local closures — would itself be the kind of dual-bookkeeping
`.claude/rules/no-dual-bookkeeping.md` exists to forbid: a ticket whose real
standing is "not this repo's to close" does not become closed by writing a
ticket file about it.

## Real local closure surface vs. genuinely owned elsewhere

**5 of the 9 tickets have a real local closure surface in this repo**
(AFDE-2604, AFDE-2606, AFDE-2608, AFDE-2611, AFDE-2612). Each of these five had
a Chicago-style pytest file written and run against real in-repo code this
session — not a description, a real `pytest -v` invocation with real output
pasted into both the ticket and this README's standing table below.

**4 of the 9 tickets are genuinely owned elsewhere**, per
`.claude/rules/ecosystem-boundary.md`'s division of labour, and are recorded
here as thin consumer/seam findings only:

- **AFDE-2605** (CMCA resource-allocation control plane) — primary owner
  `ggen` / `bcinr`, per the upstream ticket and this repo's own
  `ecosystem-boundary.md`. This repo has a same-acronym, differently-scoped
  local module (`src/autofde_lab/cmca/`) that is real but is not the
  route-selector A2A-2605 requires.
- **AFDE-2607** (Blue River Dam cross-repo closure) — explicitly cross-repo by
  the upstream ticket's own framing; this repo is a consumer of the seam
  (`fabric/pddl_engine.py`, `openclaw_bridge.py`) and confirmed by grep that
  neither claims authority/admission semantics for itself, but the cross-repo
  Dam closure stays `UNKNOWN` here by construction.
- **AFDE-2609** (portable `graphlaw.wasm`) — primary owner `ggen` / `praxis`
  per `.claude/rules/ecosystem-boundary.md`'s own division table. This repo
  consumes a local `praxis-graphlaw-wasm` build via `GraphLawBridge` and found
  two real local gaps (hash-drift, non-zero-import) in that consumption, but
  the cross-repo deterministic-build/host-parity Definition of Done is not
  this repo's to close.
- **AFDE-2610** (AtomVM enterprise idle-compute estate) — primary owner
  `unrdf` per the upstream ticket. This repo has zero idle-estate/host-lease
  scheduling code (confirmed by grep) and one adjacent, much narrower local
  primitive (`openclaw_runtime.run_bounded`'s wall-clock ceiling) that was
  falsified for real but is not an idle-estate controller.

Every "genuinely owned elsewhere" ticket above still went through the same
gather-evidence-then-write discipline as the five local-closure tickets — real
greps, real reads, in some cases a real falsifier — but the resulting standing
is explicitly scoped as a **consumer/seam** finding, never claimed as closure
of the upstream law itself.

## Standing vocabulary

This repo's own vocabulary, per `.claude/rules/standing-law.md` — narrower and
stricter than the upstream ash_a2a set (`ALIVE` / `PARTIAL_ALIVE` /
`NOT_FOUND`), extended here with the additional statuses that vocabulary
requires:

- `ALIVE` — the declared consequence works and a command was actually run this
  session, with output observed, evidencing it.
- `PARTIAL_ALIVE` — a bounded working checkpoint exists but the larger claim
  does not follow from it yet.
- `BLOCKED:<reason>` — a named external prerequisite prevents lawful progress.
- `BUILD_BROKEN` — the relevant build or test suite fails.
- `UNKNOWN` — observation is insufficient to classify standing (not the same
  as `UNSUPPORTED`).
- `UNSUPPORTED` — the required capability or dependency is absent (an
  environment gate or missing optional extra), not incomplete work.
- `NOT_FOUND` — the named component was not evidenced anywhere in this repo by
  a real grep/read this session; predecessor primitives may still be `ALIVE`
  (same usage as the upstream ash_a2a README's `NOT_FOUND`).

No ticket here infers merge, publication, hosted CI, deployment, production
standing, or cross-repo closure from local source presence or local tests —
that is exactly what `.claude/rules/ecosystem-boundary.md` and
`.claude/rules/standing-law.md`'s three-dimension split
(`technicalStanding` / `organizationalStanding` / `enterpriseStanding`) forbid.

## Standing table

All 9 files confirmed present on disk via `ls docs/jira/v26.9.16/` before this
README cited any of them.

| ID | Surface | Local standing | Real local surface Y/N | Closure |
|---|---|---|---|---|
| [AFDE-2604](AFDE-2604-admission-fencing-local-closure.md) | admission → authority → DO fence | `PARTIAL_ALIVE` (defect confirmed `ALIVE`; fence itself `NOT_FOUND` in source) | Y | Composed 3-court fixture: law holds for admitted-not-authorized (`REFUSED_NO_GRANT`), fails for authorized-not-admitted — `ExecutionEnvelope` cannot carry an `AdmissionResult`. Laws #1/#3 remain `NOT_FOUND` as enforced behavior. |
| [AFDE-2605](AFDE-2605-cmca-selector-consumer-seam.md) | CMCA-shaped route selector | `NOT_FOUND` for the required 5-class selector; this repo's own same-name CMCA module is `PARTIAL_ALIVE` (differently scoped) | N (consumer/seam) | No closure claimed; primary owner `ggen`/`bcinr` per ecosystem-boundary.md. |
| [AFDE-2606](AFDE-2606-recursive-projection-closure.md) | recursive DME / projection candidate-only invariant | Per-boundary: `fabric/pddl_engine.py` and `fabric/powl.py` `ALIVE`; epoch/residual/recursion composition `NOT_FOUND` | Y | Law 6 (projection is candidate-only, never actuation) held: 4 passed. Cross-process determinism left `UNKNOWN`, named explicitly rather than assumed. |
| [AFDE-2607](AFDE-2607-cross-repo-seam-typing.md) | Blue River Dam cross-repo seam typing | `PARTIAL_ALIVE` (code-level non-authority claim `ALIVE`; one MCP-instructions wording-drift risk found) | N (consumer/seam) | A2A-2607 itself `UNKNOWN` from this repo by construction; cross-repo closure not owned here. |
| [AFDE-2608](AFDE-2608-projected-ephemeral-ontology-invariant.md) | projected-ephemeral ontology/constitution invariant | `PARTIAL_ALIVE` | Y | 3 passed. Real, pre-existing drift found (HTNDomain/HDDLDomain missing from committed ontology snapshot) — not fixed this pass, named as an open gap. |
| [AFDE-2609](AFDE-2609-wasm-artifact-discipline-consumer-seam.md) | portable `graphlaw.wasm` artifact discipline | `PARTIAL_ALIVE` (bridge functionally `ALIVE`; content-address + zero-import claims `FALSE`, both falsified for real) | N (consumer/seam) | A2A-2609 cross-repo Definition of Done (deterministic build, host parity) `UNKNOWN` here by construction; primary owner `ggen`/`praxis`. |
| [AFDE-2610](AFDE-2610-idle-estate-consumer-seam.md) | AtomVM enterprise idle-compute estate | Scoped, no blanket claim: idle-estate/host-lease/drain-deadline scheduling `NOT_FOUND`; resource-envelope hook on `Solver` `UNSUPPORTED`; `run_bounded()` timeout ceiling `ALIVE` | N (consumer/seam) | No idle-estate controller exists locally to close; primary owner `unrdf`. |
| [AFDE-2611](AFDE-2611-shllm-bounded-local-tier.md) | SHLLM bounded local UNKNOWN tier | `PARTIAL_ALIVE` | Y | Test skipped honestly (`dspy` not importable — `UNSUPPORTED`, not `BLOCKED`). No budget-bound code (`AllocationStanding.EXHAUSTED`) reachable from the one real local compile call site (`fabric/dspy.py:142`) — Law 4 has no live implementation to hold or fail. |
| [AFDE-2612](AFDE-2612-machine-experience-compile-back-closure.md) | Machine Experience compile-back (UNKNOWN → KNOWN) | `PARTIAL_ALIVE` | Y | 2 passed — zero-LLM-call claim held numerically on both real routes, but incidentally (content-blind hook fallback / exact-tuple authority match), not via genuine pattern-match detection. |

## Dependency order (real, local-only)

This is **not** a copy of the upstream 8-ticket dependency graph — most of
those edges cross repository boundaries this repo cannot verify or close.
The order below reflects only what this session's real evidence supports
*inside this repo*:

```text
AFDE-2604  admission -> authority -> DO fence   (foundational: defect confirmed,
    |                                            composed 3-court fixture pinned)
    |
    +--> AFDE-2612  Machine Experience compile-back
    |        depends conceptually on AFDE-2604 holding: today's zero-LLM-call
    |        result on the reflex-loop route is incidental (content-blind hook
    |        fallback), not gated on real admission — closing AFDE-2604's fence
    |        is a precondition for AFDE-2612's "promoted route is genuinely
    |        admission-checked" claim to become more than incidental.

AFDE-2608  projected-ephemeral ontology invariant   (foundational: ontology/
    |                                                 constitution generation
    |                                                 seam, independently verified
    |                                                 this session)
    |
    +--> AFDE-2612  Machine Experience compile-back
             the compiled/promoted KNOWN route AFDE-2612 manufactures is itself
             a generated artifact; AFDE-2608's projected-vs-source invariant
             bounds what that promotion is allowed to become.

AFDE-2606  recursive projection / candidate-only invariant
    (parallel to 2604/2608 — same projection-layer concern, no direct local
    edge to 2611/2612 found this session; upstream's 2606->2612 edge is
    cross-repo per ecosystem-boundary.md and not re-asserted here)

AFDE-2611  SHLLM bounded local tier
    (currently isolated locally: UNSUPPORTED on `dspy` blocks even an honest
    pass/fail signal, so no other local ticket can be said to depend on it
    holding yet)

AFDE-2605 / AFDE-2607 / AFDE-2609 / AFDE-2610
    (thin consumer/seam tickets — no local dependency edges asserted; each is
    a leaf pointing outward at ggen/bcinr/praxis/unrdf/ash_a2a per
    ecosystem-boundary.md, not a node this repo's local graph depends on)
```

The two foundational nodes are **AFDE-2604** (admission fencing) and
**AFDE-2608** (ontology invariant) because every other real local-closure
ticket either directly exercises the admission/authority path they define
(AFDE-2612) or shares their generation/projection seam (AFDE-2606). Nothing
in this local graph is claimed to converge on a Blue River Dam-style
cross-repo closure (AFDE-2607) — that remains `UNKNOWN` from this repo by
construction, per `.claude/rules/ecosystem-boundary.md`.

## Non-goals for this ticket set

Same non-goals as the upstream `ash_a2a` set, restated locally: no claim here
resolves Sybil-resistant identity issuance, universal program verification,
arbitrary external-system transactional atomicity, or unbounded distributed
planning. Additionally, and specific to this repo: no ticket here claims
`organizationalStanding` or `enterpriseStanding` per
`.claude/rules/standing-law.md` — every status in the table above is a
`technicalStanding` claim only, scoped to this repository's own process
boundary.

## Provenance

Every ticket file listed above, and the test files each cites
(`tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py`,
`tests/fabric/test_afde_2606_projection_candidate_only_closure.py`,
`tests/fabric/test_afde_2608_projected_ephemeral_invariant.py`,
`tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py`,
`tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py`),
were confirmed present on disk this session before being cited here. No git
commit, push, PR, or branch operation was performed while writing this
README or any of the ticket files it indexes — local file writes and local
`pytest` runs only.
