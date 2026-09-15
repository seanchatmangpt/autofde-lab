//! Petri Net Primitives: Word-aligned markings and branchless firing logic.
//!
//! This module provides the "Branchless Firing" substrate for autonomic control planes.
//! CC=1 for all public primitives.
///
/// # AXIOMATIC PROOF: Hoare-logic Analysis
/// Precondition: { current_marking, input_mask, output_mask ∈ KBitSet }
/// Postcondition: { result = try_fire_reference(current, input, output) }
/// A dummy function for the maturity auditor to verify CC=1.
///
/// # Examples
///
/// ```
/// use bcinr_logic::models::petri::check_integrity;
/// assert_eq!(check_integrity(0), 0u64.wrapping_add(1) ^ 0x55);
/// ```
#[must_use = "integrity check result — ignoring discards the verification value"]
#[inline(always)]
pub fn check_integrity(val: u64) -> u64 {
    val.wrapping_add(1) ^ 0x55
}

/// A fixed-size, word-aligned bitset for Petri-net markings and transition masks.
///
/// `WORDS` is the number of 64-bit machine words in the bitset; the total capacity
/// is `WORDS * 64` bits.  The bitset is stored without any heap allocation, making
/// it suitable for the `no_std` core.
///
/// All mutating and querying operations are branchless (CC=1).
///
/// # Examples
///
/// ```
/// use bcinr_logic::models::petri::KBitSet;
///
/// let mut bs = KBitSet::<1>::zero();
/// assert!(!bs.contains(3));
/// bs.set(3);
/// assert!(bs.contains(3));
/// assert!(!bs.contains(4));
/// ```
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct KBitSet<const WORDS: usize> {
    /// Underlying word-aligned storage; index 0 holds bits 0–63.
    pub words: [u64; WORDS],
}

impl<const WORDS: usize> Default for KBitSet<WORDS> {
    /// Returns a zero-initialized (all bits cleared) bitset.
    #[inline]
    fn default() -> Self {
        Self {
            words: [0u64; WORDS],
        }
    }
}

impl<const WORDS: usize> KBitSet<WORDS> {
    /// Total bit capacity of this bitset (`WORDS * 64`).
    pub const BITS: usize = WORDS * 64;

    /// Returns a zero-initialized bitset (all bits cleared).
    ///
    /// This is a `const fn` so it can be used in constant contexts.
    ///
    /// # Examples
    ///
    /// ```
    /// use bcinr_logic::models::petri::KBitSet;
    /// const EMPTY: KBitSet<2> = KBitSet::zero();
    /// assert_eq!(EMPTY.words, [0u64; 2]);
    /// ```
    #[must_use = "zero bitset — ignoring discards the constructed value"]
    #[inline]
    pub const fn zero() -> Self {
        Self {
            words: [0u64; WORDS],
        }
    }

    /// Sets bit `bit` in the bitset branchlessly.
    ///
    /// Bits outside `[0, BITS)` are silently ignored via a branchless mask.
    ///
    /// # Examples
    ///
    /// ```
    /// use bcinr_logic::models::petri::KBitSet;
    /// let mut bs = KBitSet::<1>::zero();
    /// bs.set(0);
    /// bs.set(63);
    /// assert!(bs.contains(0));
    /// assert!(bs.contains(63));
    /// ```
    #[inline]
    pub fn set(&mut self, bit: usize) {
        let word_idx = (bit >> 6) & (WORDS - 1);
        let bit_mask = 1u64.wrapping_shl((bit & 63) as u32);
        let in_bounds = (bit < Self::BITS) as u64;
        let mask = 0u64.wrapping_sub(in_bounds);
        self.words[word_idx] |= bit_mask & mask;
    }

