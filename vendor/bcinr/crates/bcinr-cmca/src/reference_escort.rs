//! Hand-transcribed exact-rational reference oracle for the CMCA escort
//! distribution, mirroring `~/mfw`'s `MFW/CMCA/Semantics/Escort.lean`
//! (`CMCA-Escort-v0.1`).
//!
//! # Scope and what this is NOT
//!
//! This module is a **hand-transcription**, not a machine-checked bridge.
//! There is no FFI, no code generation, and no export path connecting the
//! Lean file at `~/mfw/mfw-theory/MFW/CMCA/Semantics/Escort.lean` to this
//! Rust crate: the correspondence between the two is established only by a
//! human reading the Lean source and typing out the equivalent Rust by hand,
//! then checking the result differentially against the fixed-point
//! implementation in [`crate::escort`] and [`crate::cascade`]
//! (`tests/cmca_h_lean_correspondence.rs`, in this crate's `tests/`
//! directory). That differential test is evidence of agreement within a
//! measured tolerance; it is not a proof that this module matches the Lean
//! definitions, and it is not a proof that the fixed-point crate matches
//! this module. Nothing here should be cited as "formally verified" or
//! "proven" correspondence.
//!
//! Every function below cites the exact line range in Escort.lean it
//! transcribes, as of the commit this module was written against
//! (`e6a69a0c`, "CMCA-Escort-v0.1").
//!
//! # Relationship to the other two `BCINR-CMCA-*` correspondence files
//!
//! `~/mfw`'s `MFW/CMCA/Semantics/CorrespondenceManifest.lean` (`MFW-CMCA-005`)
//! independently freezes seven correspondence invariants a Rust checkpoint
//! must be able to test, naming Lean's own kernel-checked golden vectors and
//! theorems directly. This crate closes all seven across three files, each
//! with a different evidentiary shape -- read together, not redundantly:
//!
//! * `tests/lean_correspondence.rs` (`BCINR-CMCA-E`) -- invariant 1 (exact
//!   output equality) and the `q=0` fork (invariant 5), by asserting
//!   `cascade::escort_weight` against Lean's literal `[1,2,3,4]`/`[0,1,3]`
//!   golden-vector values, copied verbatim from the proved theorems.
//! * `tests/lean_correspondence_h.rs` -- invariants 3, 4, 6, 7 (scale
//!   invariance, permutation equivalence, pairwise concentration, strict
//!   extrema movement on `[1,2,10]`), plus the two new small-field witnesses
//!   (`[1]`, `[1,1]`) the manifest added specifically for this checkpoint --
//!   same golden-vector-literal method as E, extended to the invariants E
//!   didn't cover.
//! * `tests/cmca_h_lean_correspondence.rs` (this module's own differential
//!   suite) -- invariant 2 (exact refusal identity, all four Lean refusal
//!   constructors, not just E's partial `zeroMassUnderNegativeLens` case)
//!   plus a broader differential sweep against the *independently
//!   transcribed* oracle above, rather than against literal copied
//!   constants -- this is what catches a bug that a copy-paste of Lean's
//!   own golden vectors could not (a shared transcription error between the
//!   test's expected value and the oracle it was copied from).
//!
//! None of the three files was written with knowledge of the other two from
//! the start -- `lean_correspondence_h.rs` was written first, directly
//! against the manifest; this module and its differential suite were
//! written afterward without initially cross-referencing it, and were
//! reconciled together after the fact. Recorded here so a future reader
//! doesn't have to reconstruct that history.
//!
//! # Exact rationals
//!
//! `~/mfw` uses Lean's arbitrary-precision `ℚ`. This module has no such
//! type available, so it implements a minimal `i128`-numerator/denominator
//! `ExactRational` with checked (overflow-detecting) arithmetic, sufficient
//! for the mass magnitudes exercised by this crate's existing tests and by
//! `tests/cmca_h_lean_correspondence.rs`. `num-rational` is not a workspace
//! dependency (checked in `Cargo.lock` before writing this module), so no
//! new external dependency was added.

extern crate alloc;

use alloc::vec::Vec;
use core::cmp::Ordering;

