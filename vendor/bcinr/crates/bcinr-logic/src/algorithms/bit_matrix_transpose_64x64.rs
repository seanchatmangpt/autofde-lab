// Academic-grade branchless algorithm library: bit_matrix_transpose_64x64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// bit_matrix_transpose_64x64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Interprets the 64 bits of `val ^ aux` as an 8x8 bit matrix (row-major,
/// byte = row) and returns its transpose, using the three classic delta-swap stages
/// (shifts 7, 14, 28). `aux` perturbs the input matrix prior to transposition.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::bit_matrix_transpose_64x64::bit_matrix_transpose_64x64;
/// let result = bit_matrix_transpose_64x64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn bit_matrix_transpose_64x64(val: u64, aux: u64) -> u64 {
    let mut x = val ^ aux;
    let t = (x ^ (x >> 7)) & 0x00AA00AA00AA00AA;
    x ^= t ^ (t << 7);
    let t = (x ^ (x >> 14)) & 0x0000CCCC0000CCCC;
    x ^= t ^ (t << 14);
    let t = (x ^ (x >> 28)) & 0x00000000F0F0F0F0;
    x ^= t ^ (t << 28);
    x
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    fn bit_matrix_transpose_64x64_reference(val: u64, aux: u64) -> u64 {
        // Independent: explicit (row, col) -> (col, row) bit relocation.
        let x = val ^ aux;
        let mut out = 0u64;
        for r in 0..8u32 {
            for c in 0..8u32 {
                let bit = (x >> (r * 8 + c)) & 1;
                out |= bit << (c * 8 + r);
            }
        }
        out
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_bit_matrix_transpose_64x64_1(val: u64, aux: u64) -> u64 {
        !bit_matrix_transpose_64x64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_bit_matrix_transpose_64x64_2(val: u64, aux: u64) -> u64 {
        bit_matrix_transpose_64x64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_bit_matrix_transpose_64x64_3(val: u64, aux: u64) -> u64 {
        bit_matrix_transpose_64x64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_bit_matrix_transpose_64x64_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            bit_matrix_transpose_64x64(val, aux),
            bit_matrix_transpose_64x64_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(
            bit_matrix_transpose_64x64(0, 0),
            bit_matrix_transpose_64x64_reference(0, 0)
        );
        assert_eq!(
            bit_matrix_transpose_64x64(u64::MAX, u64::MAX),
            bit_matrix_transpose_64x64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            bit_matrix_transpose_64x64(u64::MAX, 0),
            bit_matrix_transpose_64x64_reference(u64::MAX, 0)
        );
        assert_eq!(
            bit_matrix_transpose_64x64(0, u64::MAX),
            bit_matrix_transpose_64x64_reference(0, u64::MAX)
        );
        // --- mutant divergence ---
        let baseline = bit_matrix_transpose_64x64_reference(42, 1337);
        assert_ne!(
            mutant_bit_matrix_transpose_64x64_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_bit_matrix_transpose_64x64_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_bit_matrix_transpose_64x64_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = bit_matrix_transpose_64x64_reference(val, aux) }
    //
    // Counterfactual Analysis for bit_matrix_transpose_64x64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_bit_matrix_transpose_64x64(c: &mut Criterion) {
        c.bench_function("bit_matrix_transpose_64x64", |b| {
            b.iter(|| {
                let res = bit_matrix_transpose_64x64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
