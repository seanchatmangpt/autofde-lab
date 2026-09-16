//! [`FeasibleRegion`]: `allocate_in`'s input bounds, extracted from inline
//! constants without changing allocation behavior. See `super::allocate_in`'s
//! docs for how each bound is actually used, and
//! [`FeasibleRegion::contains_allocation`]'s docs for why this is not also a
//! universally-enforced output contract.

use crate::fixed::NonNegativeFixed;
use crate::generated::consequence_mass::case_studies::N;
use crate::generated_profile::{
    ALLOCATOR_BETA_MAX_BITS, ALLOCATOR_MASS_MAX_BITS, ALLOCATOR_MASS_MIN_BITS,
    ALLOCATOR_PRICE_GAIN_MAX_BITS,
};

use super::StabilityRefusal;

/// The current allocator's four bounds, named and versioned. Field names
/// carry the operational-role distinction [`FeasibleRegion`]'s docs
/// establish: `beta_max`/`mass_min`/`mass_max` are clamp targets;
/// `price_gain_max` is the one bound that gates.
///
/// The four values are sourced from [`crate::generated_profile`] --
/// manufactured by `ggen sync` from `ontology/profile.ttl`'s
/// `bc:ProfileConstant` entries (`ALLOCATOR_BETA_MAX_BITS` and siblings).
/// Do not hand-edit those constants; edit the graph and regenerate. This
/// checkpoint (BCINR-CMCA-C) is preservation only: the four bit values are
/// unchanged from what `FeasibleRegion::CURRENT` hard-coded before this
/// type existed -- only where they come from changed.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct AllocatorRuntimeProfile {
    pub identity: &'static str,
    pub version: &'static str,
    pub beta_max: NonNegativeFixed,
    pub mass_min: NonNegativeFixed,
    pub mass_max: NonNegativeFixed,
    pub price_gain_max: NonNegativeFixed,
}

/// The allocator's admitted current profile.
pub const BCINR_CMCA_ALLOCATOR_V0_1: AllocatorRuntimeProfile = AllocatorRuntimeProfile {
    identity: "BCINR-CMCA-Allocator",
    version: "v0.1",
    beta_max: NonNegativeFixed::from_bits(ALLOCATOR_BETA_MAX_BITS),
    mass_min: NonNegativeFixed::from_bits(ALLOCATOR_MASS_MIN_BITS),
    mass_max: NonNegativeFixed::from_bits(ALLOCATOR_MASS_MAX_BITS),
    price_gain_max: NonNegativeFixed::from_bits(ALLOCATOR_PRICE_GAIN_MAX_BITS),
};

/// The numeric bounds `allocate_in` clamps or gates against, named rather
/// than inline. Two different kinds of bound, not one region:
///
/// `beta_max`, `m_min`, `m_max` are **clamp targets** -- `allocate_in`
/// applies them unconditionally (`beta = min(zeta, beta_max)`,
/// `node_masses[k][i] = clip(node_masses[k][i], m_min, m_max)`). There is no
/// input value for these three that produces a refusal instead of a silent
/// reshape; that has always been true of this function and this checkpoint
/// does not change it.
///
/// `mu_max` is the one bound among these four that already gates: any
/// `mu[i] > mu_max` sets `price_err`, which folds into `has_error` and
/// ultimately produces [`StabilityRefusal::PriceGainUnsafe`] (confirmed by
/// reading `allocate_in`'s `err_val` selection chain -- its final fallback
/// slot, index 7, *is* `PriceGainUnsafe`, not an unrelated default).
///
/// [`FeasibleRegion::admit_inputs`] therefore only checks `mu` against
/// `mu_max`: it is the only one of the four with an admission decision to
/// make. [`FeasibleRegion::contains_allocation`] checks a *related but
/// separate* output property -- see its own docs for why it is not the
/// universal postcondition an earlier version of this type assumed.
#[derive(Copy, Clone, Debug, PartialEq)]
pub struct FeasibleRegion {
    pub(super) beta_max: NonNegativeFixed,
    pub(super) m_min: NonNegativeFixed,
    pub(super) m_max: NonNegativeFixed,
    pub(super) mu_max: NonNegativeFixed,
}

