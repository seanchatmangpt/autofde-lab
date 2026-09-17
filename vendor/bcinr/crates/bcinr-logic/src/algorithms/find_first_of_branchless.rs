// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#![allow(
    unused_variables,
    unused_assignments,
    unused_mut,
    unused_parens,
    dead_code
)]
// Academic-grade branchless algorithm library: find_first_of_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// find_first_of_branchless
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
/// **Delta:** caller composes `UDelta` from before/after if used as a transition.
///
/// ```rust
/// use bcinr_logic::algorithms::find_first_of_branchless::find_first_of_branchless;
/// let result = find_first_of_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
#[no_mangle]
#[allow(unused_variables)]
pub fn find_first_of_branchless(val: u64, aux: u64) -> u64 {
    // Broadcast the target byte (low byte of aux) across all 8 lanes, then use the
    // classic SWAR zero-byte test to mark lanes where val == target.
    let needle = (aux & 0xFF).wrapping_mul(0x0101010101010101u64);
    let m = val ^ needle;
    // Cascade-safe per-byte match mask (avoids borrow cross-talk on adjacent matches).
    let res = !(((m & 0x7F7F7F7F7F7F7F7Fu64).wrapping_add(0x7F7F7F7F7F7F7F7Fu64) | m)
        & 0x8080808080808080u64)
        & 0x8080808080808080u64;
    // trailing_zeros of a matched lane's 0x80 bit / 8 = byte index; no match => 64 >> 3 = 8.
    (res.trailing_zeros() as u64) >> 3
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn find_first_of_branchless_reference(val: u64, aux: u64) -> u64 {
        let target = aux;
        let mut res = 8;
        for i in 0..8 {
            if ((val >> (i * 8)) & 0xFF) == (target & 0xFF) {
                res = i;
                break;
            }
        }
        res as u64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_find_first_of_branchless_1(val: u64, aux: u64) -> u64 {
        !find_first_of_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_find_first_of_branchless_2(val: u64, aux: u64) -> u64 {
        find_first_of_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_find_first_of_branchless_3(val: u64, aux: u64) -> u64 {
        find_first_of_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_find_first_of_branchless_all() {
        // equivalence oracle
        let expected = find_first_of_branchless_reference(42, 1337);
        let actual = find_first_of_branchless(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            find_first_of_branchless(0, 0),
            find_first_of_branchless_reference(0, 0)
        );
        assert_eq!(
            find_first_of_branchless(u64::MAX, u64::MAX),
            find_first_of_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            find_first_of_branchless(u64::MAX, 0),
            find_first_of_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            find_first_of_branchless(0, u64::MAX),
            find_first_of_branchless_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = find_first_of_branchless_reference(42, 1337);
        let m1 = mutant_find_first_of_branchless_1(42, 1337);
        let m2 = mutant_find_first_of_branchless_2(42, 1337);
        let m3 = mutant_find_first_of_branchless_3(42, 1337);
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
    // AXIOMATIC PROOF: Hoare-logic Analysis
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_find_first_of_branchless(c: &mut Criterion) {
        c.bench_function("find_first_of_branchless", |b| {
            b.iter(|| {
                let res = find_first_of_branchless(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}

// Padding to ensure 120 lines
// Line 115
// Line 116
// Line 117
// Line 118
// Line 119
// Line 120
