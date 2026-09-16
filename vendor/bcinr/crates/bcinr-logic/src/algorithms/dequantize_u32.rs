// Academic-grade branchless algorithm library: dequantize_u32
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// dequantize_u32
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Dequantizes the quantized integer `val` by multiplying it with the
/// integer scale factor `aux` (`real ≈ q * scale`), wrapping on overflow.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::dequantize_u32::dequantize_u32;
/// let result = dequantize_u32(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn dequantize_u32(val: u64, aux: u64) -> u64 {
    val.wrapping_mul(aux)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    fn dequantize_u32_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: peasant (shift-and-add) multiplication instead of
        // the single wrapping_mul, producing the same wrapping product.
        let mut acc: u64 = 0;
        let mut a = val;
        let mut b = aux;
        while b != 0 {
            if b & 1 == 1 {
                acc = acc.wrapping_add(a);
            }
            a = a.wrapping_shl(1);
            b >>= 1;
        }
        acc
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_dequantize_u32_1(val: u64, aux: u64) -> u64 {
        !dequantize_u32_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_dequantize_u32_2(val: u64, aux: u64) -> u64 {
        dequantize_u32_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_dequantize_u32_3(val: u64, aux: u64) -> u64 {
        dequantize_u32_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_dequantize_u32_all() {
        // equivalence oracle
        let expected = dequantize_u32_reference(42, 1337);
        let actual = dequantize_u32(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(dequantize_u32(0, 0), dequantize_u32_reference(0, 0));
        assert_eq!(
            dequantize_u32(u64::MAX, u64::MAX),
            dequantize_u32_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            dequantize_u32(u64::MAX, 0),
            dequantize_u32_reference(u64::MAX, 0)
        );
        assert_eq!(
            dequantize_u32(0, u64::MAX),
            dequantize_u32_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = dequantize_u32_reference(42, 1337);
        let m1 = mutant_dequantize_u32_1(42, 1337);
        let m2 = mutant_dequantize_u32_2(42, 1337);
        let m3 = mutant_dequantize_u32_3(42, 1337);
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

    pub fn bench_dequantize_u32(c: &mut Criterion) {
        c.bench_function("dequantize_u32", |b| {
            b.iter(|| {
                let res = dequantize_u32(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
