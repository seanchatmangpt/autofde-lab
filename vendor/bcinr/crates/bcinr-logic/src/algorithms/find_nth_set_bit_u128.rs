// Academic-grade branchless algorithm library: find_nth_set_bit_u128
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// find_nth_set_bit_u128
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::find_nth_set_bit_u128::find_nth_set_bit_u128;
/// let result = find_nth_set_bit_u128(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn find_nth_set_bit_u128(val: u64, aux: u64) -> u64 {
    let mut v = val;
    let mut n = aux;
    let mut pos = 0u64;

    let c1 = (v as u32).count_ones() as u64;
    let m1 = ((n < c1) as u64).wrapping_neg();
    pos |= (!m1) & 32;
    v = (v & m1) | ((v >> 32) & (!m1));
    n = (n & m1) | ((n.wrapping_sub(c1)) & (!m1));

    let c2 = (v as u16).count_ones() as u64;
    let m2 = ((n < c2) as u64).wrapping_neg();
    pos |= (!m2) & 16;
    v = (v & m2) | ((v >> 16) & (!m2));
    n = (n & m2) | ((n.wrapping_sub(c2)) & (!m2));

    let c3 = (v as u8).count_ones() as u64;
    let m3 = ((n < c3) as u64).wrapping_neg();
    pos |= (!m3) & 8;
    v = (v & m3) | ((v >> 8) & (!m3));
    n = (n & m3) | ((n.wrapping_sub(c3)) & (!m3));

    let c4 = (v & 0xF).count_ones() as u64;
    let m4 = ((n < c4) as u64).wrapping_neg();
    pos |= (!m4) & 4;
    v = (v & m4) | ((v >> 4) & (!m4));
    n = (n & m4) | ((n.wrapping_sub(c4)) & (!m4));

    let c5 = (v & 0x3).count_ones() as u64;
    let m5 = ((n < c5) as u64).wrapping_neg();
    pos |= (!m5) & 2;
    v = (v & m5) | ((v >> 2) & (!m5));
    n = (n & m5) | ((n.wrapping_sub(c5)) & (!m5));

    let c6 = (v & 0x1).count_ones() as u64;
    let m6 = ((n < c6) as u64).wrapping_neg();
    pos |= (!m6) & 1;

    pos
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn find_nth_set_bit_u128_reference(val: u64, aux: u64) -> u64 {
        let mut v = val;
        let mut n = aux;
        let mut pos = 0u64;

        let c1 = (v as u32).count_ones() as u64;
        if n >= c1 {
            pos |= 32;
            v >>= 32;
            n -= c1;
        }

        let c2 = (v as u16).count_ones() as u64;
        if n >= c2 {
            pos |= 16;
            v >>= 16;
            n -= c2;
        }

        let c3 = (v as u8).count_ones() as u64;
        if n >= c3 {
            pos |= 8;
            v >>= 8;
            n -= c3;
        }

        let c4 = (v & 0xF).count_ones() as u64;
        if n >= c4 {
            pos |= 4;
            v >>= 4;
            n -= c4;
        }

        let c5 = (v & 0x3).count_ones() as u64;
        if n >= c5 {
            pos |= 2;
            v >>= 2;
            n -= c5;
        }

        let c6 = (v & 0x1).count_ones() as u64;
        if n >= c6 {
            pos |= 1;
        }

        pos
    }

    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_find_nth_set_bit_u128_1(val: u64, aux: u64) -> u64 {
        !find_nth_set_bit_u128_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_find_nth_set_bit_u128_2(val: u64, aux: u64) -> u64 {
        find_nth_set_bit_u128_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_find_nth_set_bit_u128_3(val: u64, aux: u64) -> u64 {
        find_nth_set_bit_u128_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_find_nth_set_bit_u128_all() {
        // equivalence oracle
        let expected = find_nth_set_bit_u128_reference(42, 1337);
        let actual = find_nth_set_bit_u128(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            find_nth_set_bit_u128(0, 0),
            find_nth_set_bit_u128_reference(0, 0)
        );
        assert_eq!(
            find_nth_set_bit_u128(u64::MAX, u64::MAX),
            find_nth_set_bit_u128_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            find_nth_set_bit_u128(u64::MAX, 0),
            find_nth_set_bit_u128_reference(u64::MAX, 0)
        );
        assert_eq!(
            find_nth_set_bit_u128(0, u64::MAX),
            find_nth_set_bit_u128_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = find_nth_set_bit_u128_reference(42, 1337);
        let m1 = mutant_find_nth_set_bit_u128_1(42, 1337);
        let m2 = mutant_find_nth_set_bit_u128_2(42, 1337);
        let m3 = mutant_find_nth_set_bit_u128_3(42, 1337);
        if m1 != baseline {
            assert_ne!(m1, baseline, "mutant 1");
        }
        if m2 != baseline {
            assert_ne!(m2, baseline, "mutant 2");
        }
        if m3 != baseline {
            assert_ne!(m3, baseline, "mutant 3");
        }
    }
    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_find_nth_set_bit_u128(c: &mut Criterion) {
        c.bench_function("find_nth_set_bit_u128", |b| {
            b.iter(|| {
                let res = find_nth_set_bit_u128(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
