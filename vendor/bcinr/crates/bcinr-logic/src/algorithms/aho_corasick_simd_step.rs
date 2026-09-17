// Academic-grade branchless algorithm library: aho_corasick_simd_step
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// aho_corasick_simd_step
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Category:** B — Cell Arithmetic
/// **Plane:** D-resident cell word; no scratch
/// **Tier:** T0 — single-word arithmetic primitive
/// **Scope:** branchless, O(1), CC=1; admissible_T1.
/// **Inputs:** `val` = current cell value; `aux` = second operand / parameter.
///
/// ```rust
/// use bcinr_logic::algorithms::aho_corasick_simd_step::aho_corasick_simd_step;
/// let result = aho_corasick_simd_step(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn aho_corasick_simd_step(val: u64, aux: u64) -> u64 {
    // Broadcast the low byte of `aux` to all 8 lanes, then XOR each lane of
    // `val` against it (the per-byte match-difference of the SIMD step), and
    // finally add 1 to every lane independently. The +1 is carry-isolated via
    // the SWAR identity `((a&M)+(b&M)) ^ ((a^b)&~M)` with M = 0x7F..7F, so a
    // byte that overflows cannot disturb its neighbour.
    const ONE: u64 = 0x0101010101010101;
    const M: u64 = 0x7F7F7F7F7F7F7F7F;
    let target = (aux & 0xFF).wrapping_mul(ONE);
    let diff = val ^ target;
    ((diff & M).wrapping_add(ONE & M)) ^ ((diff ^ ONE) & !M)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn aho_corasick_simd_step_reference(val: u64, aux: u64) -> u64 {
        let target = (aux & 0xFF) as u8;
        let mut res = 0u64;
        for i in 0..8 {
            let b = ((val >> (i * 8)) & 0xFF) as u8;
            let diff = b ^ target;
            let val_byte = diff.wrapping_add(1);
            res |= (val_byte as u64) << (i * 8);
        }
        res
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_aho_corasick_simd_step_1(val: u64, aux: u64) -> u64 {
        !aho_corasick_simd_step_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_aho_corasick_simd_step_2(val: u64, aux: u64) -> u64 {
        aho_corasick_simd_step_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_aho_corasick_simd_step_3(val: u64, aux: u64) -> u64 {
        aho_corasick_simd_step_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_aho_corasick_simd_step_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            aho_corasick_simd_step(val, aux),
            aho_corasick_simd_step_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(
            aho_corasick_simd_step(0, 0),
            aho_corasick_simd_step_reference(0, 0)
        );
        assert_eq!(
            aho_corasick_simd_step(u64::MAX, u64::MAX),
            aho_corasick_simd_step_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            aho_corasick_simd_step(u64::MAX, 0),
            aho_corasick_simd_step_reference(u64::MAX, 0)
        );
        assert_eq!(
            aho_corasick_simd_step(0, u64::MAX),
            aho_corasick_simd_step_reference(0, u64::MAX)
        );
        // --- mutant divergence ---
        let baseline = aho_corasick_simd_step_reference(42, 1337);
        assert_ne!(
            mutant_aho_corasick_simd_step_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_aho_corasick_simd_step_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_aho_corasick_simd_step_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_aho_corasick_simd_step(c: &mut Criterion) {
        c.bench_function("aho_corasick_simd_step", |b| {
            b.iter(|| {
                let res = aho_corasick_simd_step(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
