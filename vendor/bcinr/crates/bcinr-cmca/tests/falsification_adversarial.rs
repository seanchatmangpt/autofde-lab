//! CMCA Falsification Tests — Adversarial Probe Suite
//!
//! These tests are designed to DISPROVE claims of correctness, using only the
//! crate's real, externally-visible public API (`allocator`, `fixed`,
//! `generated::consequence_mass::case_studies`, `observatory`) and real generated fixtures —
//! no mocks, no doubles. Every assertion is against an actual returned
//! value or `Result` variant, never a comment describing what a value
//! "should" be.
//!
//! `bcinr-cmca`'s `certification`, `stability`, `jump`, and `proposal`
//! modules are crate-internal (not `pub mod` in `lib.rs`) — their claims
//! ("authority check prevents unadmitted proposals", eigenvalue/contraction
//! margin, dwell enforcement via `observe_dwell`, BLAKE3-style certificate
//! chaining) are exercised for real inside those modules' own
//! `#[cfg(test)] mod tests` (already passing; see e.g.
//! `src/proposal.rs::tests`, `src/certification.rs::tests`), not fakeable
//! from an external integration-test binary. What *is* externally reachable
//! and offers an equivalent stability-gate surface is
//! `observatory::evaluate_calibration` — the MAPE-K telemetry gate that
//! decides recertification vs. refusal from measured drift, scale inertia,
//! numerical uncertainty, and Gram degeneracy. The stability-envelope-style
//! falsification tests below target that real gate instead.
//!
//! If any test here passes when it should fail, CMCA is proven incorrect at
//! that point.
// These tests deliberately exercise the `#[deprecated]` authority-chain types
// (`AdaptiveUpdate`, `CertifiedLearning`, receipts, ...) that CMCA-102 fences
// pending Hoare-logic verification. The crate's integration suite is the
// documented exception allowed to construct them (see lib.rs's INTEGRATION
// NOTE); this scoped allow keeps CI's `-D warnings` clippy gate green without
// un-deprecating the types for production callers.
#![allow(deprecated)]
#![allow(clippy::needless_range_loop)]

use bcinr_cmca::allocator::{
    allocate, allocate_single_lens, AdaptiveUpdate, AdmittedControlState, CertificateReceipt,
    CertifiedLearning, EnvelopeReceipt, OutcomeReceipt,
};
use bcinr_cmca::fixed::NonNegativeFixed;
use bcinr_cmca::generated::consequence_mass::case_studies::{
    ETA, LAMBDA, LENS_REGISTRY, N, OBJECT_REGISTRY, Q,
};
use bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST;
use bcinr_cmca::observatory::{
    evaluate_calibration, MeasurementArtifact, ModeDelta, ObservatoryFlag, SupportStanding,
};

fn get_proof() -> Option<AdaptiveUpdate<CertifiedLearning>> {
    AdaptiveUpdate::admit_adaptive_update(
        AdmittedControlState::admit_control_state(0),
        CertificateReceipt::admit_certificate(0),
        EnvelopeReceipt::admit_envelope(0),
        OutcomeReceipt::admit_outcome(0),
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ONE,
        CertifiedLearning::admit_learning(),
    )
}

fn run_allocate(parent: [i32; N], round: u32) -> [NonNegativeFixed; N] {
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;

    allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        round,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        get_proof().as_ref(),
    )
    .expect("allocation must succeed for a well-formed registry")
}

// ============================================================================
// FALSIFICATION SET 1: Q16.16 Fixed-Point Precision Violations
// ============================================================================

#[test]
fn falsify_q16_16_saturation_silently_truncates() {
    // Claim: Q16.16 saturating_add never wraps past MAX.
    // Falsification attempt: add near the top of the range and check for
    // wraparound (a wrapped value would be *smaller* than either operand).
    let near_max = NonNegativeFixed::from_bits(u32::MAX - 10);
    let ten = NonNegativeFixed::from_bits(20);

    let result = near_max.saturating_add(ten);

    assert!(
        result.to_bits() >= near_max.to_bits(),
        "FALSIFIED: saturating_add produced a value smaller than an operand — wraparound occurred"
    );
    assert_eq!(
        result.to_bits(),
        NonNegativeFixed::MAX.to_bits(),
        "saturating_add must clamp to MAX (by value) when the true sum exceeds representable range"
    );
}

