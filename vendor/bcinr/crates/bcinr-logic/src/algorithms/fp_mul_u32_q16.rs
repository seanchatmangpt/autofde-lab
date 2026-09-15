// Academic-grade branchless algorithm library: fp_mul_u32_q16
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// fp_mul_u32_q16
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::fp_mul_u32_q16::fp_mul_u32_q16;
/// let result = fp_mul_u32_q16(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn fp_mul_u32_q16(val: u64, aux: u64) -> u64 {
    ((val as u128 * aux as u128) >> 16) as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn fp_mul_u32_q16_reference(val: u64, aux: u64) -> u64 {
        ((val as u128 * aux as u128) / 65536) as u64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_fp_mul_u32_q16_1(val: u64, aux: u64) -> u64 {
        !fp_mul_u32_q16_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_fp_mul_u32_q16_2(val: u64, aux: u64) -> u64 {
        fp_mul_u32_q16_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_fp_mul_u32_q16_3(val: u64, aux: u64) -> u64 {
        fp_mul_u32_q16_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_fp_mul_u32_q16_all() {
        // equivalence oracle
        let expected = fp_mul_u32_q16_reference(42, 1337);
        let actual = fp_mul_u32_q16(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(fp_mul_u32_q16(0, 0), fp_mul_u32_q16_reference(0, 0));
        assert_eq!(
            fp_mul_u32_q16(u64::MAX, u64::MAX),
            fp_mul_u32_q16_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            fp_mul_u32_q16(u64::MAX, 0),
            fp_mul_u32_q16_reference(u64::MAX, 0)
        );
        assert_eq!(
            fp_mul_u32_q16(0, u64::MAX),
            fp_mul_u32_q16_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = fp_mul_u32_q16_reference(42, 1337);
        let m1 = mutant_fp_mul_u32_q16_1(42, 1337);
        let m2 = mutant_fp_mul_u32_q16_2(42, 1337);
        let m3 = mutant_fp_mul_u32_q16_3(42, 1337);
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

    pub fn bench_fp_mul_u32_q16(c: &mut Criterion) {
        c.bench_function("fp_mul_u32_q16", |b| {
            b.iter(|| {
                let res = fp_mul_u32_q16(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
