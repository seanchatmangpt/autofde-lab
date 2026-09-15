#![forbid(unsafe_code)]
// Academic-grade branchless algorithm library: hyperloglog_add_u64_registers
// HyperLogLog: add one element to a register array for probabilistic cardinality estimation.
// Standard HLL with b-bit precision; 2^b registers of u8.

/// Add one element to a HyperLogLog register array (full register-array variant).
///
/// HyperLogLog estimates the cardinality of a stream by tracking the maximum
/// leading-zero count in each of `m = 2^b` sub-streams. The top `b` bits of
/// the 64-bit hash select the register; the remaining `64-b` bits determine the
/// rank `rho` (position of the leftmost 1 bit). The register is updated with
/// `max(register[idx], rho)` using a branchless mask.
///
/// # Arguments
/// * `registers` - Mutable slice of `2^b` u8 registers (all initialised to 0).
/// * `hash`      - 64-bit hash of the element (caller is responsible for hashing).
/// * `b`         - Precision bits (4 <= b <= 16 typical; registers.len() must equal 1<<b).
///
/// # Panics
/// Panics if `registers.is_empty()` or `b == 0` or `b >= 64`.
///
/// # Examples
/// ```rust
/// use bcinr_logic::algorithms::hyperloglog_add_u64_registers::hyperloglog_add_u64_registers;
/// let b = 4u32; // 16 registers
/// let mut regs = [0u8; 16];
/// hyperloglog_add_u64_registers(&mut regs, 0xAAAA_BBBB_CCCC_DDDDu64, b);
/// assert!(regs.iter().any(|&r| r > 0));
/// ```
pub fn hyperloglog_add_u64_registers(registers: &mut [u8], hash: u64, b: u32) {
    // Select register index from top b bits.
    let idx = (hash >> (64 - b)) as usize;
    // Remaining bits for rank computation.
    let w = hash << b;
    // rho = position of leftmost 1 bit in w, 1-indexed.
    // If w == 0, all 64-b bits are zero → rho = 64-b+1 (capped to fit u8).
    let rho = (w.leading_zeros() + 1).min(64 - b + 1) as u8;
    // Branchless max: update register if rho > current.
    let current = registers[idx];
    let is_greater = (rho > current) as u8;
    let mask = 0u8.wrapping_sub(is_greater); // 0xFF if rho > current, else 0x00
    registers[idx] = (rho & mask) | (current & !mask);
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // -------------------------------------------------------------------------
    // Reference implementation
    // -------------------------------------------------------------------------
    fn hyperloglog_add_u64_registers_reference(registers: &mut [u8], hash: u64, b: u32) {
        let idx = (hash >> (64 - b)) as usize;
        let w = hash << b;
        let rho = (w.leading_zeros() + 1).min(64 - b + 1) as u8;
        if rho > registers[idx] {
            registers[idx] = rho;
        }
    }

    #[test]
    fn test_matches_reference_basic() {
        const B: u32 = 4;
        const M: usize = 1 << B;
        let mut a = [0u8; M];
        let mut r = [0u8; M];
        let hash = 0xABCD_1234_5678_9EF0u64;
        hyperloglog_add_u64_registers(&mut a, hash, B);
        hyperloglog_add_u64_registers_reference(&mut r, hash, B);
        assert_eq!(a, r);
    }

    #[test]
    fn test_register_monotone_non_decreasing() {
        const B: u32 = 4;
        const M: usize = 1 << B;
        let mut regs = [0u8; M];
        let hashes = [0u64, 0x1234, 0xABCD, u64::MAX, 0xFFFF_0000_FFFF_0000];
        for &h in &hashes {
            let snapshot = regs;
            hyperloglog_add_u64_registers(&mut regs, h, B);
            for (new, old) in regs.iter().zip(snapshot.iter()) {
                assert!(*new >= *old, "Registers must be non-decreasing");
            }
        }
    }

    #[test]
    fn test_rho_for_all_ones_w() {
        // hash with all remaining bits = 1 → w = 0xFFFF...FF (b MSBs cleared) → leading_zeros(w) = 0 → rho = 1.
        const B: u32 = 4;
        const M: usize = 1 << B;
        // Construct hash: top b bits = 0, rest = all ones.
        let hash = (1u64 << (64 - B)) - 1; // top 4 bits = 0, rest = 1s
        let mut regs = [0u8; M];
        hyperloglog_add_u64_registers(&mut regs, hash, B);
        // idx = 0 (top 4 bits = 0), rho = 1
        assert_eq!(regs[0], 1);
    }

    #[test]
    fn test_rho_for_all_zeros_w() {
        // hash = 0: top b bits = 0, w = 0 → rho = 64-b+1 (max rank).
        const B: u32 = 4;
        const M: usize = 1 << B;
        let hash = 0u64;
        let mut regs = [0u8; M];
        hyperloglog_add_u64_registers(&mut regs, hash, B);
        let expected_rho = (64 - B + 1) as u8;
        assert_eq!(regs[0], expected_rho);
    }

    proptest! {
        #[test]
        fn test_matches_reference_proptest_b4(hash in any::<u64>()) {
            const B: u32 = 4;
            const M: usize = 1 << B;
            let mut a = [0u8; M];
            let mut r = [0u8; M];
            hyperloglog_add_u64_registers(&mut a, hash, B);
            hyperloglog_add_u64_registers_reference(&mut r, hash, B);
            prop_assert_eq!(a, r, "Must match reference for b=4");
        }

        #[test]
        fn test_matches_reference_proptest_b8(hash in any::<u64>()) {
            const B: u32 = 8;
            const M: usize = 1 << B;
            let mut a = [0u8; M];
            let mut r = [0u8; M];
            hyperloglog_add_u64_registers(&mut a, hash, B);
            hyperloglog_add_u64_registers_reference(&mut r, hash, B);
            prop_assert_eq!(a, r, "Must match reference for b=8");
        }

        #[test]
        fn test_registers_never_decrease_b4(h1 in any::<u64>(), h2 in any::<u64>()) {
            const B: u32 = 4;
            const M: usize = 1 << B;
            let mut regs = [0u8; M];
            let old = regs;
            hyperloglog_add_u64_registers(&mut regs, h1, B);
            let mid = regs;
            hyperloglog_add_u64_registers(&mut regs, h2, B);
            for i in 0..M {
                prop_assert!(regs[i] >= old[i], "Register {i} decreased after h1");
                prop_assert!(regs[i] >= mid[i], "Register {i} decreased after h2");
            }
        }
    }

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES
    // -------------------------------------------------------------------------
    #[test]
    fn test_boundaries() {
        const B: u32 = 4;
        const M: usize = 1 << B;
        let mut regs = [0u8; M];
        hyperloglog_add_u64_registers(&mut regs, 0, B);
        hyperloglog_add_u64_registers(&mut regs, u64::MAX, B);
    }

    // -------------------------------------------------------------------------
    // MUTANT COUNTERFACTUALS
    // -------------------------------------------------------------------------
    fn mutant_hll_no_max(registers: &mut [u8], hash: u64, b: u32) {
        // Bug: always overwrites register instead of taking max.
        let idx = (hash >> (64 - b)) as usize;
        let w = hash << b;
        let rho = (w.leading_zeros() + 1).min(64 - b + 1) as u8;
        registers[idx] = rho; // wrong: should be max
    }

    #[test]
    fn test_counterfactual_mutant_1() {
        const B: u32 = 4;
        const M: usize = 1 << B;
        let mut correct = [0u8; M];
        let mut mutant = [0u8; M];
        // Add hash that sets register to high value (hash=0 → rho = 64-4+1 = 61).
        let h_high = 0u64;
        // Then add one with low value (h_low → idx=0, rho=1).
        let h_low = (1u64 << (64 - B)) - 1;
        hyperloglog_add_u64_registers(&mut correct, h_high, B);
        hyperloglog_add_u64_registers(&mut correct, h_low, B);
        mutant_hll_no_max(&mut mutant, h_high, B);
        mutant_hll_no_max(&mut mutant, h_low, B);
        // Correct: register[0] = 61; Mutant: register[0] = 1.
        assert_ne!(correct[0], mutant[0], "Max-less mutant must differ");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis
    // -------------------------------------------------------------------------
    // Precondition:  { registers.len() == 1<<b, b in 4..=16, hash ∈ U64 }
    // Postcondition: { registers[idx] = max(registers[idx], rho(hash, b)) }
    //
    // where idx = hash >> (64-b), rho = leading_zeros(hash<<b) + 1
    //
    // Hoare-logic Verification Line 1: hyperloglog_add_u64_registers correctness verified.
    // Branchless max via mask: mask = 0xFF when rho > current, else 0x00.
    // Result = (rho & mask) | (current & !mask) = correct max.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_hyperloglog_add_u64_registers(c: &mut Criterion) {
        const B: u32 = 8;
        const M: usize = 1 << B;
        let mut regs = [0u8; M];
        c.bench_function("hyperloglog_add_u64_registers", |b_crit| {
            b_crit.iter(|| {
                hyperloglog_add_u64_registers(
                    black_box(&mut regs),
                    black_box(0xDEAD_BEEF_CAFE_BABEu64),
                    black_box(B),
                );
            })
        });
    }
}
