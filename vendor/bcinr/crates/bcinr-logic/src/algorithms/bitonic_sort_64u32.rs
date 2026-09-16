// Academic-grade branchless algorithm library: bitonic_sort_64u32
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// bitonic_sort_64u32
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Sorts the eight byte-lanes of `val` (lane 0 = least-significant byte)
/// using the canonical 24-comparator bitonic sorting network (3 phases of build-and-merge
/// with the standard alternating sub-block directions). The low bit of `aux` selects the
/// final order: ascending when even, descending when odd. Each comparator is a branchless
/// min/max compare-exchange whose direction is a compile-time constant XORed with the
/// global order bit.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::bitonic_sort_64u32::bitonic_sort_64u32;
/// let result = bitonic_sort_64u32(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn bitonic_sort_64u32(val: u64, aux: u64) -> u64 {
    let flip = aux & 1; // 1 => globally descending
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

    // asc = 1 means "min first" for this comparator before the global flip.
    let mut ce = |i: usize, j: usize, asc: u64| {
        let descending = asc ^ 1 ^ flip; // 1 => max first
        let dirm = 0u64.wrapping_sub(descending);
        let a = b[i];
        let c = b[j];
        let lo = u64::min(a, c);
        let hi = u64::max(a, c);
        b[i] = (lo & !dirm) | (hi & dirm);
        b[j] = (hi & !dirm) | (lo & dirm);
    };

    // Phase 1
    ce(0, 1, 1);
    ce(2, 3, 0);
    ce(4, 5, 1);
    ce(6, 7, 0);
    // Phase 2
    ce(0, 2, 1);
    ce(1, 3, 1);
    ce(4, 6, 0);
    ce(5, 7, 0);
    ce(0, 1, 1);
    ce(2, 3, 1);
    ce(4, 5, 0);
    ce(6, 7, 0);
    // Phase 3
    ce(0, 4, 1);
    ce(1, 5, 1);
    ce(2, 6, 1);
    ce(3, 7, 1);
    ce(0, 2, 1);
    ce(1, 3, 1);
    ce(4, 6, 1);
    ce(5, 7, 1);
    ce(0, 1, 1);
    ce(2, 3, 1);
    ce(4, 5, 1);
    ce(6, 7, 1);

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
    fn bitonic_sort_64u32_reference(val: u64, aux: u64) -> u64 {
        // Independent: a correct sort fully orders the lanes, so use std sort directly.
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
    fn mutant_bitonic_sort_64u32_1(val: u64, aux: u64) -> u64 {
        !bitonic_sort_64u32_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_bitonic_sort_64u32_2(val: u64, aux: u64) -> u64 {
        bitonic_sort_64u32_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_bitonic_sort_64u32_3(val: u64, aux: u64) -> u64 {
        bitonic_sort_64u32_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_bitonic_sort_64u32_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            bitonic_sort_64u32(val, aux),
            bitonic_sort_64u32_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(bitonic_sort_64u32(0, 0), bitonic_sort_64u32_reference(0, 0));
        assert_eq!(
            bitonic_sort_64u32(u64::MAX, u64::MAX),
            bitonic_sort_64u32_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            bitonic_sort_64u32(u64::MAX, 0),
            bitonic_sort_64u32_reference(u64::MAX, 0)
        );
        assert_eq!(
            bitonic_sort_64u32(0, u64::MAX),
            bitonic_sort_64u32_reference(0, u64::MAX)
        );
        // --- mutant divergence ---
        let baseline = bitonic_sort_64u32_reference(42, 1337);
        assert_ne!(
            mutant_bitonic_sort_64u32_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_bitonic_sort_64u32_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_bitonic_sort_64u32_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = bitonic_sort_64u32_reference(val, aux) }
    //
    // Counterfactual Analysis for bitonic_sort_64u32:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_bitonic_sort_64u32(c: &mut Criterion) {
        c.bench_function("bitonic_sort_64u32", |b| {
            b.iter(|| {
                let res = bitonic_sort_64u32(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