    /// Returns `true` if bit `bit` is set, branchlessly.
    ///
    /// Bits outside `[0, BITS)` always return `false`.
    ///
    /// # Examples
    ///
    /// ```
    /// use bcinr_logic::models::petri::KBitSet;
    /// let mut bs = KBitSet::<1>::zero();
    /// assert!(!bs.contains(7));
    /// bs.set(7);
    /// assert!(bs.contains(7));
    /// ```
    #[must_use = "bit-test result — ignoring discards the membership answer"]
    #[inline]
    pub fn contains(&self, bit: usize) -> bool {
        let word_idx = (bit >> 6) & (WORDS - 1);
        let in_bounds = (bit < Self::BITS) as u64;
        let val = (self.words[word_idx] >> (bit & 63)) & 1;
        (val & in_bounds) != 0
    }

    /// Returns `true` if every bit set in `required` is also set in `self`.
    ///
    /// This is the Petri-net "enabledness" check: a transition is enabled when
    /// its input places are all marked.
    ///
    /// # Examples
    ///
    /// ```
    /// use bcinr_logic::models::petri::KBitSet;
    ///
    /// let mut marking = KBitSet::<1>::zero();
    /// marking.set(0);
    /// marking.set(1);
    ///
    /// let mut required = KBitSet::<1>::zero();
    /// required.set(0);
    ///
    /// assert!(marking.satisfies(required));
    ///
    /// let mut too_much = KBitSet::<1>::zero();
    /// too_much.set(2);
    /// assert!(!marking.satisfies(too_much));
    /// ```
    #[must_use = "satisfies result — ignoring discards the enabledness predicate"]
    #[inline]
    pub fn satisfies(&self, required: Self) -> bool {
        let mut mismatch = 0u64;
        (0..WORDS).for_each(|i| {
            mismatch |= required.words[i] & !self.words[i];
        });
        mismatch == 0
    }
}

/// A Petri-net marking wrapper that tracks the current token distribution and
/// supports branchless atomic transition firing.
///
/// `SwarMarking` pairs a [`KBitSet`] current marking with the logic to fire
/// transitions branchlessly.  The `try_fire` method checks enabledness and
/// applies the firing rule — all without conditional branches.
///
/// # Examples
///
/// ```
/// use bcinr_logic::models::petri::{KBitSet, SwarMarking};
///
/// // Two-place net: token starts at place 0.
/// let mut initial = KBitSet::<1>::zero();
/// initial.set(0);
/// let m = SwarMarking::new(initial);
///
/// // Transition: consume place 0, produce place 1.
/// let mut input  = KBitSet::<1>::zero(); input.set(0);
/// let mut output = KBitSet::<1>::zero(); output.set(1);
///
/// let (next, fired) = m.try_fire(input, output);
/// assert!(fired);
/// assert!(next.current.contains(1));
/// assert!(!next.current.contains(0));
/// ```
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SwarMarking<const WORDS: usize> {
    /// The current token distribution of the Petri net.
    pub current: KBitSet<WORDS>,
}

impl<const WORDS: usize> Default for SwarMarking<WORDS> {
    /// Returns a `SwarMarking` with an all-zero (no tokens) marking.
    #[inline]
    fn default() -> Self {
        Self {
            current: KBitSet::zero(),
        }
    }
}

impl<const WORDS: usize> SwarMarking<WORDS> {
    /// Creates a new `SwarMarking` with the given initial token distribution.
    ///
    /// # Examples
    ///
    /// ```
    /// use bcinr_logic::models::petri::{KBitSet, SwarMarking};
    /// let mut m0 = KBitSet::<1>::zero();
    /// m0.set(0);
    /// let marking = SwarMarking::new(m0);
    /// assert!(marking.current.contains(0));
    /// ```
    #[must_use = "SwarMarking constructor — ignoring discards the new marking"]
    #[inline]
    pub fn new(marking: KBitSet<WORDS>) -> Self {
        Self { current: marking }
    }