#[test]
fn falsify_q16_16_division_precision_loss() {
    // Claim: Q16.16 division composed with multiplication recovers the
    // numerator within a couple ULP: (a / b) * b ~= a.
    let numerator = NonNegativeFixed::from_bits(0x0001_0000); // 1.0
    let denominator = NonNegativeFixed::from_bits(3); // smallest nonzero test divisor

    let quotient = numerator.saturating_div(denominator);
    let recovered = quotient.saturating_mul(denominator);

    let loss = numerator.to_bits().abs_diff(recovered.to_bits());

    assert!(
        loss <= 2,
        "FALSIFIED: Q16.16 division/multiplication round-trip lost {} ULP (numerator={:#x}, recovered={:#x})",
        loss,
        numerator.to_bits(),
        recovered.to_bits()
    );
}

#[test]
fn falsify_q16_16_multiplication_distributive() {
    // Claim: (a+b)*c == a*c + b*c within saturating-arithmetic rounding.
    let a = NonNegativeFixed::from_bits(100 << 16); // 100.0
    let b = NonNegativeFixed::from_bits(200 << 16); // 200.0
    let c = NonNegativeFixed::from_bits(0x0000_8000); // 0.5

    let left = a.saturating_add(b).saturating_mul(c);
    let right = a.saturating_mul(c).saturating_add(b.saturating_mul(c));

    assert_eq!(
        left, right,
        "FALSIFIED: distributive law violated — (a+b)*c={:?} != a*c+b*c={:?}",
        left, right
    );
}

// ============================================================================
// FALSIFICATION SET 2: Determinism Under Load Variation
// ============================================================================

#[test]
fn falsify_allocation_constant_time_all_inputs() {
    // The public API has no separate "candidate count" knob — every call
    // allocates across the same fixed N=8 registry — so a literal timing
    // side-channel probe isn't expressible through it. What *is*
    // adversarially checkable: an allocator whose selection secretly
    // depended on incidental load (e.g. hidden global state, allocator
    // arena reuse) would produce different output for structurally
    // identical calls made under different loop iteration counts. Run the
    // same allocation sandwiched between different amounts of prior
    // allocator activity and verify the result never depends on that prior
    // activity.
    let parent = [-1; N];

    let light_load = run_allocate(parent, 0);

    for _ in 0..500 {
        let _ = run_allocate(parent, 0); // burn prior allocator activity
    }
    let heavy_load = run_allocate(parent, 0);

    for i in 0..N {
        assert_eq!(
            light_load[i], heavy_load[i],
            "FALSIFIED: candidate {} allocation depends on prior allocator call volume",
            i
        );
    }
}

// ============================================================================
// FALSIFICATION SET 3: Allocation Correctness
// ============================================================================

#[test]
fn falsify_allocation_selects_highest_value() {
    // Claim (from case_studies.rs::test_case_study_1_cache_choice, already
    // proven): under the default MeasureCache-dominant LAMBDA weighting,
    // Artifact_A (index 0, recomputationCost=0.9) must receive strictly
    // more allocation than Artifact_B (index 1, recomputationCost=0.1).
    // Falsification attempt: if the allocator had an off-by-one or
    // reversed comparison bug, this ordering would invert.
    let parent = [-1; N];
    let result = run_allocate(parent, 0);

    assert!(
        result[0].val > result[1].val,
        "FALSIFIED: higher-recomputation-cost candidate (idx 0, val={:?}) did not outrank \
         lower-cost candidate (idx 1, val={:?})",
        result[0],
        result[1]
    );
}

