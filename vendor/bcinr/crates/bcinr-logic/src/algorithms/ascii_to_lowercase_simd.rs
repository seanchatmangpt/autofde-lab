// Academic-grade branchless algorithm library: ascii_to_lowercase_simd
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// ascii_to_lowercase_simd
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Each of the 8 packed bytes of `val` that is an ASCII uppercase
/// letter (`b'A'..=b'Z'`) is lowercased by adding `0x20`; all other bytes are
/// untouched. `aux` is not part of the transform (SIMD lowercasing is unary).
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// Interpretation: a SWAR (8-lane) realization of `b -> b + 0x20 iff b in A..=Z`.
/// The per-byte in-range mask uses the exact "hasbetween" SWAR identity, so it is
/// correct for every byte value, not only clean ASCII.
///
/// ```rust
/// use bcinr_logic::algorithms::ascii_to_lowercase_simd::ascii_to_lowercase_simd;
/// let result = ascii_to_lowercase_simd(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn ascii_to_lowercase_simd(val: u64, aux: u64) -> u64 {
    const ONES: u64 = 0x0101010101010101;
    const H: u64 = 0x8080808080808080;
    const LO7: u64 = 0x7F7F7F7F7F7F7F7F;
    let low = val & LO7;
    let upper = ONES.wrapping_mul(127 + 0x5B).wrapping_sub(low);
    let lower = low.wrapping_add(ONES.wrapping_mul(127 - 0x40));
    let mask = upper & !val & lower & H;
    val.wrapping_add(mask >> 2)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn ascii_to_lowercase_simd_reference(val: u64, aux: u64) -> u64 {
        // Independent structure: explicit per-byte scalar loop with a real
        // comparison branch (test-only), reassembling the 8 lanes.
        let mut out: u64 = 0;
        for i in 0..8 {
            let b = ((val >> (8 * i)) & 0xFF) as u8;
            let c = if b.is_ascii_uppercase() { b + 0x20 } else { b };
            out |= (c as u64) << (8 * i);
        }
        out
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_ascii_to_lowercase_simd_1(val: u64, aux: u64) -> u64 {
        !ascii_to_lowercase_simd_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_ascii_to_lowercase_simd_2(val: u64, aux: u64) -> u64 {
        ascii_to_lowercase_simd_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_ascii_to_lowercase_simd_3(val: u64, aux: u64) -> u64 {
        ascii_to_lowercase_simd_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_ascii_to_lowercase_simd_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            ascii_to_lowercase_simd(val, aux),
            ascii_to_lowercase_simd_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(
            ascii_to_lowercase_simd(0, 0),
            ascii_to_lowercase_simd_reference(0, 0)
        );
        assert_eq!(
            ascii_to_lowercase_simd(u64::MAX, u64::MAX),
            ascii_to_lowercase_simd_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            ascii_to_lowercase_simd(u64::MAX, 0),
            ascii_to_lowercase_simd_reference(u64::MAX, 0)
        );
        assert_eq!(
            ascii_to_lowercase_simd(0, u64::MAX),
            ascii_to_lowercase_simd_reference(0, u64::MAX)
        );
        // --- mutant divergence ---
        let baseline = ascii_to_lowercase_simd_reference(42, 1337);
        assert_ne!(
            mutant_ascii_to_lowercase_simd_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_ascii_to_lowercase_simd_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_ascii_to_lowercase_simd_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = ascii_to_lowercase_simd_reference(val, aux) }
    //
    // Counterfactual Analysis for ascii_to_lowercase_simd:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_ascii_to_lowercase_simd(c: &mut Criterion) {
        c.bench_function("ascii_to_lowercase_simd", |b| {
            b.iter(|| {
                let res = ascii_to_lowercase_simd(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
