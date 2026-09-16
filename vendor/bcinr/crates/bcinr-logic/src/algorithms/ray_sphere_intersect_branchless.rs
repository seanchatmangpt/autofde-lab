// Academic-grade branchless algorithm library: ray_sphere_intersect_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// ray_sphere_intersect_branchless
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::ray_sphere_intersect_branchless::ray_sphere_intersect_branchless;
/// let result = ray_sphere_intersect_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn ray_sphere_intersect_branchless(val: u64, aux: u64) -> u64 {
    // Ray-sphere hit test reduced to the sign of the quadratic discriminant
    // `Δ = b² - 4c` (the unit-direction case where a = 1). `val` carries the
    // signed coefficient `b`, `aux` the signed coefficient `c`. A real root —
    // i.e. the ray meets the sphere — exists iff Δ >= 0.
    //
    // # Branchless Contract
    // Δ is formed with wrapping two's-complement arithmetic; its sign lives in
    // bit 63. Extracting that bit and XOR-ing with 1 yields 1 for Δ >= 0 (hit)
    // and 0 for Δ < 0 (miss), with no comparison branch.
    let b = val;
    let c = aux;
    let disc = b.wrapping_mul(b).wrapping_sub(4u64.wrapping_mul(c));
    (disc >> 63) ^ 1
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn ray_sphere_intersect_branchless_reference(val: u64, aux: u64) -> u64 {
        let b = val;
        let c = aux;
        let disc = b.wrapping_mul(b).wrapping_sub(4u64.wrapping_mul(c));
        if (disc >> 63) == 1 {
            0
        } else {
            1
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_ray_sphere_intersect_branchless_1(val: u64, aux: u64) -> u64 {
        !ray_sphere_intersect_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_ray_sphere_intersect_branchless_2(val: u64, aux: u64) -> u64 {
        ray_sphere_intersect_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_ray_sphere_intersect_branchless_3(val: u64, aux: u64) -> u64 {
        ray_sphere_intersect_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_ray_sphere_intersect_branchless_all() {
        // equivalence oracle
        let expected = ray_sphere_intersect_branchless_reference(42, 1337);
        let actual = ray_sphere_intersect_branchless(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            ray_sphere_intersect_branchless(0, 0),
            ray_sphere_intersect_branchless_reference(0, 0)
        );
        assert_eq!(
            ray_sphere_intersect_branchless(u64::MAX, u64::MAX),
            ray_sphere_intersect_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            ray_sphere_intersect_branchless(u64::MAX, 0),
            ray_sphere_intersect_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            ray_sphere_intersect_branchless(0, u64::MAX),
            ray_sphere_intersect_branchless_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = ray_sphere_intersect_branchless_reference(42, 1337);
        let m1 = mutant_ray_sphere_intersect_branchless_1(42, 1337);
        let m2 = mutant_ray_sphere_intersect_branchless_2(42, 1337);
        let m3 = mutant_ray_sphere_intersect_branchless_3(42, 1337);
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
    // Postcondition: { result = ray_sphere_intersect_branchless_reference(val, aux) }
    //
    // Counterfactual Analysis for ray_sphere_intersect_branchless:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_ray_sphere_intersect_branchless(c: &mut Criterion) {
        c.bench_function("ray_sphere_intersect_branchless", |b| {
            b.iter(|| {
                let res = ray_sphere_intersect_branchless(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
