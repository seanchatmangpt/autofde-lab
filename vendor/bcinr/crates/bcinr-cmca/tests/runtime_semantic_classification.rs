//! BCINR-CMCA-D: classifies, without changing, the mathematical operation
//! each of `bcinr-cmca`'s five numeric runtime surfaces actually realizes.
//!
//! # Non-interference (the law C's drift-check bug forced into existence)
//!
//! `Verify(A)` must not mutate `A`. C's first drift-check ran `ggen sync`
//! (which overwrites its target) and only then compared to `git diff` --
//! the repair happened before the verification, so a hand-edited file was
//! reported clean. This file is a pure-observation harness by construction:
//! every test calls a production function and asserts on its return value.
//! Nothing here writes a file, calls `ggen`, or mutates any state the five
//! surfaces below depend on. That is not a claim to re-verify each run --
//! it is true by what this file is capable of doing at all.
//!
//! # D1 inventory (built from code, not docs -- see the approved plan for
//! full file:line citations)
//!
//! | Surface | `q=0` zero-mass sibling | All-zero masses | Negative lens + zero mass | Production callers |
//! |---|---|---|---|---|
//! | `cascade::escort_weight` | `ONE` unconditionally -> sibling coverage | q=0: uniform. q>0: `DegenerateSiblingSet` if *all* zero. q<0: `ZeroMassUnderNegativeLens` | `ZeroMassUnderNegativeLens`, refuses | **None** |
//! | `cascade::consequence_mass`/`_traced` | delegates to `escort_weight` | same | same | **None** |
//! | `allocator::allocate`/`allocate_in` | `a_i = q*log2(mass)=0` when `q=0`, independent of mass -> sibling coverage | q=0: uniform. q!=0: silent divide-by-`ONE` fallback, no typed refusal | no dedicated check, silent (possibly saturated) result | **None** |
//! | `allocator::power` | `exp_eq_zero` branch returns `ONE` regardless of base -> sibling coverage | scalar, no vector branch | `exponent<0 & base=0` -> silently saturates to `MAX`, no fault flagged | Only via `escort_distribution` |
//! | `escort::escort_distribution` | integer path: sibling coverage (delegates to `escort_weight`) | q=0: uniform. q!=0 integer: `DegenerateNormalization`. q<0 fractional: `power` saturates the zero-mass element to `MAX`, no individual fault | integer: `ExactPathRefused` (names the exact node). **fractional: also refuses, but the saturated `MAX` overflows the summation, tripping a generic `DegenerateNormalization` instead -- both paths refuse, but only one names why** | **None** |
//!
//! Two findings that shape every classification below:
//! 1. All five surfaces agree on `q=0` sibling coverage -- the runtime is
//!    internally consistent here, not fractured. Whether that agrees with
//!    `~/mfw`'s Lean crown is checkpoint E's question, not D's.
//! 2. **Every one of these five surfaces has zero production callers
//!    today.** None can honestly be classified `PRODUCTION` authority.
// These tests deliberately exercise the `#[deprecated]` authority-chain types
// (`AdaptiveUpdate`, `CertifiedLearning`, receipts, ...) that CMCA-102 fences
// pending Hoare-logic verification. The crate's integration suite is the
// documented exception allowed to construct them (see lib.rs's INTEGRATION
// NOTE); this scoped allow keeps CI's `-D warnings` clippy gate green without
// un-deprecating the types for production callers.
#![allow(deprecated)]
// Exercises `cascade`/`escort`/`reference_escort` (alloc-gated modules): without
// the feature this target compiles to zero tests, keeping the default-feature
// matrix green instead of failing to resolve gated imports.
#![cfg(feature = "alloc")]

use bcinr_cmca::allocator::{
    allocate_in, power, AdaptiveUpdate, AdmittedControlState, CertificateReceipt,
    CertifiedLearning, EnvelopeReceipt, FeasibleRegion, OutcomeReceipt, StabilityRefusal,
};
use bcinr_cmca::cascade::{consequence_mass, escort_weight, CascadeRefusal, CascadeTree};
use bcinr_cmca::escort::{escort_distribution, EscortRefusal};
use bcinr_cmca::fixed::{NonNegativeFixed, SignedFixed};
use bcinr_cmca::generated::consequence_mass::case_studies::{
    ETA, LENS_REGISTRY, N, OBJECT_REGISTRY, Q,
};
use bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST;

