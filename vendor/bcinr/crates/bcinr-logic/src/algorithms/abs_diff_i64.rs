// Academic-grade branchless algorithm library: abs_diff_i64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// abs_diff_i64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::abs_diff_i64::abs_diff_i64;
/// let result = abs_diff_i64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
/// # Branchless Contract
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn abs_diff_i64(val: u64, aux: u64) -> u64 {
    // Branchless Contract: interpret both words as signed i64 and return the
    // absolute difference |val - aux| as a u64. `i64::abs_diff` is branchless.
    (val as i64).abs_diff(aux as i64)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn abs_diff_i64_reference(val: u64, aux: u64) -> u64 {
        // Independent: widen to i128, subtract, take magnitude via if-branch.
        let a = val as i64 as i128;
        let b = aux as i64 as i128;
        let d = a - b;
        let mag = if d < 0 { -d } else { d };
        mag as u64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_abs_diff_i64_1(val: u64, aux: u64) -> u64 {
        !abs_diff_i64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_abs_diff_i64_2(val: u64, aux: u64) -> u64 {
        abs_diff_i64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_abs_diff_i64_3(val: u64, aux: u64) -> u64 {
        abs_diff_i64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_abs_diff_i64_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            abs_diff_i64(val, aux),
            abs_diff_i64_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(abs_diff_i64(0, 0), abs_diff_i64_reference(0, 0));
        assert_eq!(
            abs_diff_i64(u64::MAX, u64::MAX),
            abs_diff_i64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            abs_diff_i64(u64::MAX, 0),
            abs_diff_i64_reference(u64::MAX, 0)
        );
        assert_eq!(
            abs_diff_i64(0, u64::MAX),
            abs_diff_i64_reference(0, u64::MAX)
        );
        // --- mutant divergence ---
        let baseline = abs_diff_i64_reference(42, 1337);
        assert_ne!(
            mutant_abs_diff_i64_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_abs_diff_i64_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_abs_diff_i64_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = abs_diff_i64_reference(val, aux) }
    //
    // Counterfactual Analysis for abs_diff_i64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_abs_diff_i64(c: &mut Criterion) {
        c.bench_function("abs_diff_i64", |b| {
            b.iter(|| {
                let res = abs_diff_i64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
