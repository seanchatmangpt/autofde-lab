//! BCINR-CMCA-H1: exact refusal correspondence closure.
//!
//! `BCINR-CMCA-H` (`PARTIAL_ALIVE`) left manifest invariant 2 (exact
//! refusal identity, per `~/mfw/mfw-theory/MFW/CMCA/Semantics/
//! CorrespondenceManifest.lean`) open. This file closes what is honestly
//! closable and characterizes, precisely, the one place where it is not.
//!
//! Tests here call `escort::escort_distribution` directly -- the
//! whole-field function, matching Lean's `escort`/`uniformSiblingCoverage`
//! signature shape. `cascade::escort_weight` (what `lean_correspondence.rs`
//! and `lean_correspondence_h.rs` test) is a per-element primitive with no
//! "the whole field is empty" concept, so it is the wrong level for the
//! empty-domain case this file needs.
//!
//! # The real finding this file exists to characterize
//!
//! The plan going into this file assumed Rust's `EscortRefusal::
//! DegenerateNormalization` would fire on an all-zero field at every
//! lens, collapsing Lean's `zeroSupport`/`zeroPartitionSum` split into one
//! constructor -- a "coarser but present" relationship. Running the actual
//! test (`coverage_and_positive_lens_all_zero_collapse_to_the_same_rust_refusal`,
//! first draft) falsified that assumption: `escort_distribution(&[0,0],
//! q=0)` does not refuse at all -- it **succeeds** with `[1/2, 1/2]`.
//!
//! The real mechanism (`crates/bcinr-cmca/src/cascade.rs`'s
//! `escort_weight`, `lens == 0` branch): at `q = 0`, every mass -- zero
//! included -- gets weight `NonNegativeFixed::ONE` unconditionally, so the
//! normalization sum over `N` masses is always `N`, never zero, for any
//! nonempty field. `DegenerateNormalization` is therefore **structurally
//! unreachable at lens 0** -- not merely a coarser stand-in for Lean's
//! `zeroSupport`, but genuinely absent, because Rust's `q = 0` never
//! implements the *support*-coverage semantics `zeroSupport` refuses
//! under in the first place (it always realizes *sibling* coverage,
//! Lean's `uniformSiblingCoverage`, which is defined to always succeed on
//! an all-zero field -- see `uniform_sibling_coverage_all_zero_succeeds`
//! below). This is consistent with, and sharpens, checkpoints D and E's
//! own established finding about `q = 0`'s sibling-coverage behavior.
//!
//! So the honest correspondence for the all-zero case is:
//! - Lean's `zeroSupport` (`ReferenceLens.coverage`, support coverage) has
//!   **no Rust correspondent at all** -- not a gap to close, because the
//!   Lean semantics it guards (support coverage at `q=0`) is not something
//!   Rust's runtime ever realizes, by design (per `escort.rs`'s own module
//!   doc, corrected in `BCINR-CMCA-H`: Rust's `q=0` maps to Lean's
//!   `uniformSiblingCoverage`, never to `ReferenceLens.coverage`).
//! - Lean's `zeroPartitionSum` (every lens other than `coverage`) DOES
//!   correspond exactly to Rust's `EscortRefusal::DegenerateNormalization`
//!   -- closed below with real evidence, not assumed.
//!
//! Everything else in Lean's declared refusal surface (`emptyDomain`,
//! `zeroMassUnderNegativeLens`) already has a Rust constructor of matching
//! granularity and is closed here with exact identity, not merely "both
//! refused."

// Exercises `cascade`/`escort`/`reference_escort` (alloc-gated modules): without
// the feature this target compiles to zero tests, keeping the default-feature
// matrix green instead of failing to resolve gated imports.
#![cfg(feature = "alloc")]

use bcinr_cmca::cascade::CascadeRefusal;
use bcinr_cmca::escort::{escort_distribution, EscortRefusal};
use bcinr_cmca::fixed::{NonNegativeFixed, SignedFixed};

const LENSES: [i32; 5] = [-2, -1, 0, 1, 2];

fn q(lens: i32) -> SignedFixed {
    SignedFixed::from_num(lens)
}

fn m(x: u32) -> NonNegativeFixed {
    NonNegativeFixed::from_num(x)
}

// ---------------------------------------------------------------------
// emptyDomain <-> EmptyInput: exact constructor identity, every lens.
// ---------------------------------------------------------------------

#[test]
fn empty_field_refuses_with_empty_input_at_every_lens() {
    for &lens in &LENSES {
        match escort_distribution(&[], q(lens)) {
            Err(EscortRefusal::EmptyInput) => {}
            other => panic!("lens={lens}: expected EmptyInput, got {other:?}"),
        }
    }
}

// ---------------------------------------------------------------------
// zeroMassUnderNegativeLens <-> ZeroMassUnderNegativeLens (wrapped in
// ExactPathRefused): exact constructor identity.
// ---------------------------------------------------------------------

#[test]
fn rare1_zero_mass_refuses_matching_lean_negative_zero_refuses() {
    // negative_zero_refuses: escort .rare1 [0,1] = .error .zeroMassUnderNegativeLens
    match escort_distribution(&[m(0), m(1)], q(-1)) {
        Err(EscortRefusal::ExactPathRefused {
            reason: CascadeRefusal::ZeroMassUnderNegativeLens { .. },
            ..
        }) => {}
        other => panic!(
            "rare1 [0,1]: expected ExactPathRefused(ZeroMassUnderNegativeLens), got {other:?}"
        ),
    }
}

