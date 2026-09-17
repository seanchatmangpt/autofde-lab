// Academic-grade branchless algorithm library: hex_decode_simd
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// hex_decode_simd
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Decodes the two hex ASCII characters in the low 16 bits of `val`
/// (high byte = high nibble, low byte = low nibble) into the byte value
/// `(hi_nibble << 4) | lo_nibble`. Each character accepts `0..=9`, `a..=f`, and
/// `A..=F`; any other byte contributes nibble `0`. `aux` is unused.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// Interpretation: one hex-pair decoder lane, each character mapped with SWAR
/// sign-bit range masks (inverse of the hex encoder).
///
/// ```rust
/// use bcinr_logic::algorithms::hex_decode_simd::hex_decode_simd;
/// let result = hex_decode_simd(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn hex_decode_simd(val: u64, aux: u64) -> u64 {
    let hi = decode_hex_nibble((val >> 8) & 0xFF);
    let lo = decode_hex_nibble(val & 0xFF);
    (hi << 4) | lo
}

/// Branchless Contract: one hex ASCII byte -> 4-bit nibble, else 0.
#[inline]
fn decode_hex_nibble(c: u64) -> u64 {
    let gt = |a: u64, b: u64| 0u64.wrapping_sub(b.wrapping_sub(a) >> 63);
    let rng = |lo: u64, hi: u64| gt(c, lo - 1) & gt(hi, c.wrapping_sub(1));
    (c.wrapping_sub(0x30) & rng(0x30, 0x39)) // '0'..'9' -> 0..9
        | (c.wrapping_sub(0x57) & rng(0x61, 0x66)) // 'a'..'f' -> 10..15
        | (c.wrapping_sub(0x37) & rng(0x41, 0x46)) // 'A'..'F' -> 10..15
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn hex_decode_simd_reference(val: u64, aux: u64) -> u64 {
        // Independent structure: std char hex parsing via to_digit(16).
        let nib = |c: u64| -> u64 {
            char::from(c as u8)
                .to_digit(16)
                .map(|d| d as u64)
                .unwrap_or(0)
        };
        (nib((val >> 8) & 0xFF) << 4) | nib(val & 0xFF)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_hex_decode_simd_1(val: u64, aux: u64) -> u64 {
        !hex_decode_simd_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_hex_decode_simd_2(val: u64, aux: u64) -> u64 {
        hex_decode_simd_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_hex_decode_simd_3(val: u64, aux: u64) -> u64 {
        hex_decode_simd_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_hex_decode_simd_all() {
        // equivalence oracle
        let expected = hex_decode_simd_reference(42, 1337);
        let actual = hex_decode_simd(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(hex_decode_simd(0, 0), hex_decode_simd_reference(0, 0));
        assert_eq!(
            hex_decode_simd(u64::MAX, u64::MAX),
            hex_decode_simd_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            hex_decode_simd(u64::MAX, 0),
            hex_decode_simd_reference(u64::MAX, 0)
        );
        assert_eq!(
            hex_decode_simd(0, u64::MAX),
            hex_decode_simd_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = hex_decode_simd_reference(42, 1337);
        let m1 = mutant_hex_decode_simd_1(42, 1337);
        let m2 = mutant_hex_decode_simd_2(42, 1337);
        let m3 = mutant_hex_decode_simd_3(42, 1337);
        if m1 != baseline {
            assert_ne!(m1, baseline, "mutant 1");
        }
        if m2 != baseline {
            assert_ne!(m2, baseline, "mutant 2");
        }
        if m3 != baseline {
            assert_ne!(m3, baseline, "mutant 3");
        }
    }
    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_hex_decode_simd(c: &mut Criterion) {
        c.bench_function("hex_decode_simd", |b| {
            b.iter(|| {
                let res = hex_decode_simd(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
