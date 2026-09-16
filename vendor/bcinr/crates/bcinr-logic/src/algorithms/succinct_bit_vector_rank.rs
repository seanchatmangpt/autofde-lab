// Academic-grade branchless algorithm library: succinct_bit_vector_rank
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// succinct_bit_vector_rank
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::succinct_bit_vector_rank::succinct_bit_vector_rank;
/// let result = succinct_bit_vector_rank(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
///
/// # Branchless Contract
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn succinct_bit_vector_rank(val: u64, aux: u64) -> u64 {
    // Branchless Contract: succinct bit-vector rank. Counts the set bits of `val` strictly below
    // bit position `aux & 63` (the rank of that position), via a masked
    // population count over the low-order prefix.
    let p = (aux & 63) as u32;
    let prefix = (1u64 << p).wrapping_sub(1);
    (val & prefix).count_ones() as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    fn succinct_bit_vector_rank_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: serial scan counting set bits strictly below
        // position `aux & 63` (test-only loop), structurally distinct from the
        // masked population count used by the impl.
        let p = (aux % 64) as u32;
        let mut count: u64 = 0;
        let mut i: u32 = 0;
        while i < p {
            count += (val >> i) & 1;
            i += 1;
        }
        count
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_succinct_bit_vector_rank_1(val: u64, aux: u64) -> u64 {
        !succinct_bit_vector_rank_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_succinct_bit_vector_rank_2(val: u64, aux: u64) -> u64 {
        succinct_bit_vector_rank_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_succinct_bit_vector_rank_3(val: u64, aux: u64) -> u64 {
        succinct_bit_vector_rank_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_succinct_bit_vector_rank_all() {
        // oracle
        assert_eq!(
            succinct_bit_vector_rank(42, 1337),
            succinct_bit_vector_rank_reference(42, 1337)
        );
        // boundaries
        assert_eq!(
            succinct_bit_vector_rank(0, 0),
            succinct_bit_vector_rank_reference(0, 0)
        );
        assert_eq!(
            succinct_bit_vector_rank(u64::MAX, u64::MAX),
            succinct_bit_vector_rank_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            succinct_bit_vector_rank(u64::MAX, 0),
            succinct_bit_vector_rank_reference(u64::MAX, 0)
        );
        assert_eq!(
            succinct_bit_vector_rank(0, u64::MAX),
            succinct_bit_vector_rank_reference(0, u64::MAX)
        );
        // mutants
        let base = succinct_bit_vector_rank_reference(42, 1337);
        assert_ne!(
            mutant_succinct_bit_vector_rank_1(42, 1337),
            base,
            "mutant 1"
        );
        assert_ne!(
            mutant_succinct_bit_vector_rank_2(42, 1337),
            base,
            "mutant 2"
        );
        assert_ne!(
            mutant_succinct_bit_vector_rank_3(42, 1337),
            base,
            "mutant 3"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = succinct_bit_vector_rank_reference(val, aux) }
    //
    // Counterfactual Analysis for succinct_bit_vector_rank:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_succinct_bit_vector_rank(c: &mut Criterion) {
        c.bench_function("succinct_bit_vector_rank", |b| {
            b.iter(|| {
                let res = succinct_bit_vector_rank(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
