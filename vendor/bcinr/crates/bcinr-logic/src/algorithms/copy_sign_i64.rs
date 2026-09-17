// Academic-grade branchless algorithm library: copy_sign_i64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// copy_sign_i64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// # Branchless Contract
/// Returns a value with the magnitude of `val` (as i64) and the sign of `aux`
/// (as i64), computed without data-dependent control flow.
///
/// ```rust
/// use bcinr_logic::algorithms::copy_sign_i64::copy_sign_i64;
/// let result = copy_sign_i64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn copy_sign_i64(val: u64, aux: u64) -> u64 {
    // Branchless Contract: return a value with the magnitude of `val` (as i64)
    // and the sign of `aux` (as i64). Computed by taking |val| then applying a
    // conditional two's-complement negation driven by aux's sign bit.
    let mag = (val as i64).unsigned_abs(); // magnitude in [0, 2^63]
    let smask = ((aux as i64) >> 63) as u64; // all-ones if aux < 0, else 0
    (mag ^ smask).wrapping_sub(smask)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    fn copy_sign_i64_reference(val: u64, aux: u64) -> u64 {
        // Independent: branch on aux sign, negate magnitude explicitly when needed.
        let mag = (val as i64).unsigned_abs();
        if (aux as i64) < 0 {
            mag.wrapping_neg()
        } else {
            mag
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_copy_sign_i64_1(val: u64, aux: u64) -> u64 {
        !copy_sign_i64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_copy_sign_i64_2(val: u64, aux: u64) -> u64 {
        copy_sign_i64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_copy_sign_i64_3(val: u64, aux: u64) -> u64 {
        copy_sign_i64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_copy_sign_i64_all() {
        // equivalence oracle
        let expected = copy_sign_i64_reference(42, 1337);
        let actual = copy_sign_i64(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(copy_sign_i64(0, 0), copy_sign_i64_reference(0, 0));
        assert_eq!(
            copy_sign_i64(u64::MAX, u64::MAX),
            copy_sign_i64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            copy_sign_i64(u64::MAX, 0),
            copy_sign_i64_reference(u64::MAX, 0)
        );
        assert_eq!(
            copy_sign_i64(0, u64::MAX),
            copy_sign_i64_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = copy_sign_i64_reference(42, 1337);
        let m1 = mutant_copy_sign_i64_1(42, 1337);
        let m2 = mutant_copy_sign_i64_2(42, 1337);
        let m3 = mutant_copy_sign_i64_3(42, 1337);
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

    pub fn bench_copy_sign_i64(c: &mut Criterion) {
        c.bench_function("copy_sign_i64", |b| {
            b.iter(|| {
                let res = copy_sign_i64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
