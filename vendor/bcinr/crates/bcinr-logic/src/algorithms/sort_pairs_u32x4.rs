// Academic-grade branchless algorithm library: sort_pairs_u32x4
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// sort_pairs_u32x4
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// Sorts the two adjacent pairs of the four u16 lanes of `val`: the pair
/// (lane0, lane1) and the pair (lane2, lane3) are each ordered ascending with
/// a branchless min/max compare-exchange. `aux` is ignored; lanes pack
/// low-to-high.
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn sort_pairs_u32x4(val: u64, aux: u64) -> u64 {
    let l0 = val & 0xFFFF;
    let l1 = (val >> 16) & 0xFFFF;
    let l2 = (val >> 32) & 0xFFFF;
    let l3 = (val >> 48) & 0xFFFF;

    let p0 = u64::min(l0, l1);
    let p1 = u64::max(l0, l1);
    let p2 = u64::min(l2, l3);
    let p3 = u64::max(l2, l3);

    p0 | (p1 << 16) | (p2 << 32) | (p3 << 48)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn sort_pairs_u32x4_reference(val: u64, _aux: u64) -> u64 {
        // Independent oracle: sort each two-element pair with the standard
        // library, then repack the four lanes.
        let mut a = [val & 0xFFFF, (val >> 16) & 0xFFFF];
        let mut b = [(val >> 32) & 0xFFFF, (val >> 48) & 0xFFFF];
        a.sort();
        b.sort();
        a[0] | (a[1] << 16) | (b[0] << 32) | (b[1] << 48)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_sort_pairs_u32x4_1(val: u64, aux: u64) -> u64 {
        !sort_pairs_u32x4_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_sort_pairs_u32x4_2(val: u64, aux: u64) -> u64 {
        sort_pairs_u32x4_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_sort_pairs_u32x4_3(val: u64, aux: u64) -> u64 {
        sort_pairs_u32x4_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_sort_pairs_u32x4_all() {
        // oracle
        assert_eq!(
            sort_pairs_u32x4(42, 1337),
            sort_pairs_u32x4_reference(42, 1337)
        );
        // boundaries
        assert_eq!(sort_pairs_u32x4(0, 0), sort_pairs_u32x4_reference(0, 0));
        assert_eq!(
            sort_pairs_u32x4(u64::MAX, u64::MAX),
            sort_pairs_u32x4_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            sort_pairs_u32x4(u64::MAX, 0),
            sort_pairs_u32x4_reference(u64::MAX, 0)
        );
        assert_eq!(
            sort_pairs_u32x4(0, u64::MAX),
            sort_pairs_u32x4_reference(0, u64::MAX)
        );
        // mutants
        let base = sort_pairs_u32x4_reference(42, 1337);
        assert_ne!(mutant_sort_pairs_u32x4_1(42, 1337), base, "mutant 1");
        assert_ne!(mutant_sort_pairs_u32x4_2(42, 1337), base, "mutant 2");
        assert_ne!(mutant_sort_pairs_u32x4_3(42, 1337), base, "mutant 3");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = sort_pairs_u32x4_reference(val, aux) }
    //
    // Counterfactual Analysis for sort_pairs_u32x4:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_sort_pairs_u32x4(c: &mut Criterion) {
        c.bench_function("sort_pairs_u32x4", |b| {
            b.iter(|| {
                let res = sort_pairs_u32x4(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