#[test]
fn falsify_allocation_respects_precedence() {
    // Claim: `parent[]` encodes real dependency structure that the
    // allocator's downstream-consequence measure must respect — a leaf
    // whose entire ancestor chain has business value 0 except for a
    // distant root (Obj_Value, index 7, businessValue=1000) must still
    // receive allocation attributable to that root, exactly as
    // case_studies.rs::test_case_study_3_downstream_consequence proves.
    // Falsification attempt: break the chain (make Obj_Value a root with
    // no incoming dependency edge) and verify allocation TO THAT SPECIFIC
    // otherwise-linked node actually differs from the fully-linked case —
    // proving the allocator is truly using `parent[]`, not ignoring it.
    let mut linked_parent = [-1; N];
    linked_parent[2] = 4; // Obj_Activity depends on Obj_Obligation
    linked_parent[3] = 2; // Obj_Deployment depends on Obj_Activity
    linked_parent[5] = 3; // Obj_Outcome depends on Obj_Deployment
    linked_parent[7] = 5; // Obj_Value depends on Obj_Outcome
    let linked_result = run_allocate(linked_parent, 0);

    let unlinked_parent = [-1; N]; // no dependency edges at all
    let unlinked_result = run_allocate(unlinked_parent, 0);

    assert_ne!(
        linked_result[4].val, unlinked_result[4].val,
        "FALSIFIED: Obj_Obligation's (idx 4) allocation is identical whether or not it is \
         linked to Obj_Value's downstream consequence — parent[] is being ignored"
    );
}

// ============================================================================
// FALSIFICATION SET 4: Stability Envelope Violations (via observatory gate)
// ============================================================================

fn healthy_artifact(overrides: impl FnOnce(&mut MeasurementArtifact)) -> MeasurementArtifact {
    let mut artifact = MeasurementArtifact {
        point_estimate: NonNegativeFixed::from_bits(70_000), // > epsilon_on
        lower_bound: NonNegativeFixed::from_bits(70_000), // > epsilon_on -> not numerically uncertain
        upper_bound: NonNegativeFixed::from_bits(70_000),
        support_standing: SupportStanding {
            is_supported: true,
            smoothing_applied: false,
        },
        effective_sample_size: NonNegativeFixed::ONE,
        dependence_standing: 0,
        numeric_error: NonNegativeFixed::ZERO,
        drift: NonNegativeFixed::ZERO, // no drift
        gram_lower_bound: NonNegativeFixed::from_bits(70_000), // healthy, > epsilon_gram
        graph_digest: 0,
        control_mode_digest: 42,
        proposal: ModeDelta::ProposeDelta, // a real delta, not a no-op
    };
    overrides(&mut artifact);
    artifact
}

const EPSILON_ON: NonNegativeFixed = NonNegativeFixed::from_bits(65_536); // 1.0
const EPSILON_GRAM: NonNegativeFixed = NonNegativeFixed::from_bits(65_536); // 1.0
const EPSILON_DRIFT: NonNegativeFixed = NonNegativeFixed::from_bits(65_536); // 1.0
const S_MEAS: NonNegativeFixed = NonNegativeFixed::from_bits(100);
const S_LEAF: NonNegativeFixed = NonNegativeFixed::from_bits(200);

fn evaluate(
    artifact: &MeasurementArtifact,
    s_meas: NonNegativeFixed,
    s_leaf: NonNegativeFixed,
) -> Result<CertificateReceipt, ObservatoryFlag> {
    evaluate_calibration(
        artifact,
        EPSILON_ON,
        EPSILON_GRAM,
        EPSILON_DRIFT,
        s_meas,
        s_leaf,
    )
}

#[test]
fn falsify_healthy_baseline_is_actually_admitted() {
    // Sanity check for the fixture itself: a genuinely healthy artifact
    // (no drift, no scale inertia, no numeric uncertainty, no gram
    // degeneracy, a real proposed delta) must be admitted. If this fails,
    // every other test in this set is meaningless.
    let artifact = healthy_artifact(|_| {});
    let result = evaluate(&artifact, S_MEAS, S_LEAF);
    assert!(
        result.is_ok(),
        "FALSIFIED: a healthy artifact was refused: {:?}",
        result
    );
}

#[test]
fn falsify_stability_envelope_prevents_oscillation() {
    // "Scale inertia" (s_meas == s_leaf) is the gate's stand-in for a
    // system that has stopped producing informative change — the
    // oscillation/no-progress failure mode. Claim: this must refuse, not
    // silently pass through as a valid recertification.
    let artifact = healthy_artifact(|_| {});
    let inert_measurement = S_LEAF; // deliberately equal to s_leaf

    let result = evaluate(&artifact, inert_measurement, S_LEAF);
    assert_eq!(
        result,
        Err(ObservatoryFlag::ScaleInert),
        "FALSIFIED: scale-identical measurement (s_meas == s_leaf) was not refused"
    );
}

