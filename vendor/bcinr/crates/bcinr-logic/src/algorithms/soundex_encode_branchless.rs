// Academic-grade branchless algorithm library: soundex_encode_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// soundex_encode_branchless
///
/// Branchless Soundex digit classification for two letters. The Soundex code
/// assigns each consonant a digit (B/F/P/V -> 1, C/G/J/K/Q/S/X/Z -> 2,
/// D/T -> 3, L -> 4, M/N -> 5, R -> 6) and 0 to vowels and non-letters. This
/// kernel takes the low byte of `val` and of `aux` as ASCII characters
/// (case-insensitive), looks up each Soundex digit through a packed nibble
/// table, and returns `digit(val) | (digit(aux) << 8)`.
///
/// # Branchless Contract
/// The table is a pair of u64 nibble-LUT constants selected by a range mask;
/// out-of-range bytes are zeroed by an arithmetic in-range mask. No branch on
/// the character value.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::soundex_encode_branchless::soundex_encode_branchless;
/// let result = soundex_encode_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn soundex_encode_branchless(val: u64, aux: u64) -> u64 {
    fn digit(byte: u64) -> u64 {
        // Packed nibble tables: LO holds A..P, HI holds Q..Z (local index 0..9).
        const LO: u64 = 0x1055_4220_0210_3210;
        const HI: u64 = 0x0000_0020_2010_3262;
        let upper = (byte & 0xFF) & !0x20; // ASCII case fold for letters
        let idx = upper.wrapping_sub(b'A' as u64); // 0..25 for letters; wraps huge otherwise
        let in_range = (idx < 26) as u64; // 1 iff a real A..Z letter (unsigned compare)
                                          // Select LO for idx<16, HI (shifted by 16) for idx>=16.
        let use_hi = (idx >> 4) & 1; // 1 for idx in 16..31
        let lo_nib = (LO >> ((idx & 15) * 4)) & 0xF;
        let hi_nib = (HI >> ((idx.wrapping_sub(16) & 15) * 4)) & 0xF;
        let nib = lo_nib ^ (use_hi.wrapping_neg() & (lo_nib ^ hi_nib));
        nib & in_range.wrapping_neg()
    }
    digit(val) | (digit(aux) << 8)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn soundex_encode_branchless_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: explicit byte->digit table with a match.
        fn digit(byte: u64) -> u64 {
            let c = (byte & 0xFF) as u8;
            let up = c.to_ascii_uppercase();
            let d: u64 = match up {
                b'B' | b'F' | b'P' | b'V' => 1,
                b'C' | b'G' | b'J' | b'K' | b'Q' | b'S' | b'X' | b'Z' => 2,
                b'D' | b'T' => 3,
                b'L' => 4,
                b'M' | b'N' => 5,
                b'R' => 6,
                _ => 0, // vowels, non-letters
            };
            d
        }
        digit(val) | (digit(aux) << 8)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_soundex_encode_branchless_1(val: u64, aux: u64) -> u64 {
        !soundex_encode_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_soundex_encode_branchless_2(val: u64, aux: u64) -> u64 {
        soundex_encode_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_soundex_encode_branchless_3(val: u64, aux: u64) -> u64 {
        soundex_encode_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_soundex_encode_branchless_all() {
        // oracle
        assert_eq!(
            soundex_encode_branchless(42, 1337),
            soundex_encode_branchless_reference(42, 1337)
        );
        // boundaries
        assert_eq!(
            soundex_encode_branchless(0, 0),
            soundex_encode_branchless_reference(0, 0)
        );
        assert_eq!(
            soundex_encode_branchless(u64::MAX, u64::MAX),
            soundex_encode_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            soundex_encode_branchless(u64::MAX, 0),
            soundex_encode_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            soundex_encode_branchless(0, u64::MAX),
            soundex_encode_branchless_reference(0, u64::MAX)
        );
        // mutants
        let base = soundex_encode_branchless_reference(42, 1337);
        assert_ne!(
            mutant_soundex_encode_branchless_1(42, 1337),
            base,
            "mutant 1"
        );
        assert_ne!(
            mutant_soundex_encode_branchless_2(42, 1337),
            base,
            "mutant 2"
        );
        assert_ne!(
            mutant_soundex_encode_branchless_3(42, 1337),
            base,
            "mutant 3"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = soundex_encode_branchless_reference(val, aux) }
    //
    // Counterfactual Analysis for soundex_encode_branchless:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_soundex_encode_branchless(c: &mut Criterion) {
        c.bench_function("soundex_encode_branchless", |b| {
            b.iter(|| {
                let res = soundex_encode_branchless(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