// ---------------------------------------------------------------------
// D2: classification vocabulary (test-local -- see the plan for why this
// is not a new `src/` production API: finding 2 above means nothing in
// production would consume it).
// ---------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[allow(dead_code)] // SupportCoverage/Unclassified: no surface constructs these in this pass -- see module docs finding 1.
enum RuntimeSemanticKind {
    UniformSiblingCoverage,
    SupportCoverage,
    IntegerFixedPointEscort,
    FractionalPowerApproximation,
    AllocatorProjection,
    Unclassified,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[allow(dead_code)]
enum CorrespondenceStanding {
    MatchesNamedWitnesses,
    DivergesOnNamedWitness,
    Experimental,
    Unsupported,
}

fn mass(x: f64) -> NonNegativeFixed {
    NonNegativeFixed::from_bits((x * 65536.0).round() as u32)
}

fn q(x: f64) -> SignedFixed {
    SignedFixed::from_bits((x * 65536.0).round() as i32)
}

fn approx_eq(a: NonNegativeFixed, b: NonNegativeFixed, tol_bits: i64) -> bool {
    (a.to_bits() as i64 - b.to_bits() as i64).abs() < tol_bits
}

// ---------------------------------------------------------------------
// D3/D4: the [0,1,3] discriminator. Confirmed (via Explore agent grep)
// to not exist anywhere in this workspace before this file -- every
// existing zero-mass test uses *all*-zero siblings, which cannot
// distinguish support coverage ([0, 1/2, 1/2]) from sibling coverage
// ([1/3, 1/3, 1/3]) because both agree when every sibling is zero.
// ---------------------------------------------------------------------

const SUPPORT_COVERAGE: [f64; 3] = [0.0, 0.5, 0.5];
const SIBLING_COVERAGE: [f64; 3] = [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0];

fn assert_is_sibling_coverage_not_support_coverage(
    result: &[NonNegativeFixed],
    who: &str,
    kind: RuntimeSemanticKind,
) {
    assert_eq!(kind, RuntimeSemanticKind::UniformSiblingCoverage);
    assert_eq!(
        result.len(),
        3,
        "{who}: expected a 3-element [0,1,3] result"
    );
    for (i, (&got, &sibling)) in result.iter().zip(SIBLING_COVERAGE.iter()).enumerate() {
        let expected = mass(sibling);
        assert!(
            approx_eq(got, expected, 50),
            "{who}[{i}]: got {got:?}, expected sibling-coverage {expected:?} (not support-coverage {:?})",
            mass(SUPPORT_COVERAGE[i])
        );
    }
}

#[test]
fn cascade_escort_weight_is_uniform_sibling_coverage_at_q_zero() {
    // masses = [0, 1, 3], lens = 0, one weight per node, then normalize by hand.
    let masses = [NonNegativeFixed::ZERO, mass(1.0), mass(3.0)];
    let weights: Vec<NonNegativeFixed> = masses
        .iter()
        .enumerate()
        .map(|(i, &m)| escort_weight(m, 0, i).unwrap())
        .collect();
    let mut sum = NonNegativeFixed::ZERO;
    for &w in &weights {
        sum += w;
    }
    let shares: Vec<NonNegativeFixed> = weights.into_iter().map(|w| w / sum).collect();
    assert_is_sibling_coverage_not_support_coverage(
        &shares,
        "cascade::escort_weight",
        RuntimeSemanticKind::UniformSiblingCoverage,
    );
}

#[test]
fn consequence_mass_is_uniform_sibling_coverage_at_q_zero() {
    // root (mass=1, needed so root_total != 0) -> {a=0.0, b=1.0, c=3.0}.
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), NonNegativeFixed::ZERO, mass(1.0), mass(3.0)],
    )
    .unwrap();
    let result = consequence_mass(&tree, &[0]).unwrap();
    // result[0] is the root's own pass-through mass; result[1..4] are the
    // three children's shares of the root's ONE unit of flow.
    assert_is_sibling_coverage_not_support_coverage(
        &result[1..],
        "cascade::consequence_mass",
        RuntimeSemanticKind::UniformSiblingCoverage,
    );
}

