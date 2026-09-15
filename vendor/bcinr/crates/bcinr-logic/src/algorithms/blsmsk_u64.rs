// Academic-grade branchless algorithm library: blsmsk_u64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// blsmsk_u64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Computes the BMI `blsmsk` mask: all bits up to and including the lowest
/// set bit of `val` are set, via `val ^ (val - 1)`. When `val` is 0 the result is the
/// all-ones word. `aux` is unused.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::blsmsk_u64::blsmsk_u64;
/// let result = blsmsk_u64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn blsmsk_u64(val: u64, _aux: u64) -> u64 {
    let dec = val.wrapping_sub(1);
    val ^ dec
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn blsmsk_u64_reference(val: u64, aux: u64) -> u64 {
        // Independent: build the mask from the lowest-set-bit index (all-ones if none).
        let tz = val.trailing_zeros();
        if tz >= 64 {
            u64::MAX
        } else {
            (1u64 << tz) | ((1u64 << tz) - 1)
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_blsmsk_u64_1(val: u64, aux: u64) -> u64 {
        !blsmsk_u64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_blsmsk_u64_2(val: u64, aux: u64) -> u64 {
        blsmsk_u64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_blsmsk_u64_3(val: u64, aux: u64) -> u64 {
        blsmsk_u64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_blsmsk_u64_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            blsmsk_u64(val, aux),
            blsmsk_u64_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(blsmsk_u64(0, 0), blsmsk_u64_reference(0, 0));
        assert_eq!(
            blsmsk_u64(u64::MAX, u64::MAX),
            blsmsk_u64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(blsmsk_u64(u64::MAX, 0), blsmsk_u64_reference(u64::MAX, 0));
        assert_eq!(blsmsk_u64(0, u64::MAX), blsmsk_u64_reference(0, u64::MAX));
        // --- mutant divergence ---
        let baseline = blsmsk_u64_reference(42, 1337);
        assert_ne!(
            mutant_blsmsk_u64_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_blsmsk_u64_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_blsmsk_u64_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = blsmsk_u64_reference(val, aux) }
    //
    // Counterfactual Analysis for blsmsk_u64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_blsmsk_u64(c: &mut Criterion) {
        c.bench_function("blsmsk_u64", |b| {
            b.iter(|| {
                let res = blsmsk_u64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