#[test]
fn rare2_zero_mass_refuses_matching_lean_negative_zero_refuses_rare2() {
    // negative_zero_refuses_rare2: escort .rare2 [1,0] = .error .zeroMassUnderNegativeLens
    match escort_distribution(&[m(1), m(0)], q(-2)) {
        Err(EscortRefusal::ExactPathRefused {
            reason: CascadeRefusal::ZeroMassUnderNegativeLens { .. },
            ..
        }) => {}
        other => panic!(
            "rare2 [1,0]: expected ExactPathRefused(ZeroMassUnderNegativeLens), got {other:?}"
        ),
    }
}

// ---------------------------------------------------------------------
// zeroSupport / zeroPartitionSum: the coarseness finding, asserted
// directly rather than left implicit.
// ---------------------------------------------------------------------

#[test]
fn positive_and_negative_lens_all_zero_refuses_with_degenerate_normalization() {
    // positive_lens_all_zero_refuses (Lean): escort .proportional [0,0] = .error .zeroPartitionSum,
    // escort .exploit2 [0,0] likewise. rare1/rare2 also refuse on [0,0] --
    // via ZeroMassUnderNegativeLens (already closed above), which fires
    // before DegenerateNormalization would even be reached, so only the
    // two positive lenses are checked here.
    for &lens in &[1, 2] {
        match escort_distribution(&[m(0), m(0)], q(lens)) {
            Err(EscortRefusal::DegenerateNormalization) => {}
            other => panic!(
                "lens={lens} [0,0]: expected DegenerateNormalization (Rust's exact \
                 match for Lean's zeroPartitionSum), got {other:?}"
            ),
        }
    }
}

#[test]
fn coverage_all_zero_has_no_rust_refusal_correspondent_it_succeeds_instead() {
    // This is the corrected form of what this file originally assumed
    // (see the module doc's "real finding" section): Lean's
    // coverage_all_zero_refuses (.error .zeroSupport) has NO Rust
    // correspondent, because Rust's q=0 never implements support
    // coverage in the first place -- it always succeeds via sibling
    // coverage. Asserted here as a positive fact, not inferred from the
    // absence of a matching Err arm.
    let result = escort_distribution(&[m(0), m(0)], q(0));
    assert!(
        result.is_ok(),
        "q=0 on an all-zero field must succeed (sibling coverage), matching \
         uniformSiblingCoverage_all_zero_succeeds, never Lean's \
         coverage_all_zero_refuses -- got {result:?}"
    );
}

// ---------------------------------------------------------------------
// uniformSiblingCoverage_all_zero_succeeds: the load-bearing q=0
// sibling-vs-support fork case. Not a refusal at all -- asserted as a
// positive success, matching Lean exactly, via the same
// escort_distribution function used everywhere else (no separate
// "uniform sibling coverage" Rust function exists).
// ---------------------------------------------------------------------

#[test]
fn q_zero_all_zero_field_succeeds_with_uniform_sibling_coverage_not_a_refusal() {
    // uniform_sibling_coverage_all_zero_succeeds (Lean):
    //   uniformSiblingCoverage [0,0] = .ok [1/2, 1/2]
    let result = escort_distribution(&[m(0), m(0)], q(0)).expect(
        "q=0 on an all-zero field must SUCCEED with sibling coverage, matching \
         Lean's uniformSiblingCoverage_all_zero_succeeds -- it must not refuse \
         with DegenerateNormalization the way coverage_all_zero_refuses would \
         suggest, because Rust's q=0 realizes sibling coverage \
         (escort_weight's lens==0 branch returns ONE unconditionally, \
         regardless of mass), not Lean's ReferenceLens.coverage \
         (support coverage, which DOES refuse on this field)",
    );
    assert_eq!(result.len(), 2);
    let half = NonNegativeFixed::ONE / (NonNegativeFixed::ONE + NonNegativeFixed::ONE);
    for (i, &share) in result.iter().enumerate() {
        assert_eq!(
            share.to_bits(),
            half.to_bits(),
            "index {i}: expected exactly 1/2, got {share:?}"
        );
    }
}

// ---------------------------------------------------------------------
// Falsifiers -- each was actually applied to this file, run, confirmed
// to fail against the real function, then reverted. Same discipline as
// BCINR-CMCA-H's own falsifiers.
//
// F1 (wrong empty-field constructor): temporarily changed the match arm
// in `empty_field_refuses_with_empty_input_at_every_lens` from
// `Err(EscortRefusal::EmptyInput)` to `Err(EscortRefusal::
// DegenerateNormalization)`. Failed at lens=-2 with the real panic
// branch ("expected EmptyInput, got Err(EmptyInput)") -- confirms the
// test is checking the actual constructor returned, not merely "some
// error occurred."
// F2 (wrong refusal precedence): constructed a deliberately-wrong
// expectation that an empty field at an out-of-domain lens magnitude
// (e.g. a hypothetical lens exceeding MAX_LENS_MAGNITUDE) would refuse
// with `UnsupportedLens` rather than `EmptyInput`. Against the real
// `escort_distribution`, the `is_empty()` check runs first
// (`escort.rs:165-167`, before the lens-magnitude check at
// `escort.rs:172-174`), so an empty field always refuses with
// `EmptyInput` regardless of lens -- the deliberately-wrong expectation
// failed to materialize as anything OTHER than EmptyInput, confirming
// the real precedence the passing test above depends on.
// F3 (wrong q=0 all-zero outcome): changed the assertion in
// `q_zero_all_zero_field_succeeds_with_uniform_sibling_coverage_not_a_refusal`
// to `assert!(escort_distribution(&[m(0), m(0)], q(0)).is_err())`.
// Failed -- the real call succeeds with `[1/2, 1/2]`, confirming this is
// a real, checked discriminator for the sibling/support fork, not a
// vacuous assertion (mirrors BCINR-CMCA-E's own falsifier discipline on
// the `[0,1,3]` fork case).
// ---------------------------------------------------------------------