/// A minimal exact rational, `numerator / denominator`, always kept with
/// `denominator > 0` and reduced to lowest terms. Arithmetic is checked:
/// any operation whose `i128` intermediate would overflow returns `None`
/// (surfaced as [`ReferenceEscortRefusal`] is NOT how overflow is reported
/// here — see the `checked_*` methods; this type has no runtime input from
/// untrusted external sources within this module's own use, since masses
/// are `u64` and lenses are closed, but the checked API is kept honest
/// rather than silently wrapping).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExactRational {
    numerator: i128,
    denominator: i128,
}

fn gcd(a: i128, b: i128) -> i128 {
    let (mut a, mut b) = (a.abs(), b.abs());
    while b != 0 {
        let t = b;
        b = a % b;
        a = t;
    }
    if a == 0 {
        1
    } else {
        a
    }
}

impl ExactRational {
    pub const ZERO: Self = Self {
        numerator: 0,
        denominator: 1,
    };
    pub const ONE: Self = Self {
        numerator: 1,
        denominator: 1,
    };

    /// Construct `numerator / denominator` in lowest terms. `denominator`
    /// must be nonzero; this module never calls it with a zero denominator
    /// (masses are `u64`, so a caller-controlled zero denominator is
    /// unreachable from `escort`/`uniform_sibling_coverage`'s own inputs).
    #[must_use]
    pub fn new(numerator: i128, denominator: i128) -> Self {
        debug_assert!(denominator != 0, "ExactRational: zero denominator");
        let sign = if denominator < 0 { -1 } else { 1 };
        let n = numerator * sign;
        let d = denominator * sign;
        let g = gcd(n, d);
        Self {
            numerator: n / g,
            denominator: d / g,
        }
    }

    #[must_use]
    pub fn from_int(n: i128) -> Self {
        Self {
            numerator: n,
            denominator: 1,
        }
    }

    #[must_use]
    pub fn numerator(self) -> i128 {
        self.numerator
    }

    #[must_use]
    pub fn denominator(self) -> i128 {
        self.denominator
    }

    #[must_use]
    pub fn is_zero(self) -> bool {
        self.numerator == 0
    }

    /// `self + other`, or `None` on `i128` overflow.
    #[must_use]
    pub fn checked_add(self, other: Self) -> Option<Self> {
        let n = self
            .numerator
            .checked_mul(other.denominator)?
            .checked_add(other.numerator.checked_mul(self.denominator)?)?;
        let d = self.denominator.checked_mul(other.denominator)?;
        Some(Self::new(n, d))
    }

    /// `self / other`, or `None` if `other` is zero or on `i128` overflow.
    #[must_use]
    pub fn checked_div(self, other: Self) -> Option<Self> {
        if other.numerator == 0 {
            return None;
        }
        let n = self.numerator.checked_mul(other.denominator)?;
        let d = self.denominator.checked_mul(other.numerator)?;
        Some(Self::new(n, d))
    }

    /// `self * self`, or `None` on `i128` overflow.
    #[must_use]
    pub fn checked_square(self) -> Option<Self> {
        let n = self.numerator.checked_mul(self.numerator)?;
        let d = self.denominator.checked_mul(self.denominator)?;
        Some(Self::new(n, d))
    }

    /// `1 / self`, or `None` if `self` is zero.
    #[must_use]
    pub fn checked_recip(self) -> Option<Self> {
        if self.numerator == 0 {
            return None;
        }
        Some(Self::new(self.denominator, self.numerator))
    }

    /// Approximate this rational as a Q16.16 bit pattern (`round(self *
    /// 65536)`), for comparison against [`crate::fixed::NonNegativeFixed`]
    /// in differential tests. Saturates rather than panics if the scaled
    /// value does not fit in `u32` (out of scope for the mass magnitudes
    /// this crate tests with, but kept total).
    #[must_use]
    pub fn to_q16_16_bits_round(self) -> u32 {
        let scaled_num = self.numerator * 65536;
        // round-half-away-from-zero over rationals: (2*num + den) / (2*den)
        // for nonnegative values (this module only ever converts
        // nonnegative escort weights).
        let doubled_num = scaled_num * 2 + self.denominator;
        let doubled_den = self.denominator * 2;
        let mut q = doubled_num / doubled_den;
        if q < 0 {
            q = 0;
        }
        if q > i128::from(u32::MAX) {
            u32::MAX
        } else {
            q as u32
        }
    }
}

