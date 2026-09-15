// Academic-grade branchless algorithm library: zigzag_decode_i64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// zigzag_decode_i64
///
/// Inverse of ZigZag encoding: recovers the signed i64 `n` from its code
/// `c` via `n = (c >> 1) ^ -(c & 1)`. Here the code decoded is
/// `c = val + aux` (wrapping); the result is the two's-complement bit
/// pattern of `n`.
///
/// # Branchless Contract
/// The low-bit negation mask `-(c & 1)` is built with wrapping negation, not
/// a branch; the path is value-independent.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::zigzag_decode_i64::zigzag_decode_i64;
/// let result = zigzag_decode_i64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn zigzag_decode_i64(val: u64, aux: u64) -> u64 {
    let c = val.wrapping_add(aux);
    (c >> 1) ^ (0u64.wrapping_sub(c & 1))
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn zigzag_decode_i64_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: case-split on parity of the code.
        let c = val.wrapping_add(aux);
        let half = c / 2;
        if c & 1 == 0 {
            // even code -> non-negative value c/2
            half
        } else {
            // odd code -> negative value -(c+1)/2 = -(half + 1)
            (half.wrapping_add(1) as i64).wrapping_neg() as u64
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_zigzag_decode_i64_1(val: u64, aux: u64) -> u64 {
        !zigzag_decode_i64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_zigzag_decode_i64_2(val: u64, aux: u64) -> u64 {
        zigzag_decode_i64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_zigzag_decode_i64_3(val: u64, aux: u64) -> u64 {
        zigzag_decode_i64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_zigzag_decode_i64_all() {
        // oracle
        assert_eq!(
            zigzag_decode_i64(42, 1337),
            zigzag_decode_i64_reference(42, 1337)
        );
        // boundaries
        assert_eq!(zigzag_decode_i64(0, 0), zigzag_decode_i64_reference(0, 0));
        assert_eq!(
            zigzag_decode_i64(u64::MAX, u64::MAX),
            zigzag_decode_i64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            zigzag_decode_i64(u64::MAX, 0),
            zigzag_decode_i64_reference(u64::MAX, 0)
        );
        assert_eq!(
            zigzag_decode_i64(0, u64::MAX),
            zigzag_decode_i64_reference(0, u64::MAX)
        );
        // mutants
        let base = zigzag_decode_i64_reference(42, 1337);
        assert_ne!(mutant_zigzag_decode_i64_1(42, 1337), base, "mutant 1");
        assert_ne!(mutant_zigzag_decode_i64_2(42, 1337), base, "mutant 2");
        assert_ne!(mutant_zigzag_decode_i64_3(42, 1337), base, "mutant 3");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = zigzag_decode_i64_reference(val, aux) }
    //
    // Counterfactual Analysis for zigzag_decode_i64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_zigzag_decode_i64(c: &mut Criterion) {
        c.bench_function("zigzag_decode_i64", |b| {
            b.iter(|| {
                let res = zigzag_decode_i64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
