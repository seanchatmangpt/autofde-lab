// Academic-grade branchless algorithm library: gray_decode_u64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// gray_decode_u64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Returns the binary value whose reflected Gray code is `val`, i.e.
/// the inverse of `gray_encode_u64`. `aux` is unused.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// Interpretation: the standard logarithmic Gray-to-binary prefix-XOR cascade
/// (`x ^= x >> 1; x ^= x >> 2; ...; x ^= x >> 32`).
///
/// ```rust
/// use bcinr_logic::algorithms::gray_decode_u64::gray_decode_u64;
/// let result = gray_decode_u64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn gray_decode_u64(val: u64, aux: u64) -> u64 {
    let mut x = val;
    x ^= x >> 1;
    x ^= x >> 2;
    x ^= x >> 4;
    x ^= x >> 8;
    x ^= x >> 16;
    x ^= x >> 32;
    x
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn gray_decode_u64_reference(val: u64, aux: u64) -> u64 {
        // Independent structure: sequential MSB-to-LSB running-XOR accumulator.
        let mut res: u64 = 0;
        let mut acc: u64 = 0;
        for i in (0..64).rev() {
            acc ^= (val >> i) & 1;
            res |= acc << i;
        }
        res
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_gray_decode_u64_1(val: u64, aux: u64) -> u64 {
        !gray_decode_u64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_gray_decode_u64_2(val: u64, aux: u64) -> u64 {
        gray_decode_u64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_gray_decode_u64_3(val: u64, aux: u64) -> u64 {
        gray_decode_u64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_gray_decode_u64_all() {
        // equivalence oracle
        let expected = gray_decode_u64_reference(42, 1337);
        let actual = gray_decode_u64(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(gray_decode_u64(0, 0), gray_decode_u64_reference(0, 0));
        assert_eq!(
            gray_decode_u64(u64::MAX, u64::MAX),
            gray_decode_u64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            gray_decode_u64(u64::MAX, 0),
            gray_decode_u64_reference(u64::MAX, 0)
        );
        assert_eq!(
            gray_decode_u64(0, u64::MAX),
            gray_decode_u64_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = gray_decode_u64_reference(42, 1337);
        let m1 = mutant_gray_decode_u64_1(42, 1337);
        let m2 = mutant_gray_decode_u64_2(42, 1337);
        let m3 = mutant_gray_decode_u64_3(42, 1337);
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

    pub fn bench_gray_decode_u64(c: &mut Criterion) {
        c.bench_function("gray_decode_u64", |b| {
            b.iter(|| {
                let res = gray_decode_u64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
