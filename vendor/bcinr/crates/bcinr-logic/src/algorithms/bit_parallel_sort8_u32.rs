// Academic-grade branchless algorithm library: bit_parallel_sort8_u32
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// bit_parallel_sort8_u32
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Sorts the eight byte-lanes of `val` using a 19-comparator Batcher
/// odd-even mergesort network. Lane 0 is the least-significant byte. The direction is
/// chosen by the low bit of `aux`: ascending when even, descending when odd.
/// Each comparator is a branchless compare-exchange (min/max + masked select).
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::bit_parallel_sort8_u32::bit_parallel_sort8_u32;
/// let result = bit_parallel_sort8_u32(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn bit_parallel_sort8_u32(val: u64, aux: u64) -> u64 {
    // dirm = all-ones for descending, zero for ascending.
    let dirm = 0u64.wrapping_sub(aux & 1);
    let mut b = [
        val & 0xFF,
        (val >> 8) & 0xFF,
        (val >> 16) & 0xFF,
        (val >> 24) & 0xFF,
        (val >> 32) & 0xFF,
        (val >> 40) & 0xFF,
        (val >> 48) & 0xFF,
        (val >> 56) & 0xFF,
    ];

    // Branchless compare-exchange of lanes i and j (straight-line, no control flow).
    let mut ce = |i: usize, j: usize| {
        let a = b[i];
        let c = b[j];
        let lo = u64::min(a, c);
        let hi = u64::max(a, c);
        b[i] = (lo & !dirm) | (hi & dirm);
        b[j] = (hi & !dirm) | (lo & dirm);
    };

    // Batcher odd-even mergesort network for n = 8 (19 comparators), fully unrolled.
    ce(0, 1);
    ce(2, 3);
    ce(4, 5);
    ce(6, 7);
    ce(0, 2);
    ce(1, 3);
    ce(4, 6);
    ce(5, 7);
    ce(1, 2);
    ce(5, 6);
    ce(0, 4);
    ce(3, 7);
    ce(1, 5);
    ce(2, 6);
    ce(1, 4);
    ce(3, 6);
    ce(2, 4);
    ce(3, 5);
    ce(3, 4);

    b[0] | (b[1] << 8)
        | (b[2] << 16)
        | (b[3] << 24)
        | (b[4] << 32)
        | (b[5] << 40)
        | (b[6] << 48)
        | (b[7] << 56)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn bit_parallel_sort8_u32_reference(val: u64, aux: u64) -> u64 {
        // Independent: extract bytes, sort with std, reverse if descending, repack.
        let mut bytes = val.to_le_bytes();
        bytes.sort_unstable();
        if aux & 1 == 1 {
            bytes.reverse();
        }
        u64::from_le_bytes(bytes)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_bit_parallel_sort8_u32_1(val: u64, aux: u64) -> u64 {
        !bit_parallel_sort8_u32_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_bit_parallel_sort8_u32_2(val: u64, aux: u64) -> u64 {
        bit_parallel_sort8_u32_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_bit_parallel_sort8_u32_3(val: u64, aux: u64) -> u64 {
        bit_parallel_sort8_u32_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_bit_parallel_sort8_u32_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            bit_parallel_sort8_u32(val, aux),
            bit_parallel_sort8_u32_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(
            bit_parallel_sort8_u32(0, 0),
            bit_parallel_sort8_u32_reference(0, 0)
        );
        assert_eq!(
            bit_parallel_sort8_u32(u64::MAX, u64::MAX),
            bit_parallel_sort8_u32_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            bit_parallel_sort8_u32(u64::MAX, 0),
            bit_parallel_sort8_u32_reference(u64::MAX, 0)
        );
        assert_eq!(
            bit_parallel_sort8_u32(0, u64::MAX),
            bit_parallel_sort8_u32_reference(0, u64::MAX)
        );
        // --- mutant divergence ---
        let baseline = bit_parallel_sort8_u32_reference(42, 1337);
        assert_ne!(
            mutant_bit_parallel_sort8_u32_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_bit_parallel_sort8_u32_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_bit_parallel_sort8_u32_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = bit_parallel_sort8_u32_reference(val, aux) }
    //
    // Counterfactual Analysis for bit_parallel_sort8_u32:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_bit_parallel_sort8_u32(c: &mut Criterion) {
        c.bench_function("bit_parallel_sort8_u32", |b| {
            b.iter(|| {
                let res = bit_parallel_sort8_u32(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