#[test]
fn power_is_uniform_sibling_coverage_at_q_zero() {
    // power(base, 0) = ONE regardless of base -- D1 finding (b) for
    // allocator::power, including base=0. This IS the sibling-coverage
    // signature at the primitive level: every base, including zero,
    // contributes equal weight.
    let masses = [NonNegativeFixed::ZERO, mass(1.0), mass(3.0)];
    let weights: Vec<NonNegativeFixed> = masses
        .iter()
        .map(|&m| power(m, SignedFixed::ZERO))
        .collect();
    for w in &weights {
        assert_eq!(w.to_bits(), NonNegativeFixed::ONE.to_bits());
    }
    let mut sum = NonNegativeFixed::ZERO;
    for &w in &weights {
        sum += w;
    }
    let shares: Vec<NonNegativeFixed> = weights.into_iter().map(|w| w / sum).collect();
    assert_is_sibling_coverage_not_support_coverage(
        &shares,
        "allocator::power",
        RuntimeSemanticKind::UniformSiblingCoverage,
    );
}

#[test]
fn escort_distribution_integer_path_is_uniform_sibling_coverage_at_q_zero() {
    let masses = [NonNegativeFixed::ZERO, mass(1.0), mass(3.0)];
    let result = escort_distribution(&masses, SignedFixed::ZERO).unwrap();
    assert_is_sibling_coverage_not_support_coverage(
        &result,
        "escort::escort_distribution",
        RuntimeSemanticKind::UniformSiblingCoverage,
    );
}

/// `allocate_in`'s masses are not directly injectable -- they're derived
/// from the fixed `OBJECT_REGISTRY` via a formula over each object's
/// factors, not a per-call scalar array. But D1 established that `q=0`
/// makes `a_i = q*log2(mass) = 0` **regardless of mass value** -- so
/// isolating the `q=0` lens (`LENS_REGISTRY`'s real "LensCoverage" entry,
/// `q=0`) with a custom `lambda` that concentrates all weight there is
/// enough to test the same claim without needing an exact `[0,1,3]`
/// triple: at `q=0`, every leaf gets equal weight, independent of
/// `OBJECT_REGISTRY`'s real (nonzero) masses. This is the honest adaptation
/// of the `[0,1,3]` fixture to `allocate_in`'s actual API, not a weaker
/// substitute claim.
#[test]
fn allocate_in_is_uniform_sibling_coverage_at_q_zero() {
    // Confirm LENS_REGISTRY really has a q=0 ("LensCoverage") entry before
    // relying on it -- this test must not silently pass against a
    // different lens if the registry ever changes.
    let coverage_lens_idx = LENS_REGISTRY
        .iter()
        .position(|l| l.q.to_bits() == 0)
        .expect("LENS_REGISTRY must contain a q=0 lens for this test to isolate");

    let mut lambda = [[NonNegativeFixed::ZERO; Q]; 4]; // K=4, matches case_studies::K
    for row in &mut lambda {
        row[coverage_lens_idx] = NonNegativeFixed::ONE;
    }

    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N]; // flat forest: every node is its own root/leaf
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    let proof = AdaptiveUpdate::admit_adaptive_update(
        AdmittedControlState::admit_control_state(0),
        CertificateReceipt::admit_certificate(0),
        EnvelopeReceipt::admit_envelope(0),
        OutcomeReceipt::admit_outcome(0),
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ONE,
        CertifiedLearning::admit_learning(),
    );

    let result = allocate_in(
        &FeasibleRegion::CURRENT,
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &lambda,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        proof.as_ref(),
    )
    .unwrap();

    // Every node is a root (parent=[-1;N]) hence its own leaf, so a
    // uniform-sibling-coverage result means every entry is equal --
    // independent of OBJECT_REGISTRY's real, unequal, nonzero masses.
    let first = result[0];
    for (i, &v) in result.iter().enumerate() {
        assert!(
            approx_eq(v, first, 50),
            "allocate_in q=0 (coverage lens): node {i} = {v:?}, expected uniform with node 0 = {first:?} -- sibling coverage means equal weight independent of mass"
        );
    }
}

// ---------------------------------------------------------------------
// D4: divergence and experimental-standing classifications
// ---------------------------------------------------------------------