impl PartialOrd for ExactRational {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for ExactRational {
    fn cmp(&self, other: &Self) -> Ordering {
        // Both denominators are positive by construction, so cross-
        // multiplication preserves order.
        (self.numerator * other.denominator).cmp(&(other.numerator * self.denominator))
    }
}

/// The five reference lenses, transcribing `ReferenceLens`
/// (Escort.lean:100-112).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReferenceLens {
    /// `q = -2`. Escort.lean:102.
    RareTwo,
    /// `q = -1`. Escort.lean:104.
    RareOne,
    /// `q = 0`. Escort.lean:107.
    Coverage,
    /// `q = 1`. Escort.lean:109.
    Proportional,
    /// `q = 2`. Escort.lean:111.
    ExploitTwo,
}

impl ReferenceLens {
    /// Transcribes `ReferenceLens.isNegative` (Escort.lean:126-129).
    #[must_use]
    pub fn is_negative(self) -> bool {
        matches!(self, ReferenceLens::RareTwo | ReferenceLens::RareOne)
    }
}

/// Transcribes `EscortRefusal` (Escort.lean:145-160), four constructors in
/// the exact declared order.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReferenceEscortRefusal {
    /// Escort.lean:146-148.
    EmptyDomain,
    /// Escort.lean:149-152.
    ZeroMassUnderNegativeLens,
    /// Escort.lean:153-156.
    ZeroSupport,
    /// Escort.lean:157-159.
    ZeroPartitionSum,
    /// Not a Lean constructor: this module's own arithmetic overflowed its
    /// `i128` rational representation for the given inputs. Lean's `ℚ` is
    /// unbounded and has no such failure mode; this refusal exists only
    /// because this transcription's carrier is bounded where Lean's is not.
    ExactArithmeticOverflow,
}

/// Transcribes `rawWeight` (Escort.lean:192-198), the private per-element
/// raw weight `r_q(m)`.
fn raw_weight(lens: ReferenceLens, m: u64) -> Option<ExactRational> {
    let m_rat = ExactRational::from_int(i128::from(m));
    match lens {
        // rare2 m => 1 / (m^2)   (Escort.lean:193)
        ReferenceLens::RareTwo => {
            let sq = m_rat.checked_square()?;
            ExactRational::ONE.checked_div(sq)
        }
        // rare1 m => 1 / m   (Escort.lean:194)
        ReferenceLens::RareOne => ExactRational::ONE.checked_div(m_rat),
        // coverage 0 => 0 | coverage (_+1) => 1   (Escort.lean:195-196)
        ReferenceLens::Coverage => {
            if m == 0 {
                Some(ExactRational::ZERO)
            } else {
                Some(ExactRational::ONE)
            }
        }
        // proportional m => m   (Escort.lean:197)
        ReferenceLens::Proportional => Some(m_rat),
        // exploit2 m => m^2   (Escort.lean:198)
        ReferenceLens::ExploitTwo => m_rat.checked_square(),
    }
}

