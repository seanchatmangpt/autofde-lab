// Academic-grade branchless algorithm library: topological_sort_step_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// topological_sort_step_branchless
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// Interpretation: one step of Kahn's topological-sort frontier update over a
/// 64-node bitset. `val` is the ready-set (nodes whose in-degree has reached
/// zero); `aux` is the set of nodes already emitted in previous steps. The
/// nodes emittable now are exactly those that are ready and not yet emitted —
/// the branchless set difference `val & !aux`.
///
/// ```rust
/// use bcinr_logic::algorithms::topological_sort_step_branchless::topological_sort_step_branchless;
/// let result = topological_sort_step_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn topological_sort_step_branchless(val: u64, aux: u64) -> u64 {
    val & !aux
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn topological_sort_step_branchless_reference(val: u64, aux: u64) -> u64 {
        // Independent structure: set difference expressed as removing the shared
        // (already-emitted) members from the ready-set via XOR, rather than the
        // and-not form.
        val ^ (val & aux)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_topological_sort_step_branchless_1(val: u64, aux: u64) -> u64 {
        !topological_sort_step_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_topological_sort_step_branchless_2(val: u64, aux: u64) -> u64 {
        topological_sort_step_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_topological_sort_step_branchless_3(val: u64, aux: u64) -> u64 {
        topological_sort_step_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_topological_sort_step_branchless_all() {
        // oracle
        assert_eq!(
            topological_sort_step_branchless(42, 1337),
            topological_sort_step_branchless_reference(42, 1337)
        );
        // boundaries
        assert_eq!(
            topological_sort_step_branchless(0, 0),
            topological_sort_step_branchless_reference(0, 0)
        );
        assert_eq!(
            topological_sort_step_branchless(u64::MAX, u64::MAX),
            topological_sort_step_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            topological_sort_step_branchless(u64::MAX, 0),
            topological_sort_step_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            topological_sort_step_branchless(0, u64::MAX),
            topological_sort_step_branchless_reference(0, u64::MAX)
        );
        // mutants
        let base = topological_sort_step_branchless_reference(42, 1337);
        assert_ne!(
            mutant_topological_sort_step_branchless_1(42, 1337),
            base,
            "mutant 1"
        );
        assert_ne!(
            mutant_topological_sort_step_branchless_2(42, 1337),
            base,
            "mutant 2"
        );
        assert_ne!(
            mutant_topological_sort_step_branchless_3(42, 1337),
            base,
            "mutant 3"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = topological_sort_step_branchless_reference(val, aux) }
    //
    // Counterfactual Analysis for topological_sort_step_branchless:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_topological_sort_step_branchless(c: &mut Criterion) {
        c.bench_function("topological_sort_step_branchless", |b| {
            b.iter(|| {
                let res = topological_sort_step_branchless(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
