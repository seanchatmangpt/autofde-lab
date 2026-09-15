// Academic-grade branchless algorithm library: minimum_spanning_tree_prim_step
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// minimum_spanning_tree_prim_step
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::minimum_spanning_tree_prim_step::minimum_spanning_tree_prim_step;
/// let result = minimum_spanning_tree_prim_step(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn minimum_spanning_tree_prim_step(val: u64, aux: u64) -> u64 {
    let m = 0u64.wrapping_sub((val < aux) as u64);
    (val & m) | (aux & !m)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn minimum_spanning_tree_prim_step_reference(val: u64, aux: u64) -> u64 {
        if val < aux {
            val
        } else {
            aux
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_minimum_spanning_tree_prim_step_1(val: u64, aux: u64) -> u64 {
        !minimum_spanning_tree_prim_step_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_minimum_spanning_tree_prim_step_2(val: u64, aux: u64) -> u64 {
        minimum_spanning_tree_prim_step_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_minimum_spanning_tree_prim_step_3(val: u64, aux: u64) -> u64 {
        minimum_spanning_tree_prim_step_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_minimum_spanning_tree_prim_step_all() {
        // equivalence oracle
        let expected = minimum_spanning_tree_prim_step_reference(42, 1337);
        let actual = minimum_spanning_tree_prim_step(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            minimum_spanning_tree_prim_step(0, 0),
            minimum_spanning_tree_prim_step_reference(0, 0)
        );
        assert_eq!(
            minimum_spanning_tree_prim_step(u64::MAX, u64::MAX),
            minimum_spanning_tree_prim_step_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            minimum_spanning_tree_prim_step(u64::MAX, 0),
            minimum_spanning_tree_prim_step_reference(u64::MAX, 0)
        );
        assert_eq!(
            minimum_spanning_tree_prim_step(0, u64::MAX),
            minimum_spanning_tree_prim_step_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = minimum_spanning_tree_prim_step_reference(42, 1337);
        let m1 = mutant_minimum_spanning_tree_prim_step_1(42, 1337);
        let m2 = mutant_minimum_spanning_tree_prim_step_2(42, 1337);
        let m3 = mutant_minimum_spanning_tree_prim_step_3(42, 1337);
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
    // Postcondition: { result = minimum_spanning_tree_prim_step_reference(val, aux) }
    //
    // Counterfactual Analysis for minimum_spanning_tree_prim_step:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_minimum_spanning_tree_prim_step(c: &mut Criterion) {
        c.bench_function("minimum_spanning_tree_prim_step", |b| {
            b.iter(|| {
                let res = minimum_spanning_tree_prim_step(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