/// `escort_distribution`'s integer path already has a permanent proof of
/// bit-identical agreement with `cascade::escort_weight`
/// (`escort.rs::tests::exact_lens_never_reaches_the_approximate_path`,
/// added when the exact-lens dispatch was built). Cited here rather than
/// duplicated -- `CorrespondenceStanding::MatchesNamedWitnesses` for the
/// integer path is established fact, not re-derived.
#[test]
fn escort_distribution_integer_path_matches_cascade_escort_weight_is_already_proven() {
    // Sanity check that the cited test still exists and this claim isn't
    // citing a test that got renamed or removed out from under it.
    let masses = [mass(1.0), mass(2.0), mass(3.0), mass(4.0)];
    let lens = 3i32;
    let via_dispatch = escort_distribution(&masses, q(lens as f64)).unwrap();
    let exact_weights: Vec<NonNegativeFixed> = masses
        .iter()
        .enumerate()
        .map(|(node, &m)| escort_weight(m, lens, node).unwrap())
        .collect();
    let mut exact_sum = NonNegativeFixed::ZERO;
    for &w in &exact_weights {
        exact_sum += w;
    }
    let via_exact: Vec<NonNegativeFixed> =
        exact_weights.into_iter().map(|w| w / exact_sum).collect();
    assert_eq!(
        via_dispatch, via_exact,
        "bit-for-bit, not just within tolerance"
    );
}

/// (Previously `DIVERGES`, CMCA-109 fixed): the same `[0,1,3]`-shaped input
/// at a negative lens takes two different code paths inside
/// `escort_distribution` depending on whether the lens is an exact integer
/// or genuinely fractional. Before CMCA-109, they disagreed on *how
/// precisely* a zero-mass sibling's refusal was reported: the integer path
/// named the exact cause (`ExactPathRefused` wrapping cascade's
/// `ZeroMassUnderNegativeLens`), while the fractional path let `power`'s
/// zero-base/negative-exponent branch silently saturate to `MAX` tagged
/// "no fault," which only surfaced as a refusal indirectly (via the summed
/// weights overflowing) and with no trace back to which element or why.
///
/// CMCA-109 fixed `power` to tag `0^(negative)` with
/// `StabilityRefusal::UnsupportedDomain` instead of `err == u32::MAX`, so
/// the fractional path now refuses immediately at the offending element via
/// `EscortRefusal::NumericFault { index, .. }` -- still a different refusal
/// *shape* than the integer path's `ExactPathRefused` (this module's own
/// `EscortRefusal` doc explains why: `NumericFault`'s `error_code` is a
/// generic numeric-fault channel, `ExactPathRefused` preserves the richer
/// `CascadeRefusal` taxonomy), but no longer a loss of diagnostic
/// precision -- both paths now name the exact zero-mass element.
#[test]
fn escort_distribution_fractional_negative_lens_now_names_the_zero_mass_element() {
    let masses = [NonNegativeFixed::ZERO, mass(1.0), mass(3.0)];

    let integer_result = escort_distribution(&masses, q(-1.0));
    assert!(
        matches!(
            integer_result,
            Err(EscortRefusal::ExactPathRefused {
                reason: CascadeRefusal::ZeroMassUnderNegativeLens { .. },
                ..
            })
        ),
        "integer negative lens over a zero-mass sibling must refuse: got {integer_result:?}"
    );

    let fractional_result = escort_distribution(&masses, q(-1.5));
    assert!(
        matches!(
            fractional_result,
            Err(EscortRefusal::NumericFault { index: 0, .. })
        ),
        "CMCA-109: the fractional path must now refuse at the zero-mass element (index 0) \
         via NumericFault, not silently collapse to a generic DegenerateNormalization or -- \
         worse -- succeed. Got {fractional_result:?}"
    );
}

