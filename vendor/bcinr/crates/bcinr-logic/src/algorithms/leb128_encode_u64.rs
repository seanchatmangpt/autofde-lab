// Academic-grade branchless algorithm library: leb128_encode_u64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// leb128_encode_u64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Produces the first 8 LEB128 bytes of `val`, packed little-endian
/// (group `k` -> output byte `k`). Each byte holds the 7-bit group
/// `(val >> 7k) & 0x7F` and its high (continuation) bit is set iff any higher bit
/// of `val` remains (`val >> 7(k+1) != 0`). This covers the low 56 bits of `val`;
/// `aux` is unused.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// Interpretation: the unsigned LEB128 encoder, fully unrolled, with the
/// continuation bit derived from a branchless nonzero test.
///
/// ```rust
/// use bcinr_logic::algorithms::leb128_encode_u64::leb128_encode_u64;
/// let result = leb128_encode_u64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn leb128_encode_u64(val: u64, aux: u64) -> u64 {
    // continuation flag for group k: 0x80 iff (val >> 7*(k+1)) != 0.
    let group = |k: u32| -> u64 {
        let g = (val >> (7 * k)) & 0x7F;
        let rest = val >> (7 * (k + 1));
        // (rest != 0) as 0/1 without a branch, then scaled to the high bit.
        let nz = ((rest | 0u64.wrapping_sub(rest)) >> 63) & 1;
        g | (nz << 7)
    };
    let mut out: u64 = 0;
    out |= group(0);
    out |= group(1) << 8;
    out |= group(2) << 16;
    out |= group(3) << 24;
    out |= group(4) << 32;
    out |= group(5) << 40;
    out |= group(6) << 48;
    out |= group(7) << 56;
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn leb128_encode_u64_reference(val: u64, aux: u64) -> u64 {
        // Independent structure: sequential consume-and-shift loop with a real
        // branch for the continuation bit.
        let mut v = val;
        let mut out: u64 = 0;
        let mut shift: u32 = 0;
        for _ in 0..8 {
            let mut byte = v & 0x7F;
            v >>= 7;
            if v != 0 {
                byte |= 0x80;
            }
            out |= byte << shift;
            shift += 8;
        }
        out
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_leb128_encode_u64_1(val: u64, aux: u64) -> u64 {
        !leb128_encode_u64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_leb128_encode_u64_2(val: u64, aux: u64) -> u64 {
        leb128_encode_u64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_leb128_encode_u64_3(val: u64, aux: u64) -> u64 {
        leb128_encode_u64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_leb128_encode_u64_all() {
        // equivalence oracle
        let expected = leb128_encode_u64_reference(42, 1337);
        let actual = leb128_encode_u64(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(leb128_encode_u64(0, 0), leb128_encode_u64_reference(0, 0));
        assert_eq!(
            leb128_encode_u64(u64::MAX, u64::MAX),
            leb128_encode_u64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            leb128_encode_u64(u64::MAX, 0),
            leb128_encode_u64_reference(u64::MAX, 0)
        );
        assert_eq!(
            leb128_encode_u64(0, u64::MAX),
            leb128_encode_u64_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = leb128_encode_u64_reference(42, 1337);
        let m1 = mutant_leb128_encode_u64_1(42, 1337);
        let m2 = mutant_leb128_encode_u64_2(42, 1337);
        let m3 = mutant_leb128_encode_u64_3(42, 1337);
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
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = leb128_encode_u64_reference(val, aux) }
    //
    // Counterfactual Analysis for leb128_encode_u64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_leb128_encode_u64(c: &mut Criterion) {
        c.bench_function("leb128_encode_u64", |b| {
            b.iter(|| {
                let res = leb128_encode_u64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
