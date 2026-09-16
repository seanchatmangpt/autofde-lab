//! # CMCA: Chatman Multifractal Consequence Allocation
//!
//! `bcinr-cmca` is an authoritative systems library implementing deterministic,
//! branchless, and allocation-free algorithms for runtime telemetry, calibration,
//! monitoring, and cascade allocation (see [`allocator`]) of bounded computational
//! systems. "Covariance Monitoring and Calibration Assessment" was this crate's
//! earlier, calibration-only framing; see `docs/CMCA_EXPLANATION.md` for the
//! canonical-name reconciliation across this crate's calibration (`observatory`)
//! and cascade-allocation (`allocator`) responsibilities.
//!
//! Under the strict constraints of the **Radon Law** (Cyclomatic Complexity $CC=1$),
//! this module provides tools to audit the health and stability of mathematical
//! substrates without introducing timing side-channels, dynamic heap allocations,
//! or panic-prone execution paths.
//!
//! ## Architectural Foundations
//!
//! The crate enforces an autonomic feedback loop structured around the standard **MAPE-K**
//! (Monitor, Analyze, Plan, Execute, Shared Knowledge) control loop:
//! 1. **Observe**: Collect telemetry metrics (such as scaling factors, condition bounds, and drift metrics).
//! 2. **Infer**: Compute safety flags branchlessly using fixed-point arithmetic invariants.
//! 3. **Propose**: Report validation states indicating whether to proceed or trigger recertification.
//!
//! ## Key Modules
//!
//! * [`fixed`]: Q16.16 fixed-point arithmetic implementation designed for $CC=1$ operations.
//! * [`allocator`]: Linear bounds-checked and panic-free bump allocators.
//! * [`observatory`]: The evaluation engine that computes calibration safety flags based on mathematical thresholds.
//!
//! ## `allocator::allocate` is fixed to this crate's own `N=8`/`K=4`/`Q=4` shape (CMCA-108)
//!
//! [`allocator::allocate`] and [`allocator::allocate_single_lens`] -- this crate's
//! certified, branchless, allocation-free allocation path -- are compiled
//! against this crate's own object/measure/lens counts (`N = 8`, `K = 4`,
//! `Q = 4`, from `generated::consequence_mass::case_studies`), **not**
//! generic over caller-chosen sizes. A caller can supply different factor
//! *values* but not a different *shape* without this crate being
//! regenerated against a different `ontology/*.ttl`. See
//! [`allocator::allocate`]'s doc comment for why (the branchless kernel
//! beneath it unrolls against the literal constants 8/4/4) and for
//! [`cascade::consequence_mass`], the escape hatch for arbitrary tree
//! shapes.
//!
//! ## Which entry point do I want? (CMCA-119)
//!
//! Five overlapping ways to get an allocation share out of this crate --
//! this section is a navigation aid, not a restatement of each one's own
//! doc comment (follow the links below for the real detail):
//!
//! * [`allocator::allocate`] -- **start here** for the common case: one
//!   LAMBDA-weighted allocation vector across the whole `N`/`K`/`Q` object
//!   registry, evaluated against `FeasibleRegion::CURRENT`. See
//!   `examples/basic_allocation.rs` for a full runnable walkthrough.
//! * [`allocator::allocate_in`] -- the same computation as `allocate`, but
//!   over a caller-chosen [`allocator::FeasibleRegion`] instead of always
//!   `CURRENT`; use this when evaluating a hypothetical/candidate region
//!   rather than the live one.
//! * [`allocator::allocate_single_lens`] -- returns exactly one lens's
//!   allocation vector for one measure, bypassing the LAMBDA blend across
//!   all `K x Q` pairs; use this to inspect "what would lens `q` alone
//!   say" instead of the combined answer.
//! * [`cascade::consequence_mass`] (requires `alloc`) -- the escape hatch
//!   for tree shapes other than this crate's fixed `N = 8`/`K = 4`/`Q = 4`;
//!   use this when the object/measure/lens counts aren't the ones this
//!   crate was regenerated against.
//! * [`escort::escort_distribution`] (requires `alloc`) -- the
//!   fractional-exponent escort distribution `L_q(i) = p_i^q / SUM_j p_j^q`
//!   built directly on [`allocator::power`]; use this when you need an
//!   escort weighting over an arbitrary mass vector, independent of the
//!   object-registry allocation machinery above.
//!
//! ## Example Usage
//!
//! ```rust
//! use bcinr_cmca::fixed::NonNegativeFixed;
//! use bcinr_cmca::observatory::{evaluate_calibration, ObservatoryFlag};
//!
//! // Define typical parameters for telemetry monitoring
//! let kappa_hat = NonNegativeFixed::from_bits(131072);       // Estimated condition number (2.0)
//! let kappa_under = NonNegativeFixed::from_bits(131072);     // Lower bound condition number (2.0)
//! let epsilon_on = NonNegativeFixed::from_bits(65536);       // Upper limit threshold (1.0)
//! let gamma_min_plus_hat = NonNegativeFixed::from_bits(131072); // Estimated positive eigenvalue (2.0)
//! let gamma_min_plus_under = NonNegativeFixed::from_bits(131072); // Lower bound positive eigenvalue (2.0)
//! let epsilon_gram = NonNegativeFixed::from_bits(65536);     // Gram matrix threshold (1.0)
//! let d_js = NonNegativeFixed::ZERO;                         // Divergence/Drift measurement (0.0)
//! let epsilon_drift = NonNegativeFixed::from_bits(65536);    // Maximum allowed drift threshold (1.0)
//! let s_meas = NonNegativeFixed::ONE;                        // Measured scale (1.0)
//! let s_leaf = NonNegativeFixed::from_bits(32768);           // Leaf scale target (0.5)
//!
//! // Provide the artifact
//! use bcinr_cmca::observatory::{MeasurementArtifact, SupportStanding, ModeDelta};
//! use bcinr_cmca::allocator::CertificateReceipt;
//!
//! let artifact = MeasurementArtifact {
//!     point_estimate: kappa_hat,
//!     lower_bound: kappa_under,
//!     upper_bound: kappa_hat,
//!     support_standing: SupportStanding { is_supported: true, smoothing_applied: false },
//!     effective_sample_size: NonNegativeFixed::ONE,
//!     dependence_standing: 0,
//!     numeric_error: NonNegativeFixed::ZERO,
//!     drift: d_js,
//!     gram_lower_bound: gamma_min_plus_under,
//!     graph_digest: 0,
//!     control_mode_digest: 42,
//!     proposal: ModeDelta::ProposeDelta,
//! };
//!
//! // Evaluate the calibration state branchlessly
//! let status = evaluate_calibration(
//!     &artifact,
//!     epsilon_on,
//!     epsilon_gram,
//!     epsilon_drift,
//!     s_meas,
//!     s_leaf,
//! );
//!
//! // The production calibration succeeds, proposing recertification. Hostile
//! // mutation features intentionally alter this semantic surface and are verified
//! // by the dedicated isolated-mutant rails instead of this production example.
//! # if cfg!(any(
//! #     feature = "mutant_1", feature = "mutant_2", feature = "mutant_3",
//! #     feature = "mutant_4", feature = "mutant_5", feature = "mutant_6",
//! #     feature = "mutant_7", feature = "mutant_8", feature = "mutant_9",
//! #     feature = "mutant_10", feature = "mutant_11"
//! # )) { return; }
//! assert!(status.is_ok());
//! ```

