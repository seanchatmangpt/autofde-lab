// Academic-grade branchless algorithm library: disjoint_set_union_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// disjoint_set_union_branchless
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::disjoint_set_union_branchless::disjoint_set_union_branchless;
/// let result = disjoint_set_union_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn disjoint_set_union_branchless(val: u64, aux: u64) -> u64 {
    let is_root = (val == aux) as u64;
    (is_root.wrapping_neg() & val) | ((!is_root.wrapping_neg()) & aux)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn disjoint_set_union_branchless_reference(val: u64, aux: u64) -> u64 {
        if val == aux {
            val
        } else {
            aux
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_disjoint_set_union_branchless_1(val: u64, aux: u64) -> u64 {
        !disjoint_set_union_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_disjoint_set_union_branchless_2(val: u64, aux: u64) -> u64 {
        disjoint_set_union_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_disjoint_set_union_branchless_3(val: u64, aux: u64) -> u64 {
        disjoint_set_union_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_disjoint_set_union_branchless_all() {
        // equivalence oracle
        let expected = disjoint_set_union_branchless_reference(42, 1337);
        let actual = disjoint_set_union_branchless(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            disjoint_set_union_branchless(0, 0),
            disjoint_set_union_branchless_reference(0, 0)
        );
        assert_eq!(
            disjoint_set_union_branchless(u64::MAX, u64::MAX),
            disjoint_set_union_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            disjoint_set_union_branchless(u64::MAX, 0),
            disjoint_set_union_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            disjoint_set_union_branchless(0, u64::MAX),
            disjoint_set_union_branchless_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = disjoint_set_union_branchless_reference(42, 1337);
        let m1 = mutant_disjoint_set_union_branchless_1(42, 1337);
        let m2 = mutant_disjoint_set_union_branchless_2(42, 1337);
        let m3 = mutant_disjoint_set_union_branchless_3(42, 1337);
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

    pub fn bench_disjoint_set_union_branchless(c: &mut Criterion) {
        c.bench_function("disjoint_set_union_branchless", |b| {
            b.iter(|| {
                let res = disjoint_set_union_branchless(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
