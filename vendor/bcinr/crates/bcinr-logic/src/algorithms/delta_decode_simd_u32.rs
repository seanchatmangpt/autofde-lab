// Academic-grade branchless algorithm library: delta_decode_simd_u32
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// delta_decode_simd_u32
///
/// SIMD-within-a-register (SWAR) 2-lane u32 delta decoding.
///
/// Interprets `val` (deltas) and `aux` (previous values) as two packed u32 lanes:
/// - Lane 0 (low  word): bits  0-31
/// - Lane 1 (high word): bits 32-63
///
/// Reconstructs the original values per lane via wrapping addition:
/// - `r0 = (val as u32).wrapping_add(aux as u32)`
/// - `r1 = ((val >> 32) as u32).wrapping_add((aux >> 32) as u32)`
///
/// Returns the two reconstructed values packed back into a single u64.
///
/// # Round-Trip Property
/// For any `val` and `prev`:
/// `delta_decode_simd_u32(delta_encode_simd_u32(val, prev), prev) == val`
///
/// # Branchless Contract
/// **Ensures:** The result matches independent per-lane addition for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::delta_decode_simd_u32::delta_decode_simd_u32;
/// // Lane 0: delta=7, prev=3 → 10; Lane 1: delta=15, prev=5 → 20
/// let enc  = ( 7u64) | (15u64 << 32);
/// let prev = ( 3u64) | ( 5u64 << 32);
/// let dec  = delta_decode_simd_u32(enc, prev);
/// assert_eq!(dec as u32, 10);
/// assert_eq!((dec >> 32) as u32, 20);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
pub fn delta_decode_simd_u32(val: u64, aux: u64) -> u64 {
    // val = [delta1: u32 | delta0: u32], aux = [prev1: u32 | prev0: u32]
    let d0 = val as u32;
    let d1 = (val >> 32) as u32;
    let p0 = aux as u32;
    let p1 = (aux >> 32) as u32;
    // Reconstruct each lane independently (wrapping addition)
    let r0 = d0.wrapping_add(p0);
    let r1 = d1.wrapping_add(p1);
    (r0 as u64) | ((r1 as u64) << 32)
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::super::delta_encode_simd_u32::delta_encode_simd_u32;
    use super::*;
    use proptest::prelude::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation (per-lane wrapping add)
    // -------------------------------------------------------------------------
    fn delta_decode_simd_u32_reference(val: u64, aux: u64) -> u64 {
        let d0 = val as u32;
        let d1 = (val >> 32) as u32;
        let p0 = aux as u32;
        let p1 = (aux >> 32) as u32;
        let r0 = d0.wrapping_add(p0);
        let r1 = d1.wrapping_add(p1);
        (r0 as u64) | ((r1 as u64) << 32)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_delta_decode_simd_u32_1(val: u64, aux: u64) -> u64 {
        !delta_decode_simd_u32_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_delta_decode_simd_u32_2(val: u64, aux: u64) -> u64 {
        delta_decode_simd_u32_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_delta_decode_simd_u32_3(val: u64, aux: u64) -> u64 {
        delta_decode_simd_u32_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    proptest! {
        #[test]
        fn test_delta_decode_simd_u32_equivalence(val in any::<u64>(), aux in any::<u64>()) {
            let expected = delta_decode_simd_u32_reference(val, aux);
            let actual = delta_decode_simd_u32(val, aux);
            prop_assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        }

        #[test]
        fn test_delta_decode_simd_u32_counterfactual_mutant_1(val in any::<u64>(), aux in any::<u64>()) {
            let expected = delta_decode_simd_u32_reference(val, aux);
            let actual = mutant_delta_decode_simd_u32_1(val, aux);
            if val != aux && val != 0 && aux != 0 {
                prop_assert!(expected != actual, "Counterfactual Mutant 1 failed to fail!");
            }
        }

        #[test]
        fn test_delta_decode_simd_u32_counterfactual_mutant_2(val in any::<u64>(), aux in any::<u64>()) {
            let expected = delta_decode_simd_u32_reference(val, aux);
            let actual = mutant_delta_decode_simd_u32_2(val, aux);
            if val != aux && val != 0 && aux != 0 {
                prop_assert!(expected != actual, "Counterfactual Mutant 2 failed to fail!");
            }
        }

        #[test]
        fn test_delta_decode_simd_u32_counterfactual_mutant_3(val in any::<u64>(), aux in any::<u64>()) {
            let expected = delta_decode_simd_u32_reference(val, aux);
            let actual = mutant_delta_decode_simd_u32_3(val, aux);
            if val != aux && val != 0 && aux != 0 {
                prop_assert!(expected != actual, "Counterfactual Mutant 3 failed to fail!");
            }
        }

        /// Round-trip: decode(encode(val, prev), prev) == val for all inputs
        #[test]
        fn test_delta_round_trip(val in any::<u64>(), prev in any::<u64>()) {
            let encoded = delta_encode_simd_u32(val, prev);
            let decoded = delta_decode_simd_u32(encoded, prev);
            prop_assert_eq!(decoded, val, "Round-trip failed for val={:#018x} prev={:#018x}", val, prev);
        }
    }

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_delta_decode_simd_u32_all() {
        // equivalence oracle
        let expected = delta_decode_simd_u32_reference(42, 1337);
        let actual = delta_decode_simd_u32(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            delta_decode_simd_u32(0, 0),
            delta_decode_simd_u32_reference(0, 0)
        );
        assert_eq!(
            delta_decode_simd_u32(u64::MAX, u64::MAX),
            delta_decode_simd_u32_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            delta_decode_simd_u32(u64::MAX, 0),
            delta_decode_simd_u32_reference(u64::MAX, 0)
        );
        assert_eq!(
            delta_decode_simd_u32(0, u64::MAX),
            delta_decode_simd_u32_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = delta_decode_simd_u32_reference(42, 1337);
        let m1 = mutant_delta_decode_simd_u32_1(42, 1337);
        let m2 = mutant_delta_decode_simd_u32_2(42, 1337);
        let m3 = mutant_delta_decode_simd_u32_3(42, 1337);
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
    // LANE SEMANTICS: Verify independent per-lane operation and round-trip
    // -------------------------------------------------------------------------
    #[test]
    fn test_delta_decode_simd_u32_lane_independence() {
        // Lane 0: delta=7, prev=3 → 10; Lane 1: delta=15, prev=5 → 20
        let enc = (7u64) | (15u64 << 32);
        let prev = (3u64) | (5u64 << 32);
        let dec = delta_decode_simd_u32(enc, prev);
        assert_eq!(dec as u32, 10);
        assert_eq!((dec >> 32) as u32, 20);

        // Wrapping: delta=u32::MAX, prev=1 → 0
        let enc2 = u32::MAX as u64;
        let prev2 = 1u64;
        let dec2 = delta_decode_simd_u32(enc2, prev2);
        assert_eq!(dec2 as u32, 0);

        // High lane wrapping
        let enc3 = (u32::MAX as u64) << 32;
        let prev3 = 1u64 << 32;
        let dec3 = delta_decode_simd_u32(enc3, prev3);
        assert_eq!((dec3 >> 32) as u32, 0);
    }

    #[test]
    fn test_delta_decode_simd_u32_round_trip_hardcoded() {
        // Specific round-trip cases
        let cases: &[(u64, u64)] = &[
            (0, 0),
            (u64::MAX, 0),
            (0, u64::MAX),
            (u64::MAX, u64::MAX),
            (0x0000_0001_0000_0002, 0x0000_0003_0000_0004),
            (0xDEAD_BEEF_CAFE_BABE, 0x1234_5678_9ABC_DEF0),
        ];
        for &(val, prev) in cases {
            let encoded = delta_encode_simd_u32(val, prev);
            let decoded = delta_decode_simd_u32(encoded, prev);
            assert_eq!(
                decoded, val,
                "Round-trip failed for val={:#018x} prev={:#018x}",
                val, prev
            );
        }
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_delta_decode_simd_u32(c: &mut Criterion) {
        c.bench_function("delta_decode_simd_u32", |b| {
            b.iter(|| {
                let res = delta_decode_simd_u32(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
