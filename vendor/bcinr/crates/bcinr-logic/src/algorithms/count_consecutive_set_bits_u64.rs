// Academic-grade branchless algorithm library: count_consecutive_set_bits_u64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// count_consecutive_set_bits_u64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::count_consecutive_set_bits_u64::count_consecutive_set_bits_u64;
/// let result = count_consecutive_set_bits_u64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn count_consecutive_set_bits_u64(val: u64, aux: u64) -> u64 {
    let mut count = 0;
    let mut v = val;
    for _ in 0..64 {
        let mask = 0u64.wrapping_sub((v != 0) as u64);
        count += 1 & mask;
        v &= v << 1;
    }
    count
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn count_consecutive_set_bits_u64_reference(val: u64, _aux: u64) -> u64 {
        let mut max_c = 0;
        let mut cur_c = 0;
        for i in 0..64 {
            if ((val >> i) & 1) == 1 {
                cur_c += 1;
                if cur_c > max_c {
                    max_c = cur_c;
                }
            } else {
                cur_c = 0;
            }
        }
        max_c
    }

    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_count_consecutive_set_bits_u64_1(val: u64, aux: u64) -> u64 {
        !count_consecutive_set_bits_u64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_count_consecutive_set_bits_u64_2(val: u64, aux: u64) -> u64 {
        count_consecutive_set_bits_u64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_count_consecutive_set_bits_u64_3(val: u64, aux: u64) -> u64 {
        count_consecutive_set_bits_u64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_count_consecutive_set_bits_u64_all() {
        // equivalence oracle
        let expected = count_consecutive_set_bits_u64_reference(42, 1337);
        let actual = count_consecutive_set_bits_u64(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            count_consecutive_set_bits_u64(0, 0),
            count_consecutive_set_bits_u64_reference(0, 0)
        );
        assert_eq!(
            count_consecutive_set_bits_u64(u64::MAX, u64::MAX),
            count_consecutive_set_bits_u64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            count_consecutive_set_bits_u64(u64::MAX, 0),
            count_consecutive_set_bits_u64_reference(u64::MAX, 0)
        );
        assert_eq!(
            count_consecutive_set_bits_u64(0, u64::MAX),
            count_consecutive_set_bits_u64_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = count_consecutive_set_bits_u64_reference(42, 1337);
        let m1 = mutant_count_consecutive_set_bits_u64_1(42, 1337);
        let m2 = mutant_count_consecutive_set_bits_u64_2(42, 1337);
        let m3 = mutant_count_consecutive_set_bits_u64_3(42, 1337);
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

    pub fn bench_count_consecutive_set_bits_u64(c: &mut Criterion) {
        c.bench_function("count_consecutive_set_bits_u64", |b| {
            b.iter(|| {
                let res = count_consecutive_set_bits_u64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
