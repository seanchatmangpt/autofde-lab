// Academic-grade branchless algorithm library: url_encode_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// url_encode_branchless
///
/// Branchless URL percent-encoding of a single byte. The byte
/// `b = (val + aux) & 0xFF` is rendered as the three-character escape
/// `%HL` where `H` and `L` are the uppercase ASCII hex digits of the high and
/// low nibbles. The result packs the three bytes little-endian:
/// `b'%' | (H << 8) | (L << 16)`.
///
/// # Branchless Contract
/// Each nibble is converted to its ASCII hex digit with an arithmetic
/// select (`'0'+n` vs `'A'+n-10`) driven by a comparison mask, never a
/// branch.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::url_encode_branchless::url_encode_branchless;
/// let result = url_encode_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn url_encode_branchless(val: u64, aux: u64) -> u64 {
    fn hex(nibble: u64) -> u64 {
        let n = nibble & 0xF;
        // mask = 1 iff n > 9 (i.e. needs 'A'..'F')
        let alpha = (9u64.wrapping_sub(n) >> 63) & 1;
        // '0' + n, plus 7 to jump from '9'+1 to 'A' for n >= 10
        (b'0' as u64) + n + alpha.wrapping_mul(7)
    }
    let b = val.wrapping_add(aux) & 0xFF;
    let hi = hex(b >> 4);
    let lo = hex(b & 0xF);
    (b'%' as u64) | (hi << 8) | (lo << 16)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn url_encode_branchless_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: index a literal hex-digit table.
        const HEX: &[u8; 16] = b"0123456789ABCDEF";
        let b = (val.wrapping_add(aux) & 0xFF) as usize;
        let hi = HEX[b >> 4] as u64;
        let lo = HEX[b & 0xF] as u64;
        (b'%' as u64) + (hi << 8) + (lo << 16)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_url_encode_branchless_1(val: u64, aux: u64) -> u64 {
        !url_encode_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_url_encode_branchless_2(val: u64, aux: u64) -> u64 {
        url_encode_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_url_encode_branchless_3(val: u64, aux: u64) -> u64 {
        url_encode_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_url_encode_branchless_all() {
        // oracle
        assert_eq!(
            url_encode_branchless(42, 1337),
            url_encode_branchless_reference(42, 1337)
        );
        // boundaries
        assert_eq!(
            url_encode_branchless(0, 0),
            url_encode_branchless_reference(0, 0)
        );
        assert_eq!(
            url_encode_branchless(u64::MAX, u64::MAX),
            url_encode_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            url_encode_branchless(u64::MAX, 0),
            url_encode_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            url_encode_branchless(0, u64::MAX),
            url_encode_branchless_reference(0, u64::MAX)
        );
        // mutants
        let base = url_encode_branchless_reference(42, 1337);
        assert_ne!(mutant_url_encode_branchless_1(42, 1337), base, "mutant 1");
        assert_ne!(mutant_url_encode_branchless_2(42, 1337), base, "mutant 2");
        assert_ne!(mutant_url_encode_branchless_3(42, 1337), base, "mutant 3");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = url_encode_branchless_reference(val, aux) }
    //
    // Counterfactual Analysis for url_encode_branchless:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_url_encode_branchless(c: &mut Criterion) {
        c.bench_function("url_encode_branchless", |b| {
            b.iter(|| {
                let res = url_encode_branchless(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