/// Transcribes `escort` (Escort.lean:225-238): the exact reference escort
/// distribution, with the same four-way refusal precedence Lean fixes,
/// checked in the same order:
///
/// 1. `masses.isEmpty` -> `emptyDomain` (Escort.lean:227-228)
/// 2. negative lens with any zero mass -> `zeroMassUnderNegativeLens`
///    (Escort.lean:229-230)
/// 3. all masses zero -> `zeroSupport` (coverage) or `zeroPartitionSum`
///    (otherwise) (Escort.lean:231-234)
/// 4. otherwise compute raw weights, sum, and refuse `zeroPartitionSum` if
///    the sum is (defensively) zero, else normalize (Escort.lean:235-238)
///
/// # Errors
///
/// Returns [`ReferenceEscortRefusal`] per the precedence above, or
/// [`ReferenceEscortRefusal::ExactArithmeticOverflow`] if this
/// transcription's `i128` rational carrier (unlike Lean's unbounded `ℚ`)
/// overflows for the given masses.
pub fn escort(
    lens: ReferenceLens,
    masses: &[u64],
) -> Result<Vec<ExactRational>, ReferenceEscortRefusal> {
    if masses.is_empty() {
        return Err(ReferenceEscortRefusal::EmptyDomain);
    }
    if lens.is_negative() && masses.contains(&0) {
        return Err(ReferenceEscortRefusal::ZeroMassUnderNegativeLens);
    }
    if masses.iter().all(|&m| m == 0) {
        return Err(match lens {
            ReferenceLens::Coverage => ReferenceEscortRefusal::ZeroSupport,
            _ => ReferenceEscortRefusal::ZeroPartitionSum,
        });
    }

    let mut weights: Vec<ExactRational> = Vec::with_capacity(masses.len());
    for &m in masses {
        let w = raw_weight(lens, m).ok_or(ReferenceEscortRefusal::ExactArithmeticOverflow)?;
        weights.push(w);
    }

    let mut sum = ExactRational::ZERO;
    for &w in &weights {
        sum = sum
            .checked_add(w)
            .ok_or(ReferenceEscortRefusal::ExactArithmeticOverflow)?;
    }
    if sum.is_zero() {
        return Err(ReferenceEscortRefusal::ZeroPartitionSum);
    }

    let mut out = Vec::with_capacity(weights.len());
    for w in weights {
        let share = w
            .checked_div(sum)
            .ok_or(ReferenceEscortRefusal::ExactArithmeticOverflow)?;
        out.push(share);
    }
    Ok(out)
}

