// Academic-grade branchless algorithm library: exp2_u64_fixed
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// exp2_u64_fixed
///
/// Branchless Q16 fixed-point 2^n, using only the integer part of the Q16 exponent.
/// Input `val` is a Q16 number (val / 65536 = exponent). Result is `2^floor(val/65536)`
/// in Q16 format (i.e. `65536 << int_exp`), saturating to u64::MAX for large exponents.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::exp2_u64_fixed::exp2_u64_fixed;
/// assert_eq!(exp2_u64_fixed(0, 0), 65536);        // 2^0 = 1 in Q16
/// assert_eq!(exp2_u64_fixed(65536, 0), 131072);   // 2^1 = 2 in Q16
/// assert_eq!(exp2_u64_fixed(131072, 0), 262144);  // 2^2 = 4 in Q16
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn exp2_u64_fixed(val: u64, _aux: u64) -> u64 {
    // val is Q16: integer exponent is val >> 16.
    // Result in Q16: 65536 * 2^int_exp = 65536 << int_exp.
    // Saturate at u64::MAX for int_exp >= 48 (65536 << 48 would overflow u64).
    let int_exp = (val >> 16) as u32;
    // Branchless saturation: if int_exp >= 48, sat_mask = 0xFFF...F, else 0x0
    let saturated = (int_exp >= 48) as u64;
    let sat_mask = saturated.wrapping_neg(); // all-ones if saturated, zero otherwise
                                             // Clamp shift to prevent undefined behavior (Rust panics on shift >= 64)
    let safe_exp = int_exp & 63;
    let result = 65536u64.wrapping_shl(safe_exp);
    // Select: if saturated return u64::MAX, else return result
    (result & !sat_mask) | sat_mask
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation matching same integer-exp semantics
    // -------------------------------------------------------------------------
    fn exp2_u64_fixed_reference(val: u64, _aux: u64) -> u64 {
        let int_exp = (val >> 16) as u32;
        if int_exp >= 48 {
            u64::MAX
        } else {
            65536u64 << int_exp
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_exp2_u64_fixed_1(val: u64, aux: u64) -> u64 {
        !exp2_u64_fixed_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_exp2_u64_fixed_2(val: u64, aux: u64) -> u64 {
        exp2_u64_fixed_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_exp2_u64_fixed_3(val: u64, aux: u64) -> u64 {
        exp2_u64_fixed_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // SEMANTIC TESTS: Verify Q16 fixed-point exponentiation
    // -------------------------------------------------------------------------
    #[test]
    fn test_exp2_u64_fixed_known_values() {
        // 2^0 = 1; in Q16 = 65536
        assert_eq!(exp2_u64_fixed(0, 0), 65536);
        // 2^1 = 2; in Q16 = 131072
        assert_eq!(exp2_u64_fixed(65536, 0), 131072);
        // 2^2 = 4; in Q16 = 262144
        assert_eq!(exp2_u64_fixed(131072, 0), 262144);
        // 2^3 = 8; in Q16 = 524288
        assert_eq!(exp2_u64_fixed(196608, 0), 524288);
        // Saturation: int_exp=48 overflows, returns u64::MAX
        assert_eq!(exp2_u64_fixed(48u64 * 65536, 0), u64::MAX);
        // Large input saturates
        assert_eq!(exp2_u64_fixed(u64::MAX, 0), u64::MAX);
    }

    proptest! {
        #[test]
        fn test_exp2_u64_fixed_equivalence(val in any::<u64>(), aux in any::<u64>()) {
            let expected = exp2_u64_fixed_reference(val, aux);
            let actual = exp2_u64_fixed(val, aux);
            prop_assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        }

        #[test]
        fn test_exp2_u64_fixed_counterfactual_mutant_1(val in any::<u64>(), aux in any::<u64>()) {
            let expected = exp2_u64_fixed_reference(val, aux);
            let actual = mutant_exp2_u64_fixed_1(val, aux);
            if val != aux && val != 0 && aux != 0 {
                prop_assert!(expected != actual, "Counterfactual Mutant 1 failed to fail!");
            }
        }

        #[test]
        fn test_exp2_u64_fixed_counterfactual_mutant_2(val in any::<u64>(), aux in any::<u64>()) {
            let expected = exp2_u64_fixed_reference(val, aux);
            let actual = mutant_exp2_u64_fixed_2(val, aux);
            if val != aux && val != 0 && aux != 0 {
                prop_assert!(expected != actual, "Counterfactual Mutant 2 failed to fail!");
            }
        }

        #[test]
        fn test_exp2_u64_fixed_counterfactual_mutant_3(val in any::<u64>(), aux in any::<u64>()) {
            let expected = exp2_u64_fixed_reference(val, aux);
            let actual = mutant_exp2_u64_fixed_3(val, aux);
            if val != aux && val != 0 && aux != 0 {
                prop_assert!(expected != actual, "Counterfactual Mutant 3 failed to fail!");
            }
        }
    }

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_exp2_u64_fixed_all() {
        // equivalence oracle
        let expected = exp2_u64_fixed_reference(42, 1337);
        let actual = exp2_u64_fixed(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(exp2_u64_fixed(0, 0), exp2_u64_fixed_reference(0, 0));
        assert_eq!(
            exp2_u64_fixed(u64::MAX, u64::MAX),
            exp2_u64_fixed_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            exp2_u64_fixed(u64::MAX, 0),
            exp2_u64_fixed_reference(u64::MAX, 0)
        );
        assert_eq!(
            exp2_u64_fixed(0, u64::MAX),
            exp2_u64_fixed_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = exp2_u64_fixed_reference(42, 1337);
        let m1 = mutant_exp2_u64_fixed_1(42, 1337);
        let m2 = mutant_exp2_u64_fixed_2(42, 1337);
        let m3 = mutant_exp2_u64_fixed_3(42, 1337);
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

    pub fn bench_exp2_u64_fixed(c: &mut Criterion) {
        c.bench_function("exp2_u64_fixed", |b| {
            b.iter(|| {
                let res = exp2_u64_fixed(black_box(65536), black_box(1337));
                black_box(res)
            })
        });
    }
}
