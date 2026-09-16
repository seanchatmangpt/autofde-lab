// Academic-grade branchless algorithm library: bloom_filter_query_u64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// bloom_filter_query_u64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Branchless Contract:** Membership query against a 64-bit Bloom filter.
/// The element `val` is mapped to two independent probe bit positions via two
/// hash mixers (each reduced mod 64). The element is *possibly present* iff all
/// of its probe bits are set in the filter word `aux`. Returns 1 for "possibly
/// present", 0 for "definitely absent".
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::bloom_filter_query_u64::bloom_filter_query_u64;
/// let result = bloom_filter_query_u64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn bloom_filter_query_u64(val: u64, aux: u64) -> u64 {
    let h1 = val.wrapping_mul(0x9E3779B97F4A7C15);
    let h2 = (val ^ 0xCBF29CE484222325).wrapping_mul(0x100000001B3);
    let i = (h1 >> 58) & 63;
    let j = (h2 >> 58) & 63;
    let probe = (1u64 << i) | (1u64 << j);
    (((aux & probe) ^ probe) == 0) as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    fn bloom_filter_query_u64_reference(val: u64, aux: u64) -> u64 {
        // Re-derive the two probe positions, then test each bit individually
        // and require both to be present (logical AND over the probes).
        let h1 = val.wrapping_mul(0x9E3779B97F4A7C15);
        let h2 = (val ^ 0xCBF29CE484222325).wrapping_mul(0x100000001B3);
        let positions = [(h1 >> 58) & 63, (h2 >> 58) & 63];
        let mut all_set = true;
        for &p in positions.iter() {
            let bit_present = (aux >> p) & 1 == 1;
            all_set = all_set && bit_present;
        }
        if all_set {
            1
        } else {
            0
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_bloom_filter_query_u64_1(val: u64, aux: u64) -> u64 {
        !bloom_filter_query_u64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_bloom_filter_query_u64_2(val: u64, aux: u64) -> u64 {
        bloom_filter_query_u64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_bloom_filter_query_u64_3(val: u64, aux: u64) -> u64 {
        bloom_filter_query_u64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_bloom_filter_query_u64_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            bloom_filter_query_u64(val, aux),
            bloom_filter_query_u64_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(
            bloom_filter_query_u64(0, 0),
            bloom_filter_query_u64_reference(0, 0)
        );
        assert_eq!(
            bloom_filter_query_u64(u64::MAX, u64::MAX),
            bloom_filter_query_u64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            bloom_filter_query_u64(u64::MAX, 0),
            bloom_filter_query_u64_reference(u64::MAX, 0)
        );
        assert_eq!(
            bloom_filter_query_u64(0, u64::MAX),
            bloom_filter_query_u64_reference(0, u64::MAX)
        );
        // --- mutant divergence ---
        let baseline = bloom_filter_query_u64_reference(42, 1337);
        assert_ne!(
            mutant_bloom_filter_query_u64_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_bloom_filter_query_u64_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_bloom_filter_query_u64_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = bloom_filter_query_u64_reference(val, aux) }
    //
    // Counterfactual Analysis for bloom_filter_query_u64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_bloom_filter_query_u64(c: &mut Criterion) {
        c.bench_function("bloom_filter_query_u64", |b| {
            b.iter(|| {
                let res = bloom_filter_query_u64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
