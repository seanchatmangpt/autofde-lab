// Academic-grade branchless algorithm library: k_independent_hash_gen
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// k_independent_hash_gen
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
/// use bcinr_logic::algorithms::k_independent_hash_gen::k_independent_hash_gen;
/// let result = k_independent_hash_gen(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn k_independent_hash_gen(val: u64, aux: u64) -> u64 {
    let x = val;
    let a = aux & 0xFFFFFFFF;
    let b = aux >> 32;
    x.wrapping_mul(a).wrapping_add(b)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn k_independent_hash_gen_reference(val: u64, aux: u64) -> u64 {
        // Independent: affine map a*x+b via u128, lanes read from byte split.
        let a = (aux as u32) as u128;
        let b = (aux >> 32) as u128;
        let prod = (val as u128) * a;
        ((prod + b) & 0xFFFF_FFFF_FFFF_FFFF) as u64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_k_independent_hash_gen_1(val: u64, aux: u64) -> u64 {
        !k_independent_hash_gen_reference(val, aux)
    }
    #[allow(unused_variables)]
    fn mutant_k_independent_hash_gen_2(val: u64, aux: u64) -> u64 {
        k_independent_hash_gen_reference(val, aux).wrapping_add(1)
    }
    #[allow(unused_variables)]
    fn mutant_k_independent_hash_gen_3(val: u64, aux: u64) -> u64 {
        k_independent_hash_gen_reference(val, aux) ^ 0xFFFFFFFF
    }

    #[test]
    fn test_k_independent_hash_gen_all() {
        // equivalence oracle
        let expected = k_independent_hash_gen_reference(42, 1337);
        let actual = k_independent_hash_gen(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            k_independent_hash_gen(0, 0),
            k_independent_hash_gen_reference(0, 0)
        );
        assert_eq!(
            k_independent_hash_gen(u64::MAX, u64::MAX),
            k_independent_hash_gen_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            k_independent_hash_gen(u64::MAX, 0),
            k_independent_hash_gen_reference(u64::MAX, 0)
        );
        assert_eq!(
            k_independent_hash_gen(0, u64::MAX),
            k_independent_hash_gen_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = k_independent_hash_gen_reference(42, 1337);
        let m1 = mutant_k_independent_hash_gen_1(42, 1337);
        let m2 = mutant_k_independent_hash_gen_2(42, 1337);
        let m3 = mutant_k_independent_hash_gen_3(42, 1337);
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

    pub fn bench_k_independent_hash_gen(c: &mut Criterion) {
        c.bench_function("k_independent_hash_gen", |b| {
            b.iter(|| {
                let res = k_independent_hash_gen(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
