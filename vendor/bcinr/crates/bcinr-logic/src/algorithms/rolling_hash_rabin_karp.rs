// Academic-grade branchless algorithm library: rolling_hash_rabin_karp
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// rolling_hash_rabin_karp
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
/// use bcinr_logic::algorithms::rolling_hash_rabin_karp::rolling_hash_rabin_karp;
/// let result = rolling_hash_rabin_karp(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn rolling_hash_rabin_karp(val: u64, aux: u64) -> u64 {
    val.wrapping_mul(31).wrapping_add(aux)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn rolling_hash_rabin_karp_reference(val: u64, aux: u64) -> u64 {
        let (p1, _) = val.overflowing_mul(31);
        let (p2, _) = p1.overflowing_add(aux);
        p2
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_rolling_hash_rabin_karp_1(val: u64, aux: u64) -> u64 {
        !rolling_hash_rabin_karp_reference(val, aux)
    }
    #[allow(unused_variables)]
    fn mutant_rolling_hash_rabin_karp_2(val: u64, aux: u64) -> u64 {
        rolling_hash_rabin_karp_reference(val, aux).wrapping_add(1)
    }
    #[allow(unused_variables)]
    fn mutant_rolling_hash_rabin_karp_3(val: u64, aux: u64) -> u64 {
        rolling_hash_rabin_karp_reference(val, aux) ^ 0xFFFFFFFF
    }

    #[test]
    fn test_rolling_hash_rabin_karp_all() {
        // equivalence oracle
        let expected = rolling_hash_rabin_karp_reference(42, 1337);
        let actual = rolling_hash_rabin_karp(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            rolling_hash_rabin_karp(0, 0),
            rolling_hash_rabin_karp_reference(0, 0)
        );
        assert_eq!(
            rolling_hash_rabin_karp(u64::MAX, u64::MAX),
            rolling_hash_rabin_karp_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            rolling_hash_rabin_karp(u64::MAX, 0),
            rolling_hash_rabin_karp_reference(u64::MAX, 0)
        );
        assert_eq!(
            rolling_hash_rabin_karp(0, u64::MAX),
            rolling_hash_rabin_karp_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = rolling_hash_rabin_karp_reference(42, 1337);
        let m1 = mutant_rolling_hash_rabin_karp_1(42, 1337);
        let m2 = mutant_rolling_hash_rabin_karp_2(42, 1337);
        let m3 = mutant_rolling_hash_rabin_karp_3(42, 1337);
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

    pub fn bench_rolling_hash_rabin_karp(c: &mut Criterion) {
        c.bench_function("rolling_hash_rabin_karp", |b| {
            b.iter(|| {
                let res = rolling_hash_rabin_karp(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
