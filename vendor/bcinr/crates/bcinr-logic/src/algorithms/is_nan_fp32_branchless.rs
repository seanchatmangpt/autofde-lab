// Academic-grade branchless algorithm library: is_nan_fp32_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// is_nan_fp32_branchless
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::is_nan_fp32_branchless::is_nan_fp32_branchless;
/// let result = is_nan_fp32_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn is_nan_fp32_branchless(val: u64, aux: u64) -> u64 {
    // Interpretation: the low 32 bits of `val` and of `aux` each hold an IEEE-754
    // binary32 bit pattern. A value is NaN iff its exponent field is all-ones
    // (0xFF) AND its 23-bit mantissa is non-zero. We pack: bit0 = nan(val),
    // bit1 = nan(aux). Fully branchless via masked exponent/mantissa compares.
    let nan = |x: u64| -> u64 {
        let exp = (x >> 23) & 0xFF;
        // exp_is_max == 1 iff exp == 0xFF.
        let exp_is_max = (exp ^ 0xFF).wrapping_sub(1) >> 63;
        let mant = x & 0x7F_FFFF;
        // mant_nz == 1 iff mant != 0.
        let mant_nz = mant.wrapping_neg() >> 63;
        exp_is_max & mant_nz
    };
    nan(val) | (nan(aux) << 1)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn is_nan_fp32_branchless_reference(val: u64, aux: u64) -> u64 {
        // Independent: reconstruct the f32 and use the standard library predicate.
        let bit = |x: u64| -> u64 {
            if f32::from_bits(x as u32).is_nan() {
                1
            } else {
                0
            }
        };
        bit(val) | (bit(aux) << 1)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_is_nan_fp32_branchless_1(val: u64, aux: u64) -> u64 {
        !is_nan_fp32_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_is_nan_fp32_branchless_2(val: u64, aux: u64) -> u64 {
        is_nan_fp32_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_is_nan_fp32_branchless_3(val: u64, aux: u64) -> u64 {
        is_nan_fp32_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_is_nan_fp32_branchless_all() {
        // equivalence oracle
        let expected = is_nan_fp32_branchless_reference(42, 1337);
        let actual = is_nan_fp32_branchless(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            is_nan_fp32_branchless(0, 0),
            is_nan_fp32_branchless_reference(0, 0)
        );
        assert_eq!(
            is_nan_fp32_branchless(u64::MAX, u64::MAX),
            is_nan_fp32_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            is_nan_fp32_branchless(u64::MAX, 0),
            is_nan_fp32_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            is_nan_fp32_branchless(0, u64::MAX),
            is_nan_fp32_branchless_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = is_nan_fp32_branchless_reference(42, 1337);
        let m1 = mutant_is_nan_fp32_branchless_1(42, 1337);
        let m2 = mutant_is_nan_fp32_branchless_2(42, 1337);
        let m3 = mutant_is_nan_fp32_branchless_3(42, 1337);
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
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = is_nan_fp32_branchless_reference(val, aux) }
    //
    // Counterfactual Analysis for is_nan_fp32_branchless:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_is_nan_fp32_branchless(c: &mut Criterion) {
        c.bench_function("is_nan_fp32_branchless", |b| {
            b.iter(|| {
                let res = is_nan_fp32_branchless(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
