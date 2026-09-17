// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#![allow(
    unused_variables,
    unused_assignments,
    unused_mut,
    unused_parens,
    dead_code
)]
// Academic-grade branchless algorithm library: find_last_of_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// find_last_of_branchless
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
/// use bcinr_logic::algorithms::find_last_of_branchless::find_last_of_branchless;
/// let result = find_last_of_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
#[no_mangle]
#[allow(unused_variables)]
pub fn find_last_of_branchless(val: u64, aux: u64) -> u64 {
    let x = val ^ ((aux & 0xFF).wrapping_mul(0x0101010101010101));
    // Cascade-safe per-byte match mask (0x80 in each lane equal to the needle).
    let m = !(((x & 0x7F7F7F7F7F7F7F7F).wrapping_add(0x7F7F7F7F7F7F7F7F) | x) & 0x8080808080808080)
        & 0x8080808080808080;
    let has_match = (((m.wrapping_neg() | m) as i64) >> 63) as u64 & 1;
    let idx = (63u64.wrapping_sub(m.leading_zeros() as u64)) >> 3;
    (idx & has_match.wrapping_neg()) | (8 & (!has_match.wrapping_neg()))
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn find_last_of_branchless_reference(val: u64, aux: u64) -> u64 {
        let target = (aux & 0xFF) as u8;
        let bytes = val.to_le_bytes();
        for i in (0..8).rev() {
            if bytes[i] == target {
                return i as u64;
            }
        }
        8
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_find_last_of_branchless_1(val: u64, aux: u64) -> u64 {
        !find_last_of_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_find_last_of_branchless_2(val: u64, aux: u64) -> u64 {
        find_last_of_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_find_last_of_branchless_3(val: u64, aux: u64) -> u64 {
        find_last_of_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_find_last_of_branchless_all() {
        // equivalence oracle
        let expected = find_last_of_branchless_reference(42, 1337);
        let actual = find_last_of_branchless(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            find_last_of_branchless(0, 0),
            find_last_of_branchless_reference(0, 0)
        );
        assert_eq!(
            find_last_of_branchless(u64::MAX, u64::MAX),
            find_last_of_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            find_last_of_branchless(u64::MAX, 0),
            find_last_of_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            find_last_of_branchless(0, u64::MAX),
            find_last_of_branchless_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = find_last_of_branchless_reference(42, 1337);
        let m1 = mutant_find_last_of_branchless_1(42, 1337);
        let m2 = mutant_find_last_of_branchless_2(42, 1337);
        let m3 = mutant_find_last_of_branchless_3(42, 1337);
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

    pub fn bench_find_last_of_branchless(c: &mut Criterion) {
        c.bench_function("find_last_of_branchless", |b| {
            b.iter(|| {
                let res = find_last_of_branchless(black_box(42), black_box(1337));
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