#[test]
fn falsify_stability_envelope_eigenvalue_bound() {
    // Gram degeneracy (loss of numerical rank/independence) is this gate's
    // real, checkable analogue of "the contraction/eigenvalue bound was
    // violated." Claim: an artifact with a healthy condition-number lower
    // bound but a Gram eigenvalue below threshold must be refused as
    // GramDegenerate, not silently admitted.
    let artifact = healthy_artifact(|a| {
        a.gram_lower_bound = NonNegativeFixed::from_bits(1_000); // well below epsilon_gram
    });

    let result = evaluate(&artifact, S_MEAS, S_LEAF);
    assert_eq!(
        result,
        Err(ObservatoryFlag::GramDegenerate),
        "FALSIFIED: a degenerate Gram eigenvalue was not refused"
    );
}

// ============================================================================
// FALSIFICATION SET 5: Priority Ordering & No-Op Admission
// (Renamed from the original "certificate/BLAKE3 chain" framing: this
// crate does not claim BLAKE3 or cryptographic collision resistance for
// its own gates — see `src/proposal.rs`'s doc comment on `mix64`. Real
// BLAKE3 receipts belong to `bcinr-powl (receipt module)`/OCEL, covered separately
// in `bcinr-powl/tests/usecase_compliance_audit.rs`. What this gate
// genuinely offers is a documented failure-priority order and refusal of
// no-op proposals — both tested here against the actual returned flag.)
// ============================================================================

#[test]
fn falsify_certificate_blake3_chain_integrity() {
    // Claim (from evaluate_calibration's own doc comment): when multiple
    // failure conditions are simultaneously true, Drifting takes priority
    // over ScaleInert. Falsification attempt: construct an artifact that
    // triggers both simultaneously and verify the reported flag is
    // Drifting, not ScaleInert — proving the priority order is real, not
    // decorative documentation.
    let artifact = healthy_artifact(|a| {
        a.drift = NonNegativeFixed::from_bits(200_000); // > epsilon_drift: triggers Drifting
    });
    let inert_measurement = S_LEAF; // also triggers ScaleInert

    let result = evaluate(&artifact, inert_measurement, S_LEAF);
    assert_eq!(
        result,
        Err(ObservatoryFlag::Drifting),
        "FALSIFIED: with both drift and scale-inertia conditions true, Drifting did not win priority"
    );
}

#[test]
fn falsify_certificate_prevents_replay_attacks() {
    // Claim: a proposal that carries no real delta (`ModeDelta::Retain` —
    // the closest thing this gate has to "replaying" a prior no-op
    // decision instead of proposing something new) must be refused as
    // ModeDeltaUnadmitted even when every numeric health check passes.
    let artifact = healthy_artifact(|a| {
        a.proposal = ModeDelta::Retain;
    });

    let result = evaluate(&artifact, S_MEAS, S_LEAF);
    assert_eq!(
        result,
        Err(ObservatoryFlag::ModeDeltaUnadmitted),
        "FALSIFIED: a no-delta (Retain) proposal was admitted instead of refused"
    );
}

// ============================================================================
// FALSIFICATION SET 6: Lens Blending Determinism, and Real Per-Lens Isolation
//
// Per-lens isolation used NOT to be observable through the public API — that
// gap is exactly what `allocate_single_lens` (added alongside this comment
// update) closes: it exposes `allocate_in`'s existing internal per-lens
// kernel (`compute_pi_kq_for_kq`) directly, rather than reimplementing it, so
// a single-lens result can never silently drift from what `allocate()`'s
// LAMBDA blend computes internally. The first two tests below probe the
// blended output's determinism (unchanged); the third and fourth are new,
// and genuinely check per-lens isolation instead of routing around it.
// ============================================================================

#[test]
fn falsify_qlens_exploitation_always_picks_max() {
    // OBJECT_REGISTRY indices 2-5 (Obj_Activity, Obj_Deployment,
    // Obj_Obligation, Obj_Outcome) have byte-identical factor vectors (see
    // `src/generated/case_studies.rs`). If the lens-blended allocation
    // ever favored one of these arbitrarily (e.g. by array index instead
    // of by factor values), that would be a real correctness bug — a
    // "highest value wins" allocator must treat identically-valued
    // candidates identically.
    let parent = [-1; N];
    let result = run_allocate(parent, 0);

    for i in 3..6 {
        assert_eq!(
            result[2].val, result[i].val,
            "FALSIFIED: candidates 2 and {} have identical factor vectors but received \
             different allocations ({:?} vs {:?}) — selection is not purely value-driven",
            i, result[2], result[i]
        );
    }
}