/// Transcribes `uniformSiblingCoverage` (Escort.lean:248-253): every
/// nonempty field (including all-zero) gets a uniform `1/n` weight per
/// sibling, refusing only on an empty field.
///
/// # Errors
///
/// [`ReferenceEscortRefusal::EmptyDomain`] on an empty `masses`.
pub fn uniform_sibling_coverage(
    masses: &[u64],
) -> Result<Vec<ExactRational>, ReferenceEscortRefusal> {
    if masses.is_empty() {
        return Err(ReferenceEscortRefusal::EmptyDomain);
    }
    let n = ExactRational::from_int(masses.len() as i128);
    let w = ExactRational::ONE
        .checked_div(n)
        .expect("masses is nonempty, so n != 0");
    Ok(masses.iter().map(|_| w).collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn r(n: i128, d: i128) -> ExactRational {
        ExactRational::new(n, d)
    }

    /// Escort.lean:1262-1265 (`escort_proportional_1234`).
    #[test]
    fn proportional_1234_matches_lean_golden_vector() {
        let out = escort(ReferenceLens::Proportional, &[1, 2, 3, 4]).unwrap();
        assert_eq!(out, alloc::vec![r(1, 10), r(2, 10), r(3, 10), r(4, 10)]);
    }

    /// Escort.lean:1268-1271 (`escort_exploit2_1234`).
    #[test]
    fn exploit2_1234_matches_lean_golden_vector() {
        let out = escort(ReferenceLens::ExploitTwo, &[1, 2, 3, 4]).unwrap();
        assert_eq!(out, alloc::vec![r(1, 30), r(4, 30), r(9, 30), r(16, 30)]);
    }

    /// Escort.lean:1276-1279 (`escort_coverage_1234`).
    #[test]
    fn coverage_1234_matches_lean_golden_vector() {
        let out = escort(ReferenceLens::Coverage, &[1, 2, 3, 4]).unwrap();
        assert_eq!(out, alloc::vec![r(1, 4), r(1, 4), r(1, 4), r(1, 4)]);
    }

    /// Escort.lean:1283-1286 (`escort_rare1_1234`).
    #[test]
    fn rare1_1234_matches_lean_golden_vector() {
        let out = escort(ReferenceLens::RareOne, &[1, 2, 3, 4]).unwrap();
        assert_eq!(out, alloc::vec![r(12, 25), r(6, 25), r(4, 25), r(3, 25)]);
    }

    /// Escort.lean:1289-1292 (`escort_rare2_1234`).
    #[test]
    fn rare2_1234_matches_lean_golden_vector() {
        let out = escort(ReferenceLens::RareTwo, &[1, 2, 3, 4]).unwrap();
        assert_eq!(
            out,
            alloc::vec![r(144, 205), r(36, 205), r(16, 205), r(9, 205)]
        );
    }

    /// Escort.lean:1298-1301 (`escort_proportional_123`).
    #[test]
    fn proportional_123_matches_lean_golden_vector() {
        let out = escort(ReferenceLens::Proportional, &[1, 2, 3]).unwrap();
        assert_eq!(out, alloc::vec![r(1, 6), r(2, 6), r(3, 6)]);
    }

    /// Escort.lean:1311 (`support_coverage_013`).
    #[test]
    fn coverage_013_excludes_zero_mass_support() {
        let out = escort(ReferenceLens::Coverage, &[0, 1, 3]).unwrap();
        assert_eq!(out, alloc::vec![r(0, 1), r(1, 2), r(1, 2)]);
    }

    /// Escort.lean:1317-1318 (`uniform_sibling_coverage_013`).
    #[test]
    fn uniform_sibling_coverage_013_includes_zero_mass() {
        let out = uniform_sibling_coverage(&[0, 1, 3]).unwrap();
        assert_eq!(out, alloc::vec![r(1, 3), r(1, 3), r(1, 3)]);
    }

    /// Escort.lean:1322 (`coverage_all_zero_refuses`).
    #[test]
    fn coverage_all_zero_refuses_with_zero_support() {
        assert_eq!(
            escort(ReferenceLens::Coverage, &[0, 0]),
            Err(ReferenceEscortRefusal::ZeroSupport)
        );
    }

    /// Escort.lean:1326-1327 (`uniform_sibling_coverage_all_zero_succeeds`).
    #[test]
    fn uniform_sibling_coverage_all_zero_succeeds() {
        let out = uniform_sibling_coverage(&[0, 0]).unwrap();
        assert_eq!(out, alloc::vec![r(1, 2), r(1, 2)]);
    }

    /// Escort.lean:1333 (`negative_zero_refuses`).
    #[test]
    fn rare1_zero_mass_refuses() {
        assert_eq!(
            escort(ReferenceLens::RareOne, &[0, 1]),
            Err(ReferenceEscortRefusal::ZeroMassUnderNegativeLens)
        );
    }

    /// Escort.lean:1337-1338 (`negative_zero_refuses_rare2`).
    #[test]
    fn rare2_zero_mass_refuses() {
        assert_eq!(
            escort(ReferenceLens::RareTwo, &[1, 0]),
            Err(ReferenceEscortRefusal::ZeroMassUnderNegativeLens)
        );
    }

    /// Escort.lean:1343-1344 (`positive_lens_all_zero_refuses`).
    #[test]
    fn proportional_all_zero_refuses_with_zero_partition_sum() {
        assert_eq!(
            escort(ReferenceLens::Proportional, &[0, 0]),
            Err(ReferenceEscortRefusal::ZeroPartitionSum)
        );
    }

    /// Escort.lean:1348, 1350 (`empty_domain_refuses_rare1`,
    /// `empty_domain_refuses_exploit2`).
    #[test]
    fn empty_domain_refuses_at_every_lens() {
        for lens in [
            ReferenceLens::RareTwo,
            ReferenceLens::RareOne,
            ReferenceLens::Coverage,
            ReferenceLens::Proportional,
            ReferenceLens::ExploitTwo,
        ] {
            assert_eq!(escort(lens, &[]), Err(ReferenceEscortRefusal::EmptyDomain));
        }
    }

    /// Escort.lean:1354-1355 (`uniform_sibling_coverage_empty_refuses`).
    #[test]
    fn uniform_sibling_coverage_empty_refuses() {
        assert_eq!(
            uniform_sibling_coverage(&[]),
            Err(ReferenceEscortRefusal::EmptyDomain)
        );
    }

    /// Sanity check ahead of using this module as H2's ground truth: every
    /// successful output sums to exactly one, not just approximately.
    #[test]
    fn every_successful_escort_output_sums_to_exactly_one() {
        for lens in [
            ReferenceLens::RareTwo,
            ReferenceLens::RareOne,
            ReferenceLens::Coverage,
            ReferenceLens::Proportional,
            ReferenceLens::ExploitTwo,
        ] {
            if let Ok(out) = escort(lens, &[1, 2, 3, 4, 5]) {
                let mut sum = ExactRational::ZERO;
                for w in out {
                    sum = sum.checked_add(w).unwrap();
                }
                assert_eq!(sum, ExactRational::ONE, "{lens:?}");
            }
        }
    }
}
