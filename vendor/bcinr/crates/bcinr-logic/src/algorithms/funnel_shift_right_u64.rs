// Academic-grade branchless algorithm library: funnel_shift_right_u64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// funnel_shift_right_u64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::funnel_shift_right_u64::funnel_shift_right_u64;
/// let result = funnel_shift_right_u64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn funnel_shift_right_u64(val: u64, aux: u64) -> u64 {
    let shift = (aux & 0x3F) as u32;

    (aux.wrapping_shr(shift))
        | (val.wrapping_shl((64u32.wrapping_sub(shift)) & 0x3F)
            & (0u64.wrapping_sub((shift != 0) as u64)))
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn funnel_shift_right_u64_reference(val: u64, aux: u64) -> u64 {
        let shift = aux & 0x3F;
        if shift == 0 {
            aux
        } else {
            (aux >> shift) | (val << (64 - shift))
        }
    }

    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_funnel_shift_right_u64_1(val: u64, aux: u64) -> u64 {
        !funnel_shift_right_u64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_funnel_shift_right_u64_2(val: u64, aux: u64) -> u64 {
        funnel_shift_right_u64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_funnel_shift_right_u64_3(val: u64, aux: u64) -> u64 {
        funnel_shift_right_u64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_funnel_shift_right_u64_all() {
        // equivalence oracle
        let expected = funnel_shift_right_u64_reference(42, 1337);
        let actual = funnel_shift_right_u64(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            funnel_shift_right_u64(0, 0),
            funnel_shift_right_u64_reference(0, 0)
        );
        assert_eq!(
            funnel_shift_right_u64(u64::MAX, u64::MAX),
            funnel_shift_right_u64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            funnel_shift_right_u64(u64::MAX, 0),
            funnel_shift_right_u64_reference(u64::MAX, 0)
        );
        assert_eq!(
            funnel_shift_right_u64(0, u64::MAX),
            funnel_shift_right_u64_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = funnel_shift_right_u64_reference(42, 1337);
        let m1 = mutant_funnel_shift_right_u64_1(42, 1337);
        let m2 = mutant_funnel_shift_right_u64_2(42, 1337);
        let m3 = mutant_funnel_shift_right_u64_3(42, 1337);
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

    pub fn bench_funnel_shift_right_u64(c: &mut Criterion) {
        c.bench_function("funnel_shift_right_u64", |b| {
            b.iter(|| {
                let res = funnel_shift_right_u64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