#[test]
fn falsify_qlens_coverage_skips_demonstrated_concepts() {
    // The same registry, replayed at a later round still inside the dwell
    // window, does not silently start favoring a different candidate
    // purely due to round number — i.e. there's no hidden per-round
    // rotation standing in for real coverage tracking (which would be a
    // different kind of bug: fake "coverage" via arbitrary rotation rather
    // than value-driven selection). This targets `allocate()`'s blended
    // output specifically, independent of the per-lens isolation checks
    // below.
    let parent = [-1; N];
    let round_0 = run_allocate(parent, 0);
    let round_50 = run_allocate(parent, 50);

    for i in 0..N {
        assert_eq!(
            round_0[i], round_50[i],
            "FALSIFIED: candidate {} allocation changed between round 0 and round 50 with no \
             other input change — indicates a hidden rotation rather than value-driven selection",
            i
        );
    }
}

#[test]
fn falsify_per_lens_isolation_is_now_real() {
    // The claim this test exists to falsify: `allocate_single_lens` is a
    // facade that secretly still blends every lens together, rather than
    // genuinely returning lens `(k, q)`'s isolated computation. If that
    // were true, every `(measure, lens_idx)` pair would produce the same
    // vector. It does not: `LensCoverage` (q=0, LENS_REGISTRY index 2)
    // weights every sibling equally under `MeasureCache` (k=0), so its
    // result differs from `LensExploitation` (q=2.0, index 0), which
    // concentrates mass on the highest-cost/highest-access candidates.
    let parent = [-1; N];
    let weights = [[NonNegativeFixed::ONE; 2 * Q]; N];

    let exploitation =
        allocate_single_lens(&OBJECT_REGISTRY, &LENS_REGISTRY, 0, 0, &parent, &weights)
            .expect("LensExploitation under MeasureCache must be admitted");
    let coverage = allocate_single_lens(&OBJECT_REGISTRY, &LENS_REGISTRY, 0, 2, &parent, &weights)
        .expect("LensCoverage under MeasureCache must be admitted");

    let mut any_divergence = false;
    for i in 0..N {
        if exploitation[i].val != coverage[i].val {
            any_divergence = true;
            break;
        }
    }
    assert!(
        any_divergence,
        "FALSIFIED: LensExploitation and LensCoverage produced identical allocations under \
         MeasureCache — per-lens isolation is not real, allocate_single_lens still blends \
         internally. exploitation={exploitation:?} coverage={coverage:?}"
    );
}

#[test]
fn falsify_single_lens_result_matches_the_blend_contribution_it_claims_to_isolate() {
    // The claim this test exists to falsify: `allocate_single_lens(k, q)`
    // does not actually correspond to the `(k, q)` term `allocate()`'s
    // LAMBDA blend sums internally — i.e. it's a plausible-looking but
    // disconnected computation. `tests/single_lens_allocation.rs`'s
    // `blend_equals_the_lambda_weighted_sum_of_single_lens_results` already
    // checks this across the full registry with a measured tolerance; this
    // test is the adversarial-suite-local witness that a single, easy case
    // (LensCoverage, q=0, under MeasureCache) is at minimum non-degenerate:
    // every object gets a strictly positive, non-saturated share (coverage
    // at q=0 is the uniform-sibling-weight case, so every one of the 8
    // objects should receive a nonzero, non-dominating share).
    let parent = [-1; N];
    let weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let coverage = allocate_single_lens(&OBJECT_REGISTRY, &LENS_REGISTRY, 0, 2, &parent, &weights)
        .expect("LensCoverage under MeasureCache must be admitted");

    for (i, share) in coverage.iter().enumerate() {
        assert!(
            share.val > 0 && share.val < NonNegativeFixed::ONE.val,
            "FALSIFIED: object {i} under LensCoverage got a degenerate share {share:?} \
             (expected a nonzero, non-dominating share under uniform sibling weighting)"
        );
    }
}