/// `CLASSIFIED` (CMCA-103 regression): the ontology-declared lens domain
/// (`q in [-2,2]`, `ontology/profile.ttl`) is an admission gate, and
/// `allocate_in` now refuses on it unconditionally -- regardless of
/// `proof.is_some()`/`proof.is_none()`. `proof=None` is the common path
/// exercised by nearly every other test in this crate; an out-of-range `q`
/// on that path must produce `Err(StabilityRefusal::QRangeDestabilizing)`,
/// not a silent accept. (Previously this test documented the opposite,
/// buggy behavior as EXPERIMENTAL/not-enforced; CMCA-103 fixed the
/// underlying gate at `allocate_in`'s `has_refusal` computation so that only
/// the learning-rate update -- not domain admission -- is proof-gated.)
#[test]
fn allocate_in_refuses_out_of_range_q_without_proof() {
    let mut lenses = LENS_REGISTRY;
    lenses[0].q = SignedFixed::from_bits(3 * 65536); // q=3, outside the declared [-2,2]

    let lambda = bcinr_cmca::generated::consequence_mass::case_studies::LAMBDA;
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    let result = allocate_in(
        &FeasibleRegion::CURRENT,
        &OBJECT_REGISTRY,
        &lenses,
        &lambda,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        None, // proof = None: the common path
    );

    assert!(
        matches!(result, Err(StabilityRefusal::QRangeDestabilizing)),
        "CMCA-103: with proof=None, an out-of-range q must now be refused as \
         QRangeDestabilizing regardless of proof.is_some()/is_none() -- got {result:?}"
    );
}

/// CMCA-103 update: this hostile `mu`/`costs` baseline is out of the
/// declared price domain (`price_err`), and `price_err` is one of the
/// selection-critical checks CMCA-103 made unconditional (it feeds directly,
/// unconditionally, into the pricing pass regardless of `proof`). It no
/// longer reaches Checkpoint A's degenerate-fallback-but-`Ok` regime on the
/// proof=None path; it is refused outright, exactly as it already was on
/// the proof=Some path. See `allocate_in`'s CMCA-103 comment.
#[test]
fn hostile_mu_cost_baseline_now_refuses_instead_of_degenerate_fallback() {
    let lambda = bcinr_cmca::generated::consequence_mass::case_studies::LAMBDA;
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];
    let mu = [NonNegativeFixed::from_bits(0u32.wrapping_sub(327680)); N];
    let costs = [NonNegativeFixed::ONE; N];

    let result = allocate_in(
        &FeasibleRegion::CURRENT,
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &lambda,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        None,
    );

    assert_eq!(
        result,
        Err(StabilityRefusal::PriceGainUnsafe),
        "CMCA-103: an out-of-domain price/mu must now refuse unconditionally instead of \
         hitting the degenerate-fallback-but-Ok regime -- got {result:?}"
    );
}

/// CMCA-103 update: `allocate_in` DOES now have a typed refusal
/// (`PriceGainUnsafe`) reachable for this input -- CMCA-103's fix made
/// `price_err` selection-critical and therefore unconditional. This
/// replaces the prior `EXPERIMENTAL` finding that no typed refusal existed
/// for this degenerate regime on the proof=None path.
#[test]
fn allocate_in_now_has_a_typed_refusal_for_the_former_degenerate_fallback_regime() {
    let lambda = bcinr_cmca::generated::consequence_mass::case_studies::LAMBDA;
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];
    let mu = [NonNegativeFixed::from_bits(0u32.wrapping_sub(327680)); N];
    let costs = [NonNegativeFixed::ONE; N];

    let result = allocate_in(
        &FeasibleRegion::CURRENT,
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &lambda,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        None,
    );

    assert_eq!(
        result,
        Err(StabilityRefusal::PriceGainUnsafe),
        "CMCA-103: this degenerate-but-not-cyclic input now has a typed refusal \
         (PriceGainUnsafe), not the prior silent-fallback-to-Ok -- got {result:?}"
    );
}

// ---------------------------------------------------------------------
// CMCA-110: `eta_err` only checked a lower bound (`ETA_G_MIN`); nothing
// enforced an upper bound, so `eta > 1.0` reached the explore-floor blend
// (`(NonNegativeFixed::ONE - eta_actual) * p_mu`) unconditionally, where
// `saturating_sub` underflows, silently clamps to 0, and discards the
// priced allocation for pure uniform explore with no refusal. Separately,
// `numeric_has_err` (the fold of `pi_res[x].err` across all 8 nodes --
// exactly where that underflow's fault flag lands) was bucketed into the
// proof-gated `has_error` instead of the unconditional
// `selection_critical_error`, so even a numeric fault from the
// unconditionally-executing selection code was swallowed on the common
// `proof=None` path. Both gaps are closed in `allocate_in`.
// ---------------------------------------------------------------------

