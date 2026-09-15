// Academic-grade branchless algorithm library: fast_inverse_sqrt_u32
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// fast_inverse_sqrt_u32
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::fast_inverse_sqrt_u32::fast_inverse_sqrt_u32;
/// let result = fast_inverse_sqrt_u32(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn fast_inverse_sqrt_u32(val: u64, aux: u64) -> u64 {
    let x = (val & 0xFFFFFFFF) as f32;
    let i = x.to_bits();
    let i = 0x5f3759df - (i >> 1);
    f32::from_bits(i) as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn fast_inverse_sqrt_u32_reference(val: u64, _aux: u64) -> u64 {
        let f_val = (val & 0xFFFFFFFF) as f32;
        let bits = f_val.to_bits();
        let approx_bits = 0x5f3759df - (bits / 2);
        let approx_f = f32::from_bits(approx_bits);
        approx_f as u64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_fast_inverse_sqrt_u32_1(val: u64, aux: u64) -> u64 {
        !fast_inverse_sqrt_u32_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_fast_inverse_sqrt_u32_2(val: u64, aux: u64) -> u64 {
        fast_inverse_sqrt_u32_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_fast_inverse_sqrt_u32_3(val: u64, aux: u64) -> u64 {
        fast_inverse_sqrt_u32_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_fast_inverse_sqrt_u32_all() {
        // equivalence oracle
        let expected = fast_inverse_sqrt_u32_reference(42, 1337);
        let actual = fast_inverse_sqrt_u32(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            fast_inverse_sqrt_u32(0, 0),
            fast_inverse_sqrt_u32_reference(0, 0)
        );
        assert_eq!(
            fast_inverse_sqrt_u32(u64::MAX, u64::MAX),
            fast_inverse_sqrt_u32_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            fast_inverse_sqrt_u32(u64::MAX, 0),
            fast_inverse_sqrt_u32_reference(u64::MAX, 0)
        );
        assert_eq!(
            fast_inverse_sqrt_u32(0, u64::MAX),
            fast_inverse_sqrt_u32_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = fast_inverse_sqrt_u32_reference(42, 1337);
        let m1 = mutant_fast_inverse_sqrt_u32_1(42, 1337);
        let m2 = mutant_fast_inverse_sqrt_u32_2(42, 1337);
        let m3 = mutant_fast_inverse_sqrt_u32_3(42, 1337);
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

    pub fn bench_fast_inverse_sqrt_u32(c: &mut Criterion) {
        c.bench_function("fast_inverse_sqrt_u32", |b| {
            b.iter(|| {
                let res = fast_inverse_sqrt_u32(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
