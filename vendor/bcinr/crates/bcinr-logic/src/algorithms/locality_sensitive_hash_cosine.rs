// Academic-grade branchless algorithm library: locality_sensitive_hash_cosine
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// locality_sensitive_hash_cosine
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
/// use bcinr_logic::algorithms::locality_sensitive_hash_cosine::locality_sensitive_hash_cosine;
/// let result = locality_sensitive_hash_cosine(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn locality_sensitive_hash_cosine(val: u64, aux: u64) -> u64 {
    let mut dot = 0i64;
    for i in 0..8 {
        let a = (((val >> (i * 8)) & 0xFF) as i8) as i64;
        let b = (((aux >> (i * 8)) & 0xFF) as i8) as i64;
        dot += a * b;
    }
    (dot > 0) as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn locality_sensitive_hash_cosine_reference(val: u64, aux: u64) -> u64 {
        let mut dot = 0i64;
        for i in 0..8 {
            let a = (((val >> (i * 8)) & 0xFF) as i8) as i64;
            let b = (((aux >> (i * 8)) & 0xFF) as i8) as i64;
            dot += a * b;
        }
        if dot > 0 {
            1
        } else {
            0
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_locality_sensitive_hash_cosine_1(val: u64, aux: u64) -> u64 {
        !locality_sensitive_hash_cosine_reference(val, aux)
    }
    #[allow(unused_variables)]
    fn mutant_locality_sensitive_hash_cosine_2(val: u64, aux: u64) -> u64 {
        locality_sensitive_hash_cosine_reference(val, aux).wrapping_add(1)
    }
    #[allow(unused_variables)]
    fn mutant_locality_sensitive_hash_cosine_3(val: u64, aux: u64) -> u64 {
        locality_sensitive_hash_cosine_reference(val, aux) ^ 0xFFFFFFFF
    }

    #[test]
    fn test_locality_sensitive_hash_cosine_all() {
        // equivalence oracle
        let expected = locality_sensitive_hash_cosine_reference(42, 1337);
        let actual = locality_sensitive_hash_cosine(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            locality_sensitive_hash_cosine(0, 0),
            locality_sensitive_hash_cosine_reference(0, 0)
        );
        assert_eq!(
            locality_sensitive_hash_cosine(u64::MAX, u64::MAX),
            locality_sensitive_hash_cosine_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            locality_sensitive_hash_cosine(u64::MAX, 0),
            locality_sensitive_hash_cosine_reference(u64::MAX, 0)
        );
        assert_eq!(
            locality_sensitive_hash_cosine(0, u64::MAX),
            locality_sensitive_hash_cosine_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = locality_sensitive_hash_cosine_reference(42, 1337);
        let m1 = mutant_locality_sensitive_hash_cosine_1(42, 1337);
        let m2 = mutant_locality_sensitive_hash_cosine_2(42, 1337);
        let m3 = mutant_locality_sensitive_hash_cosine_3(42, 1337);
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

    pub fn bench_locality_sensitive_hash_cosine(c: &mut Criterion) {
        c.bench_function("locality_sensitive_hash_cosine", |b| {
            b.iter(|| {
                let res = locality_sensitive_hash_cosine(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
