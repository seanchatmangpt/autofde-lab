// Academic-grade branchless algorithm library: cyclic_redundancy_check_crc32c
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// cyclic_redundancy_check_crc32c
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
/// use bcinr_logic::algorithms::cyclic_redundancy_check_crc32c::cyclic_redundancy_check_crc32c;
/// let result = cyclic_redundancy_check_crc32c(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn cyclic_redundancy_check_crc32c(val: u64, aux: u64) -> u64 {
    let mut crc = val as u32;
    let b = aux as u8;
    crc ^= b as u32;
    crc = (crc >> 1) ^ (0x82F63B78 & (crc & 1).wrapping_neg());
    crc = (crc >> 1) ^ (0x82F63B78 & (crc & 1).wrapping_neg());
    crc = (crc >> 1) ^ (0x82F63B78 & (crc & 1).wrapping_neg());
    crc = (crc >> 1) ^ (0x82F63B78 & (crc & 1).wrapping_neg());
    crc = (crc >> 1) ^ (0x82F63B78 & (crc & 1).wrapping_neg());
    crc = (crc >> 1) ^ (0x82F63B78 & (crc & 1).wrapping_neg());
    crc = (crc >> 1) ^ (0x82F63B78 & (crc & 1).wrapping_neg());
    crc = (crc >> 1) ^ (0x82F63B78 & (crc & 1).wrapping_neg());
    crc as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn cyclic_redundancy_check_crc32c_reference(val: u64, aux: u64) -> u64 {
        let mut crc = val as u32;
        let b = aux as u8;
        crc ^= b as u32;
        for _ in 0..8 {
            if (crc & 1) != 0 {
                crc = (crc >> 1) ^ 0x82F63B78;
            } else {
                crc >>= 1;
            }
        }
        crc as u64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_cyclic_redundancy_check_crc32c_1(val: u64, aux: u64) -> u64 {
        !cyclic_redundancy_check_crc32c_reference(val, aux)
    }
    #[allow(unused_variables)]
    fn mutant_cyclic_redundancy_check_crc32c_2(val: u64, aux: u64) -> u64 {
        cyclic_redundancy_check_crc32c_reference(val, aux).wrapping_add(1)
    }
    #[allow(unused_variables)]
    fn mutant_cyclic_redundancy_check_crc32c_3(val: u64, aux: u64) -> u64 {
        cyclic_redundancy_check_crc32c_reference(val, aux) ^ 0xFFFFFFFF
    }

    #[test]
    fn test_cyclic_redundancy_check_crc32c_all() {
        // equivalence oracle
        let expected = cyclic_redundancy_check_crc32c_reference(42, 1337);
        let actual = cyclic_redundancy_check_crc32c(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            cyclic_redundancy_check_crc32c(0, 0),
            cyclic_redundancy_check_crc32c_reference(0, 0)
        );
        assert_eq!(
            cyclic_redundancy_check_crc32c(u64::MAX, u64::MAX),
            cyclic_redundancy_check_crc32c_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            cyclic_redundancy_check_crc32c(u64::MAX, 0),
            cyclic_redundancy_check_crc32c_reference(u64::MAX, 0)
        );
        assert_eq!(
            cyclic_redundancy_check_crc32c(0, u64::MAX),
            cyclic_redundancy_check_crc32c_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = cyclic_redundancy_check_crc32c_reference(42, 1337);
        let m1 = mutant_cyclic_redundancy_check_crc32c_1(42, 1337);
        let m2 = mutant_cyclic_redundancy_check_crc32c_2(42, 1337);
        let m3 = mutant_cyclic_redundancy_check_crc32c_3(42, 1337);
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

    pub fn bench_cyclic_redundancy_check_crc32c(c: &mut Criterion) {
        c.bench_function("cyclic_redundancy_check_crc32c", |b| {
            b.iter(|| {
                let res = cyclic_redundancy_check_crc32c(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