/// CMCA-110 acceptance criterion 1 & 3: `eta > 1.0` with `proof=None` must
/// now be refused, not silently accepted with a uniform-explore result that
/// discarded the priced allocation via an unflagged underflow.
#[test]
fn allocate_in_refuses_eta_above_one_without_proof() {
    let lambda = bcinr_cmca::generated::consequence_mass::case_studies::LAMBDA;
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    // Just over 1.0 in Q16.16 -- the smallest out-of-domain value for a
    // blend-mixing coefficient, and exactly the value the ticket's
    // underflow analysis identifies as the first corrupting input.
    let eta_over_one = NonNegativeFixed::from_bits(NonNegativeFixed::ONE.val + 1);

    let result = allocate_in(
        &FeasibleRegion::CURRENT,
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &lambda,
        eta_over_one,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        None, // proof = None: the common path
    );

    assert!(
        result.is_err(),
        "CMCA-110: eta > 1.0 with proof=None must be refused, not silently degraded to an \
         unflagged uniform-explore result -- got {result:?}"
    );
    assert_eq!(
        result,
        Err(StabilityRefusal::ExploreFloorOutsideEnvelope),
        "CMCA-110: eta_err (now upper-bound-checked) must be the reason this refuses -- got \
         {result:?}. CMCA-122 gave eta_err its own dedicated reason instead of folding it \
         into LearningRateOutsideEnvelope."
    );
}

/// CMCA-110 acceptance criterion 4: `numeric_has_err` is now folded into
/// `selection_critical_error` (unconditional), not `has_error`
/// (proof-gated). This is verified at the arithmetic layer the ticket's
/// root-cause analysis names directly: the explore-floor blend's
/// `NonNegativeFixed::ONE - eta_actual` subtraction, which is exactly what
/// `pi_res[x].err`/`numeric_err`/`numeric_has_err` fold together in
/// `allocate_in`. This is an independent check from the `eta_err`
/// upper-bound gate above -- it confirms the *numeric* fault this
/// out-of-range `eta` produces is itself real and would be a genuine
/// second gate even if `eta_err` did not exist, not that the two fixes
/// coincidentally cover the same case only because they share an input.
#[test]
fn eta_above_one_underflows_the_explore_floor_blend_subtraction() {
    let eta_over_one = NonNegativeFixed::from_bits(NonNegativeFixed::ONE.val + 1);
    let underflowed = NonNegativeFixed::ONE - eta_over_one;

    assert_eq!(
        underflowed.err,
        StabilityRefusal::NumericRangeExceeded as u32,
        "CMCA-110: `NonNegativeFixed::ONE - eta_actual` must fault as \
         NumericRangeExceeded (not silently saturate to 0 unflagged) when eta > 1.0 -- this is \
         the numeric fault `numeric_has_err` folds and must surface as a refusal on the \
         proof=None path now that it is selection-critical"
    );
    assert_eq!(
        underflowed.val, 0,
        "CMCA-110: the underlying saturating_sub still clamps to 0 -- the fix is that the \
         resulting err flag now reaches has_refusal, not that the clamp itself changed"
    );
}

/// Documentation-as-test: records the D1 finding that all five surfaces
/// have zero production callers today. This is the test to update (not
/// silently delete) if any of them ever gains a real caller -- the point
/// is to make that fact loud when it changes, not to prevent it.
#[test]
fn all_five_surfaces_have_no_production_caller_as_of_bcinr_cmca_d() {
    // No executable assertion is possible for "no caller exists anywhere
    // in the workspace" from inside a single crate's test binary -- that
    // claim was established by a workspace-wide grep during BCINR-CMCA-D's
    // planning phase, not by anything this test can check at runtime.
    // This test exists so the claim has a permanent, named location in the
    // test suite rather than living only in a plan file or commit message.
    //
    // Surfaces confirmed production-caller-free as of this checkpoint:
    // cascade::escort_weight, cascade::consequence_mass/_traced,
    // allocator::allocate/allocate_in, allocator::power,
    // escort::escort_distribution.
}
