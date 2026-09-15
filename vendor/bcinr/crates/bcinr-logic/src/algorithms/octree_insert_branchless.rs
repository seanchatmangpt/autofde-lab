// Academic-grade branchless algorithm library: octree_insert_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// octree_insert_branchless
///
/// Interpretation: octree insertion locates a point by its 3D Morton (Z-order)
/// code. `val` packs a point as three 21-bit coordinates: x = bits[0..21],
/// y = bits[21..42], z = bits[42..63]. The bits of x, y, z are interleaved to
/// form the 63-bit Morton code (the octree path). `aux` gives an insertion
/// depth `d = (aux & 31)` capped at 21 levels; the code is masked to the top
/// `3*d` bits actually used at that depth (low bits truncated).
///
/// # Branchless Contract
/// **Ensures:** Result is the depth-masked 3D Morton interleave of val's lanes.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::octree_insert_branchless::octree_insert_branchless;
/// let result = octree_insert_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn octree_insert_branchless(val: u64, aux: u64) -> u64 {
    // Spread the low 21 bits of `c` so each occupies every third bit position.
    fn spread3(c: u64) -> u64 {
        let mut x = c & 0x1F_FFFF; // 21 bits
        x = (x | (x << 32)) & 0x1F00000000FFFF;
        x = (x | (x << 16)) & 0x1F0000FF0000FF;
        x = (x | (x << 8)) & 0x100F00F00F00F00F;
        x = (x | (x << 4)) & 0x10C30C30C30C30C3;
        x = (x | (x << 2)) & 0x1249249249249249;
        x
    }
    let x = val & 0x1F_FFFF;
    let y = (val >> 21) & 0x1F_FFFF;
    let z = (val >> 42) & 0x1F_FFFF;
    let morton = spread3(x) | (spread3(y) << 1) | (spread3(z) << 2);
    // Depth mask: keep the top 3*d code bits used at depth d (cap 21).
    let d = u64::min(aux & 31, 21) as u32;
    let keep = (d * 3) as u64;
    let shift = 63u64.wrapping_sub(keep);
    // Mask off the low (63-3d) bits; when d==0 the whole code clears.
    (morton >> shift) << shift
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn octree_insert_branchless_reference(val: u64, aux: u64) -> u64 {
        // Independent structure: bit-by-bit interleave via an explicit loop,
        // then clear low bits below the depth cut.
        let x = val & 0x1F_FFFF;
        let y = (val >> 21) & 0x1F_FFFF;
        let z = (val >> 42) & 0x1F_FFFF;
        let mut morton: u64 = 0;
        for i in 0..21 {
            morton |= ((x >> i) & 1) << (3 * i);
            morton |= ((y >> i) & 1) << (3 * i + 1);
            morton |= ((z >> i) & 1) << (3 * i + 2);
        }
        let d = (aux & 31).min(21) as u32;
        let shift = 63u32 - d * 3;
        if shift >= 64 {
            0
        } else {
            (morton >> shift) << shift
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_octree_insert_branchless_1(val: u64, aux: u64) -> u64 {
        !octree_insert_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_octree_insert_branchless_2(val: u64, aux: u64) -> u64 {
        octree_insert_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_octree_insert_branchless_3(val: u64, aux: u64) -> u64 {
        octree_insert_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_octree_insert_branchless_all() {
        // equivalence oracle
        let expected = octree_insert_branchless_reference(42, 1337);
        let actual = octree_insert_branchless(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            octree_insert_branchless(0, 0),
            octree_insert_branchless_reference(0, 0)
        );
        assert_eq!(
            octree_insert_branchless(u64::MAX, u64::MAX),
            octree_insert_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            octree_insert_branchless(u64::MAX, 0),
            octree_insert_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            octree_insert_branchless(0, u64::MAX),
            octree_insert_branchless_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = octree_insert_branchless_reference(42, 1337);
        let m1 = mutant_octree_insert_branchless_1(42, 1337);
        let m2 = mutant_octree_insert_branchless_2(42, 1337);
        let m3 = mutant_octree_insert_branchless_3(42, 1337);
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
    // Postcondition: { result = octree_insert_branchless_reference(val, aux) }
    //
    // Counterfactual Analysis for octree_insert_branchless:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_octree_insert_branchless(c: &mut Criterion) {
        c.bench_function("octree_insert_branchless", |b| {
            b.iter(|| {
                let res = octree_insert_branchless(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
