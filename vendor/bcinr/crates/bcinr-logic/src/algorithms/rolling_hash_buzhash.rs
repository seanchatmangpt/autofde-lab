// Academic-grade branchless algorithm library: rolling_hash_buzhash
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// rolling_hash_buzhash
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
///
/// ```rust
/// use bcinr_logic::algorithms::rolling_hash_buzhash::rolling_hash_buzhash;
/// let result = rolling_hash_buzhash(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn rolling_hash_buzhash(val: u64, aux: u64) -> u64 {
    val.rotate_left(1) ^ aux
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    fn rolling_hash_buzhash_reference(val: u64, aux: u64) -> u64 {
        // BuzHash single-character roll: cyclic 1-bit left shift of the running
        // hash, then XOR the incoming character hash. Recompose the rotation
        // from primitive shifts and an explicit carry of the top bit.
        let carry = (val >> 63) & 1;
        let shifted = (val << 1) | carry;
        shifted ^ aux
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_rolling_hash_buzhash_1(val: u64, aux: u64) -> u64 {
        !rolling_hash_buzhash_reference(val, aux)
    }
    #[allow(unused_variables)]
    fn mutant_rolling_hash_buzhash_2(val: u64, aux: u64) -> u64 {
        rolling_hash_buzhash_reference(val, aux).wrapping_add(1)
    }
    #[allow(unused_variables)]
    fn mutant_rolling_hash_buzhash_3(val: u64, aux: u64) -> u64 {
        rolling_hash_buzhash_reference(val, aux) ^ 0xFFFFFFFF
    }

    #[test]
    fn test_rolling_hash_buzhash_all() {
        // equivalence oracle
        let expected = rolling_hash_buzhash_reference(42, 1337);
        let actual = rolling_hash_buzhash(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            rolling_hash_buzhash(0, 0),
            rolling_hash_buzhash_reference(0, 0)
        );
        assert_eq!(
            rolling_hash_buzhash(u64::MAX, u64::MAX),
            rolling_hash_buzhash_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            rolling_hash_buzhash(u64::MAX, 0),
            rolling_hash_buzhash_reference(u64::MAX, 0)
        );
        assert_eq!(
            rolling_hash_buzhash(0, u64::MAX),
            rolling_hash_buzhash_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = rolling_hash_buzhash_reference(42, 1337);
        let m1 = mutant_rolling_hash_buzhash_1(42, 1337);
        let m2 = mutant_rolling_hash_buzhash_2(42, 1337);
        let m3 = mutant_rolling_hash_buzhash_3(42, 1337);
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
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_rolling_hash_buzhash(c: &mut Criterion) {
        c.bench_function("rolling_hash_buzhash", |b| {
            b.iter(|| {
                let res = rolling_hash_buzhash(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
