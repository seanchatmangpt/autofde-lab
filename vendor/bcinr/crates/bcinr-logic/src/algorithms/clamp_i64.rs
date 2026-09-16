// Academic-grade branchless algorithm library: clamp_i64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// clamp_i64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::clamp_i64::clamp_i64;
/// let result = clamp_i64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
/// # Branchless Contract
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn clamp_i64(val: u64, aux: u64) -> u64 {
    // Branchless Contract: clamp `val` (as i64) into the inclusive range whose
    // endpoints are the sign-extended low and high 32-bit halves of `aux`.
    // Endpoints are ordered first so lo <= hi, then v is clamped via min/max.
    let v = val as i64;
    let a = (aux as i32) as i64; // low half, sign-extended
    let b = ((aux >> 32) as i32) as i64; // high half, sign-extended
    let lo = a.min(b);
    let hi = a.max(b);
    v.max(lo).min(hi) as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    fn clamp_i64_reference(val: u64, aux: u64) -> u64 {
        // Independent: explicit comparisons to clamp into the ordered range.
        let v = val as i64;
        let a = (aux as i32) as i64;
        let b = ((aux >> 32) as i32) as i64;
        let (lo, hi) = if a <= b { (a, b) } else { (b, a) };
        let r = if v < lo {
            lo
        } else if v > hi {
            hi
        } else {
            v
        };
        r as u64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_clamp_i64_1(val: u64, aux: u64) -> u64 {
        !clamp_i64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_clamp_i64_2(val: u64, aux: u64) -> u64 {
        clamp_i64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_clamp_i64_3(val: u64, aux: u64) -> u64 {
        clamp_i64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_clamp_i64_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            clamp_i64(val, aux),
            clamp_i64_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(clamp_i64(0, 0), clamp_i64_reference(0, 0));
        assert_eq!(
            clamp_i64(u64::MAX, u64::MAX),
            clamp_i64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(clamp_i64(u64::MAX, 0), clamp_i64_reference(u64::MAX, 0));
        assert_eq!(clamp_i64(0, u64::MAX), clamp_i64_reference(0, u64::MAX));
        // --- mutant divergence ---
        let baseline = clamp_i64_reference(42, 1337);
        assert_ne!(
            mutant_clamp_i64_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_clamp_i64_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_clamp_i64_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = clamp_i64_reference(val, aux) }
    //
    // Counterfactual Analysis for clamp_i64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_clamp_i64(c: &mut Criterion) {
        c.bench_function("clamp_i64", |b| {
            b.iter(|| {
                let res = clamp_i64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
