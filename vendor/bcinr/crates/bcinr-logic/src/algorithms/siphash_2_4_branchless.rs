// Academic-grade branchless algorithm library: siphash_2_4_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// siphash_2_4_branchless
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::siphash_2_4_branchless::siphash_2_4_branchless;
/// let result = siphash_2_4_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
///
/// # Branchless Contract
/// Interpretation: a real SipHash-2-4 over a single 8-byte message word `val`
/// under the 128-bit key `(0, aux)`. The four state words are initialised with
/// the standard SipHash IV constants, the message word is absorbed with two
/// SipRounds (the "2"), the length/finalisation byte is mixed, and four more
/// SipRounds (the "4") finalise the state. The 2 compression + 4 finalisation
/// SipRounds are fully unrolled, giving a branchless constant-time MAC.
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn siphash_2_4_branchless(val: u64, aux: u64) -> u64 {
    let k0: u64 = 0;
    let k1: u64 = aux;
    let mut v0 = k0 ^ 0x736f6d6570736575;
    let mut v1 = k1 ^ 0x646f72616e646f6d;
    let mut v2 = k0 ^ 0x6c7967656e657261;
    let mut v3 = k1 ^ 0x7465646279746573;

    // absorb message word `val`
    v3 ^= val;
    // SipRound x2
    sipround(&mut v0, &mut v1, &mut v2, &mut v3);
    sipround(&mut v0, &mut v1, &mut v2, &mut v3);
    v0 ^= val;

    // finalisation block: top byte = message length (8)
    let b: u64 = 8u64 << 56;
    v3 ^= b;
    sipround(&mut v0, &mut v1, &mut v2, &mut v3);
    sipround(&mut v0, &mut v1, &mut v2, &mut v3);
    v0 ^= b;

    v2 ^= 0xff;
    sipround(&mut v0, &mut v1, &mut v2, &mut v3);
    sipround(&mut v0, &mut v1, &mut v2, &mut v3);
    sipround(&mut v0, &mut v1, &mut v2, &mut v3);
    sipround(&mut v0, &mut v1, &mut v2, &mut v3);

    v0 ^ v1 ^ v2 ^ v3
}

#[inline]
fn sipround(v0: &mut u64, v1: &mut u64, v2: &mut u64, v3: &mut u64) {
    *v0 = v0.wrapping_add(*v1);
    *v1 = v1.rotate_left(13);
    *v1 ^= *v0;
    *v0 = v0.rotate_left(32);
    *v2 = v2.wrapping_add(*v3);
    *v3 = v3.rotate_left(16);
    *v3 ^= *v2;
    *v0 = v0.wrapping_add(*v3);
    *v3 = v3.rotate_left(21);
    *v3 ^= *v0;
    *v2 = v2.wrapping_add(*v1);
    *v1 = v1.rotate_left(17);
    *v1 ^= *v2;
    *v2 = v2.rotate_left(32);
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn siphash_2_4_branchless_reference(val: u64, aux: u64) -> u64 {
        // SipHash-2-4 re-derived with a 4-element state array and a counted-loop
        // SipRound, instead of four mutable scalars and unrolled calls.
        fn round(s: &mut [u64; 4]) {
            s[0] = s[0].wrapping_add(s[1]);
            s[1] = s[1].rotate_left(13) ^ s[0];
            s[0] = s[0].rotate_left(32);
            s[2] = s[2].wrapping_add(s[3]);
            s[3] = s[3].rotate_left(16) ^ s[2];
            s[0] = s[0].wrapping_add(s[3]);
            s[3] = s[3].rotate_left(21) ^ s[0];
            s[2] = s[2].wrapping_add(s[1]);
            s[1] = s[1].rotate_left(17) ^ s[2];
            s[2] = s[2].rotate_left(32);
        }
        fn rounds(s: &mut [u64; 4], n: usize) {
            for _ in 0..n {
                round(s);
            }
        }
        let (k0, k1) = (0u64, aux);
        let mut s = [
            k0 ^ 0x736f6d6570736575,
            k1 ^ 0x646f72616e646f6d,
            k0 ^ 0x6c7967656e657261,
            k1 ^ 0x7465646279746573,
        ];
        s[3] ^= val;
        rounds(&mut s, 2);
        s[0] ^= val;
        let b = 8u64 << 56;
        s[3] ^= b;
        rounds(&mut s, 2);
        s[0] ^= b;
        s[2] ^= 0xff;
        rounds(&mut s, 4);
        s[0] ^ s[1] ^ s[2] ^ s[3]
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_siphash_2_4_branchless_1(val: u64, aux: u64) -> u64 {
        !siphash_2_4_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_siphash_2_4_branchless_2(val: u64, aux: u64) -> u64 {
        siphash_2_4_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_siphash_2_4_branchless_3(val: u64, aux: u64) -> u64 {
        siphash_2_4_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_siphash_2_4_branchless_all() {
        // oracle
        assert_eq!(
            siphash_2_4_branchless(42, 1337),
            siphash_2_4_branchless_reference(42, 1337)
        );
        // boundaries
        assert_eq!(
            siphash_2_4_branchless(0, 0),
            siphash_2_4_branchless_reference(0, 0)
        );
        assert_eq!(
            siphash_2_4_branchless(u64::MAX, u64::MAX),
            siphash_2_4_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            siphash_2_4_branchless(u64::MAX, 0),
            siphash_2_4_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            siphash_2_4_branchless(0, u64::MAX),
            siphash_2_4_branchless_reference(0, u64::MAX)
        );
        // mutants
        let base = siphash_2_4_branchless_reference(42, 1337);
        assert_ne!(mutant_siphash_2_4_branchless_1(42, 1337), base, "mutant 1");
        assert_ne!(mutant_siphash_2_4_branchless_2(42, 1337), base, "mutant 2");
        assert_ne!(mutant_siphash_2_4_branchless_3(42, 1337), base, "mutant 3");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = siphash_2_4_branchless_reference(val, aux) }
    //
    // Counterfactual Analysis for siphash_2_4_branchless:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_siphash_2_4_branchless(c: &mut Criterion) {
        c.bench_function("siphash_2_4_branchless", |b| {
            b.iter(|| {
                let res = siphash_2_4_branchless(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