impl FeasibleRegion {
    /// The bounds `allocate()` has always used, extracted rather than
    /// changed. `allocate(x) == allocate_in(&FeasibleRegion::CURRENT, x)`
    /// for every input, by construction: `allocate` is defined as that call.
    /// Sourced from `BCINR_CMCA_ALLOCATOR_V0_1` (BCINR-CMCA-C) -- the bit
    /// values are unchanged, only their origin.
    pub const CURRENT: Self = Self {
        beta_max: BCINR_CMCA_ALLOCATOR_V0_1.beta_max,
        m_min: BCINR_CMCA_ALLOCATOR_V0_1.mass_min,
        m_max: BCINR_CMCA_ALLOCATOR_V0_1.mass_max,
        mu_max: BCINR_CMCA_ALLOCATOR_V0_1.price_gain_max,
    };

    /// The profile's identity string -- the minimal additive surface a
    /// future allocator-side trace or receipt could bind to. Deliberately
    /// not a cryptographic digest (no const-time BLAKE3 is available in
    /// this crate) and deliberately not wired into any trace type here:
    /// `consequence_mass_traced` (the cascade's trace) does not consume
    /// this profile at all, and `allocate_in` has no trace type of its own
    /// to bind -- building one is a separate, checkpoint-sized decision.
    pub const fn profile_identity(&self) -> &'static str {
        BCINR_CMCA_ALLOCATOR_V0_1.identity
    }

    /// Absolute tolerance `contains_allocation` allows on the sum, matching
    /// the 1% figure `usecase_trading_determinism.rs`'s ad hoc test used
    /// before this contract existed (`NonNegativeFixed::ONE.val / 100`).
    const SUM_TOLERANCE_BITS: u32 = NonNegativeFixed::ONE.val / 100;

    /// Checks the one input bound among these four that `allocate_in`
    /// actually refuses on (see the struct docs): every `mu[i]` must not
    /// exceed `mu_max`. Mirrors `allocate_in`'s own `price_err` check
    /// exactly (`mu_max.val < mu[i].val`, strict), so a caller can decide
    /// not to call `allocate_in` at all rather than call it and discard an
    /// `Err`.
    pub fn admit_inputs(&self, mu: &[NonNegativeFixed; N]) -> Result<(), StabilityRefusal> {
        for &m in mu {
            if self.mu_max.val < m.val {
                return Err(StabilityRefusal::PriceGainUnsafe);
            }
        }
        Ok(())
    }

    /// Checks: every component nonnegative (guaranteed by
    /// `NonNegativeFixed`'s type, not checked here), none exceeds `ONE`, and
    /// the sum equals `ONE` within `Self::SUM_TOLERANCE_BITS`.
    ///
    /// **Not a universal postcondition of `allocate_in`.** It was written as
    /// one, wired into `allocate_in` as an automatic refusal gate, and that
    /// broke a real, correct, pre-existing test:
    /// `hostile_mutants.rs::verify_correctness_baselines`'s
    /// `CORRECT_MU_COST = [4096; N]` is a legitimate `allocate()` output
    /// (large `mu`/`costs` collapse `priced_sum` to zero, which forces the
    /// fallback `psd = ONE` branch -- the leaf sum in that branch is not
    /// renormalized to `ONE`, by design). Checkpoint A's plan explicitly
    /// forbids changing allocation behavior, so the automatic gate was
    /// reverted; this method is now a caller-invoked check for the
    /// non-degenerate regime (`priced_sum != 0`, the common case, e.g. the
    /// scenario `usecase_trading_determinism.rs`'s ad hoc 1%-tolerance
    /// assertion covers) -- call it when you know your inputs are in that
    /// regime, not as a blanket assumption about every `Ok` result.
    pub fn contains_allocation(&self, allocation: &[NonNegativeFixed; N]) -> bool {
        let mut sum: u64 = 0;
        for &a in allocation {
            if a.val > NonNegativeFixed::ONE.val {
                return false;
            }
            sum += a.val as u64;
        }
        let target = NonNegativeFixed::ONE.val as u64;
        sum.abs_diff(target) <= Self::SUM_TOLERANCE_BITS as u64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The normalized regime: components summing to (approximately) `ONE`.
    #[test]
    fn contains_allocation_true_for_a_normalized_distribution() {
        let allocation: [NonNegativeFixed; N] =
            core::array::from_fn(|_| NonNegativeFixed::from_bits(65536 / N as u32));
        assert!(FeasibleRegion::CURRENT.contains_allocation(&allocation));
    }

    /// The degenerate regime this method's docs cite by name:
    /// `hostile_mutants.rs::CORRECT_MU_COST`, a real, correct `allocate()`
    /// output whose sum is deliberately not close to `ONE` (large
    /// `mu`/`costs` collapse `priced_sum` to zero, forcing the
    /// non-renormalized `psd = ONE` fallback branch). `contains_allocation`
    /// must say `false` here -- if it said `true`, the method's own docs
    /// about what it does and does not guarantee would be wrong.
    #[test]
    fn contains_allocation_false_for_the_documented_degenerate_baseline() {
        const CORRECT_MU_COST: [u32; N] = [4096, 4096, 4096, 4096, 4096, 4096, 4096, 4096];
        let allocation: [NonNegativeFixed; N] =
            core::array::from_fn(|i| NonNegativeFixed::from_bits(CORRECT_MU_COST[i]));
        assert!(!FeasibleRegion::CURRENT.contains_allocation(&allocation));
    }

    /// [`FeasibleRegion::admit_inputs`] mirrors `allocate_in`'s own
    /// `price_err` check: `mu_max` is a strict ceiling (`mu_max.val < m.val`
    /// refuses; `mu.val == mu_max.val` is admitted).
    #[test]
    fn admit_inputs_refuses_mu_strictly_above_mu_max() {
        let mut mu = [NonNegativeFixed::ZERO; N];
        mu[3] = NonNegativeFixed::from_bits(FeasibleRegion::CURRENT.mu_max.val + 1);
        assert_eq!(
            FeasibleRegion::CURRENT.admit_inputs(&mu),
            Err(StabilityRefusal::PriceGainUnsafe)
        );
    }

    #[test]
    fn admit_inputs_admits_mu_at_or_below_mu_max() {
        let mut mu = [NonNegativeFixed::ZERO; N];
        mu[3] = FeasibleRegion::CURRENT.mu_max;
        assert!(FeasibleRegion::CURRENT.admit_inputs(&mu).is_ok());
    }

    /// BCINR-CMCA-C law 2 (profile fidelity): the exact literal bit values
    /// this type held before the ggen-manufactured profile existed. A
    /// change to `ontology/profile.ttl` that alters one of these values
    /// must fail this test, not just the drift check -- a Rust-level
    /// tripwire independent of remembering to run `ggen sync`/diff.
    #[test]
    fn current_profile_preserves_exact_q16_bits() {
        assert_eq!(BCINR_CMCA_ALLOCATOR_V0_1.beta_max.to_bits(), 6553);
        assert_eq!(BCINR_CMCA_ALLOCATOR_V0_1.mass_min.to_bits(), 6);
        assert_eq!(BCINR_CMCA_ALLOCATOR_V0_1.mass_max.to_bits(), 65536000);
        assert_eq!(BCINR_CMCA_ALLOCATOR_V0_1.price_gain_max.to_bits(), 6553600);
    }

    /// Wiring check, not a value check: `FeasibleRegion::CURRENT` and
    /// `BCINR_CMCA_ALLOCATOR_V0_1` are both `const`-derived from the same
    /// generated constants, so this cannot catch a wrong *value* (a bit
    /// mutation moves both sides together -- confirmed by running this
    /// exact mutation during BCINR-CMCA-C's falsifier pass; only
    /// `current_profile_preserves_exact_q16_bits` catches that). What this
    /// catches is `CURRENT` being wired to some other literal or a
    /// different field entirely.
    #[test]
    fn feasible_region_current_matches_allocator_profile() {
        assert_eq!(
            FeasibleRegion::CURRENT.beta_max,
            BCINR_CMCA_ALLOCATOR_V0_1.beta_max
        );
        assert_eq!(
            FeasibleRegion::CURRENT.m_min,
            BCINR_CMCA_ALLOCATOR_V0_1.mass_min
        );
        assert_eq!(
            FeasibleRegion::CURRENT.m_max,
            BCINR_CMCA_ALLOCATOR_V0_1.mass_max
        );
        assert_eq!(
            FeasibleRegion::CURRENT.mu_max,
            BCINR_CMCA_ALLOCATOR_V0_1.price_gain_max
        );
    }

    #[test]
    fn profile_identity_is_queryable() {
        assert_eq!(
            FeasibleRegion::CURRENT.profile_identity(),
            "BCINR-CMCA-Allocator"
        );
    }
}