#![cfg_attr(not(feature = "std"), no_std)]
#![deny(unsafe_code)]

#[cfg(feature = "std")]
extern crate std;

pub mod allocation_receipt;
pub mod allocator;
/// Arbitrary-shape multifractal cascade with a lens per level. Requires
/// `alloc`: unlike [`allocator`], it sizes to the tree rather than to a fixed
/// `N = 8`, so it cannot be allocation-free. See the module docs for why both
/// exist.
#[cfg(feature = "alloc")]
pub mod cascade;
/// Fractional-exponent escort distribution (`L_q(i) = p_i^q / SUM_j p_j^q`)
/// built on [`allocator::power`]. See the module docs for why this exists
/// alongside [`cascade::escort_weight`], which only covers integer `q`.
#[cfg(feature = "alloc")]
pub mod escort;
pub mod fixed;
pub mod generated;
/// Numeric-profile and policy constants generated by `ggen sync` from
/// `ontology/graph.ttl`. Do not hand-edit; edit the graph and regenerate.
pub mod generated_profile;
pub mod lrc;
pub mod observatory;
/// Hand-transcribed exact-rational reference oracle for the CMCA escort
/// distribution, mirroring `~/mfw`'s `MFW/CMCA/Semantics/Escort.lean`. Not a
/// machine-checked bridge -- see the module docs for exact scope.
#[cfg(feature = "alloc")]
pub mod reference_escort;
pub mod stability_theorem;

pub use allocator::{check_hierarchy_acyclic, HierarchyRefusal, StabilityRefusal};

// INTEGRATION NOTE (v26.7.24, re-fenced explicitly per CMCA-102 Branch B):
// Recovery-only authority modules (CertifiedLearning, CertifiedSelectionOnly,
// AdmittedControlState, CertificateReceipt, EnvelopeReceipt, OutcomeReceipt,
// AdaptiveUpdate) are defined in allocator.rs and deliberately NOT re-exported from
// this crate root. This top-level comment is now a pointer, not the fence itself:
// each of the 7 types carries its own `#[doc(hidden)]` attribute and doc comment at
// its definition site in allocator.rs, naming CMCA-102 and the unblocking condition
// (a Hoare-logic proof of the authority chain's dependency closure, per phd_gates.md
// / SAFETY.md conventions) directly on the gate. The types remain `pub` -- not
// `pub(crate)` -- because this crate's own integration-test suite
// (crates/bcinr-cmca/tests/*.rs) already depends on reaching them via
// `bcinr_cmca::allocator::*` as an external crate; `pub(crate)` would break that
// suite today. `#[doc(hidden)]` keeps them out of the crate's public-facing rustdoc
// listing (see CMCA-102's `cargo doc` acceptance criterion) without changing
// reachability or behavior. Recovery's new typed refusals (CMCA_LEARNING_FROZEN,
// etc.) will be added to StabilityRefusal as new enum variants once dependency
// closure is proven.

/// A branchless mock/dummy function utilized in tests and contract validation.
///
/// Under release profiles, this function compiles to a single wrapping addition
/// instruction without any conditional branches or memory accesses, conforming to $CC=1$.
///
/// # Examples
///
/// ```rust
/// use bcinr_cmca::dummy_branchless;
///
/// assert_eq!(dummy_branchless(42), 43);
/// assert_eq!(dummy_branchless(u64::MAX), 0);
/// ```
///
/// # Branchless Contract
///
/// ```text
/// u64_contract!(
///     requires: true,
///     ensures: true
/// )
/// ```
pub fn dummy_branchless(val: u64) -> u64 {
    val.wrapping_add(1)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dummy_branchless() {
        assert_eq!(dummy_branchless(0), 1);
        assert_eq!(dummy_branchless(42), 43);
        assert_eq!(dummy_branchless(u64::MAX), 0);
    }
}
