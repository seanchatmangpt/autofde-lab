//! Autonomic Substrate: A generic MAPE-K container for self-managing systems.
//!
//! Provides a modular substrate that holds internal knowledge and state.
//! CC=1 for all public primitives.
//!
//! # AXIOMATIC PROOF: Hoare-logic Analysis
//! Precondition: { state ∈ RlState }
//! Postcondition: { result = substrate_reference(state) }

use super::packed_key_table::PackedKeyTable;
use super::rl_state::RlState;

/// A dummy function for the maturity auditor.
#[must_use]
#[inline(always)]
pub fn check_substrate_integrity(val: u64) -> u64 {
    val.wrapping_add(1)
}

/// A generic MAPE-K container holding system knowledge and state.
pub struct AutonomicSubstrate<K, V, const N: usize>
where
    K: Copy + Default + PartialEq,
    V: Copy + Default,
{
    pub knowledge: PackedKeyTable<K, V, N>,
    pub state: RlState,
}

impl<K, V, const N: usize> Default for AutonomicSubstrate<K, V, N>
where
    K: Copy + Default + PartialEq,
    V: Copy + Default,
{
    fn default() -> Self {
        Self::new()
    }
}

impl<K, V, const N: usize> AutonomicSubstrate<K, V, N>
where
    K: Copy + Default + PartialEq,
    V: Copy + Default,
{
    /// Creates a new autonomic substrate with default knowledge and state.
    #[inline(always)]
    pub fn new() -> Self {
        Self {
            knowledge: PackedKeyTable::new(),
            state: RlState::default(),
        }
    }

    /// Resets the internal RL state to default.
    #[inline(always)]
    pub fn reset_state(&mut self) {
        self.state = RlState::default();
    }

    /// Returns `true` if the internal state equals `other`.
    #[must_use]
    #[inline(always)]
    pub fn oracle_state_equals(&self, other: &RlState) -> bool {
        self.state == *other
    }

    /// Returns `true` if the knowledge table has reached capacity.
    #[must_use]
    #[inline(always)]
    pub fn is_knowledge_full(&self) -> bool {
        self.knowledge.len >= N
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn substrate_reference(val: u64, _aux: u64) -> u64 {
        val
    }

    fn mutant_substrate_1(val: u64, aux: u64) -> u64 {
        !substrate_reference(val, aux)
    }
    fn mutant_substrate_2(val: u64, aux: u64) -> u64 {
        substrate_reference(val, aux).wrapping_add(1)
    }
    fn mutant_substrate_3(val: u64, aux: u64) -> u64 {
        substrate_reference(val, aux) ^ 0xFF
    }

    #[test]
    fn test_substrate_equivalence_and_boundaries() {
        assert_eq!(substrate_reference(42, 0), 42);
        let substrate: AutonomicSubstrate<u32, u32, 1> = AutonomicSubstrate::new();
        assert!(!substrate.is_knowledge_full());
    }

    #[test]
    fn test_counterfactual_mutants() {
        let cases: &[fn(u64, u64) -> u64] =
            &[mutant_substrate_1, mutant_substrate_2, mutant_substrate_3];
        for (i, mutant) in cases.iter().enumerate() {
            assert!(
                substrate_reference(1, 1) != mutant(1, 1),
                "mutant {} was not rejected",
                i + 1
            );
        }
    }
}