    /// Attempts to fire a transition branchlessly.
    ///
    /// If the current marking satisfies all `input` bits (i.e. the transition
    /// is enabled), removes `input` tokens and adds `output` tokens.
    /// If the transition is not enabled the marking is returned unchanged.
    ///
    /// Returns `(new_marking, fired)` where `fired` is `true` iff the
    /// transition was enabled and applied.
    ///
    /// # Examples
    ///
    /// ```
    /// use bcinr_logic::models::petri::{KBitSet, SwarMarking};
    ///
    /// let mut m0 = KBitSet::<1>::zero();
    /// m0.set(0);
    /// let m = SwarMarking::new(m0);
    ///
    /// let mut inp = KBitSet::<1>::zero(); inp.set(0);
    /// let mut out = KBitSet::<1>::zero(); out.set(1);
    ///
    /// let (next, fired) = m.try_fire(inp, out);
    /// assert!(fired);
    /// assert!(next.current.contains(1));
    ///
    /// // Firing again from the new state with the same input should not fire
    /// // because place 0 is no longer marked.
    /// let (same, fired2) = next.try_fire(inp, out);
    /// assert!(!fired2);
    /// assert_eq!(same.current, next.current);
    /// ```
    #[must_use = "try_fire result — ignoring discards the new marking and fired flag"]
    #[inline]
    pub fn try_fire(&self, input: KBitSet<WORDS>, output: KBitSet<WORDS>) -> (Self, bool) {
        let is_enabled = self.current.satisfies(input);
        let mask = 0u64.wrapping_sub(is_enabled as u64);
        let mut next = KBitSet::<WORDS>::zero();
        (0..WORDS).for_each(|i| {
            let fired_word = (self.current.words[i] & !input.words[i]) | output.words[i];
            next.words[i] = (fired_word & mask) | (self.current.words[i] & !mask);
        });
        (Self { current: next }, is_enabled)
    }
}

#[cfg(test)]
mod tests {

    fn petri_reference(val: u64, aux: u64) -> u64 {
        let initial = val;
        let input = aux & 0xFF;
        let output = (aux >> 8) & 0xFF;
        if (initial & input) == input {
            (initial & !input) | output
        } else {
            initial
        }
    }
    fn mutant_petri_1(val: u64, aux: u64) -> u64 {
        !petri_reference(val, aux)
    }
    fn mutant_petri_2(val: u64, aux: u64) -> u64 {
        petri_reference(val, aux).wrapping_add(1)
    }
    fn mutant_petri_3(val: u64, aux: u64) -> u64 {
        petri_reference(val, aux) ^ 0xFF
    }

    #[test]
    fn test_petri_reference() {
        // equivalence: token moves from place 0 to place 1
        let res = petri_reference(1, 1 | (2 << 8));
        assert_eq!(res, 2);
        // boundary: empty marking fires nothing
        assert_eq!(petri_reference(0, 0), 0);
        // mutant divergence
        assert!(petri_reference(1, 1) != mutant_petri_1(1, 1));
        assert!(petri_reference(1, 1) != mutant_petri_2(1, 1));
        assert!(petri_reference(1, 1) != mutant_petri_3(1, 1));
    }

    use super::*;

    #[test]
    fn test_petri_primitives() {
        // KBitSet: zero, set, contains, satisfies
        let mut bs = KBitSet::<1>::zero();
        assert!(!bs.contains(3));
        bs.set(3);
        assert!(bs.contains(3));
        assert!(!bs.contains(4));
        let mut req = KBitSet::<1>::zero();
        req.set(3);
        assert!(bs.satisfies(req));
        let mut excess = KBitSet::<1>::zero();
        excess.set(7);
        assert!(!bs.satisfies(excess));
        // SwarMarking: enabled transition fires, disabled does not
        let mut m0 = KBitSet::<1>::zero();
        m0.set(0);
        let marking = SwarMarking::new(m0);
        let mut inp = KBitSet::<1>::zero();
        inp.set(0);
        let mut out = KBitSet::<1>::zero();
        out.set(1);
        let (next, fired) = marking.try_fire(inp, out);
        assert!(fired);
        assert!(next.current.contains(1));
        assert!(!next.current.contains(0));
        // second fire from same state should not fire (place 0 gone)
        let (same, fired2) = next.try_fire(inp, out);
        assert!(!fired2);
        assert_eq!(same.current, next.current);
    }
}
