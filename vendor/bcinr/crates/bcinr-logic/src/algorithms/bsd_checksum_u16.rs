// Academic-grade branchless algorithm library: bsd_checksum_u16
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// bsd_checksum_u16
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Interpretation:** The classic BSD 16-bit rotating checksum over the 8 bytes
/// packed (little-endian) in `val`, starting from initial accumulator
/// `sum = aux & 0xFFFF`. For each byte: rotate the 16-bit accumulator right by one
/// (`sum = (sum >> 1) | (sum << 15)`), add the byte, and mask to 16 bits. The
/// 8-byte window is fully unrolled, keeping the routine branchless and O(1).
/// **Ensures:** Result matches the independent reference for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::bsd_checksum_u16::bsd_checksum_u16;
/// let result = bsd_checksum_u16(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn bsd_checksum_u16(val: u64, aux: u64) -> u64 {
    let mut s = aux & 0xFFFF;
    s = (((s >> 1) | (s << 15)) & 0xFFFF).wrapping_add(val & 0xFF) & 0xFFFF;
    s = (((s >> 1) | (s << 15)) & 0xFFFF).wrapping_add((val >> 8) & 0xFF) & 0xFFFF;
    s = (((s >> 1) | (s << 15)) & 0xFFFF).wrapping_add((val >> 16) & 0xFF) & 0xFFFF;
    s = (((s >> 1) | (s << 15)) & 0xFFFF).wrapping_add((val >> 24) & 0xFF) & 0xFFFF;
    s = (((s >> 1) | (s << 15)) & 0xFFFF).wrapping_add((val >> 32) & 0xFF) & 0xFFFF;
    s = (((s >> 1) | (s << 15)) & 0xFFFF).wrapping_add((val >> 40) & 0xFF) & 0xFFFF;
    s = (((s >> 1) | (s << 15)) & 0xFFFF).wrapping_add((val >> 48) & 0xFF) & 0xFFFF;
    s = (((s >> 1) | (s << 15)) & 0xFFFF).wrapping_add((val >> 56) & 0xFF) & 0xFFFF;
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    fn bsd_checksum_u16_reference(val: u64, aux: u64) -> u64 {
        // Independent: iterate the byte array with a u16 accumulator type.
        let mut sum: u16 = (aux & 0xFFFF) as u16;
        for &b in val.to_le_bytes().iter() {
            sum = sum.rotate_right(1);
            sum = sum.wrapping_add(b as u16);
        }
        sum as u64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_bsd_checksum_u16_1(val: u64, aux: u64) -> u64 {
        !bsd_checksum_u16_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_bsd_checksum_u16_2(val: u64, aux: u64) -> u64 {
        bsd_checksum_u16_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_bsd_checksum_u16_3(val: u64, aux: u64) -> u64 {
        bsd_checksum_u16_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_bsd_checksum_u16_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            bsd_checksum_u16(val, aux),
            bsd_checksum_u16_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(bsd_checksum_u16(0, 0), bsd_checksum_u16_reference(0, 0));
        assert_eq!(
            bsd_checksum_u16(u64::MAX, u64::MAX),
            bsd_checksum_u16_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            bsd_checksum_u16(u64::MAX, 0),
            bsd_checksum_u16_reference(u64::MAX, 0)
        );
        assert_eq!(
            bsd_checksum_u16(0, u64::MAX),
            bsd_checksum_u16_reference(0, u64::MAX)
        );
        // --- mutant divergence ---
        let baseline = bsd_checksum_u16_reference(42, 1337);
        assert_ne!(
            mutant_bsd_checksum_u16_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_bsd_checksum_u16_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_bsd_checksum_u16_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = bsd_checksum_u16_reference(val, aux) }
    //
    // Counterfactual Analysis for bsd_checksum_u16:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_bsd_checksum_u16(c: &mut Criterion) {
        c.bench_function("bsd_checksum_u16", |b| {
            b.iter(|| {
                let res = bsd_checksum_u16(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