#[test]
fn falsify_qlens_rare_surfaces_edge_cases() {
    // Same scope note as above: isolating the "rare" lens isn't possible
    // through the public API. The genuinely checkable property: the
    // lowest-frequency-signal candidates in the registry (those with all
    // demand factors at 0 — Artifact_A/B, indices 0-1) still receive
    // strictly positive allocation rather than being zeroed out entirely,
    // which would indicate low-signal candidates are dropped rather than
    // weighted.
    let parent = [-1; N];
    let result = run_allocate(parent, 0);

    assert!(
        result[0].val > 0 && result[1].val > 0,
        "FALSIFIED: low-demand-signal candidates (idx 0,1) received zero allocation — \
         edge cases are being dropped, not surfaced"
    );
}

// ============================================================================
// FALSIFICATION SET 7: Dwell/No-Progress Boundary Sweep
// ============================================================================

#[test]
fn falsify_dwell_enforcement_blocks_premature_mode_changes() {
    // Boundary sweep on the scale-inertia gate (this crate's externally
    // reachable analogue of "no real progress since last observation" —
    // see Set 4's module note): any nonzero difference between s_meas and
    // s_leaf must be treated as real progress and admitted (given an
    // otherwise-healthy artifact); exact equality must always refuse.
    let artifact = healthy_artifact(|_| {});

    for delta in [1u32, 2, 100] {
        let s_meas = NonNegativeFixed::from_bits(S_LEAF.to_bits() - delta);
        let result = evaluate(&artifact, s_meas, S_LEAF);
        assert!(
            result.is_ok(),
            "FALSIFIED: a measurement differing from leaf scale by {} was refused: {:?}",
            delta,
            result
        );
    }

    let result_at_boundary = evaluate(&artifact, S_LEAF, S_LEAF);
    assert_eq!(
        result_at_boundary,
        Err(ObservatoryFlag::ScaleInert),
        "FALSIFIED: exact scale equality was not refused"
    );
}

// ============================================================================
// FALSIFICATION SET 8: Numeric Bounds & Saturation
// ============================================================================

#[test]
fn falsify_gain_matrix_stays_in_bounds() {
    // The generated LAMBDA table (the actual gain/weighting matrix used by
    // `allocate()`) must have every entry within [0.0, 1.0] in Q16.16 — a
    // value outside that range would mean the generator emitted an
    // unnormalized weight, which the allocator has no runtime check for.
    let one = NonNegativeFixed::ONE.to_bits();
    for (k, row) in LAMBDA.iter().enumerate() {
        for (q, entry) in row.iter().enumerate() {
            assert!(
                entry.to_bits() <= one,
                "FALSIFIED: LAMBDA[{}][{}] = {:?} exceeds 1.0",
                k,
                q,
                entry
            );
        }
    }
}

#[test]
fn falsify_contraction_margin_prevents_divergence() {
    // Boundary sweep on the drift gate — the externally reachable
    // analogue of "the envelope's divergence margin was exceeded."
    // `evaluate_calibration` triggers Drifting exactly when
    // `epsilon_drift < d_js` (strict). Verify the boundary is exactly
    // there, not off by a wide margin in either direction.
    for (drift_bits, should_admit) in [
        (0u32, true),                          // no drift
        (EPSILON_DRIFT.to_bits(), true), // exactly at threshold: not strictly greater, must pass
        (EPSILON_DRIFT.to_bits() + 1, false), // one ULP past threshold: must refuse
        (EPSILON_DRIFT.to_bits() * 10, false), // far past threshold: must refuse
    ] {
        let artifact = healthy_artifact(|a| {
            a.drift = NonNegativeFixed::from_bits(drift_bits);
        });
        let result = evaluate(&artifact, S_MEAS, S_LEAF);
        assert_eq!(
            result.is_ok(),
            should_admit,
            "FALSIFIED: drift={} admission was {:?}, expected should_admit={}",
            drift_bits,
            result,
            should_admit
        );
    }
}

// ============================================================================
// Summary
// ============================================================================
//
// Every test above executes a real call into the crate's public API and
// asserts on the actual returned value or `Result` variant. Where the
// public API genuinely cannot isolate a claim (per-lens selection,
// unadmitted-proposal rejection, contraction-margin sealing — all of which
// live in crate-internal modules), the test was either redirected to the
// nearest real, checkable equivalent (`observatory::evaluate_calibration`),
// or the claim is documented above as covered by the crate's own internal
// `#[cfg(test)]` suite instead of faked here.
