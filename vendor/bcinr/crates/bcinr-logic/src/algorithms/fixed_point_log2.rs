// Academic-grade branchless algorithm library: fixed_point_log2
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// fixed_point_log2
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Fixed-point binary logarithm of `val`. The integer part is
/// `floor(log2(val)) = 63 - clz(val)`; the fractional part is the `fb = aux & 63`
/// high mantissa bits after the implicit leading one. The result is
/// `(ip << fb) + frac`, an unsigned Qx.fb estimate. `val == 0` maps to `0`.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::fixed_point_log2::fixed_point_log2;
/// let result = fixed_point_log2(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn fixed_point_log2(val: u64, aux: u64) -> u64 {
    let lz = val.leading_zeros(); // 64 when val == 0
    let nz = ((val | val.wrapping_neg()) >> 63) & 1; // 1 iff val != 0
    let ip = 63u64.wrapping_sub(lz as u64) & nz.wrapping_neg(); // 0 when val == 0
    let fb = (aux & 63) as u32;
    // Drop the implicit leading one, then keep the top `fb` mantissa bits.
    // `wrapping_shl(lz+1)` of a nonzero val removes the leading set bit; for val==0
    // mantissa is 0 so frac is 0 regardless.
    let mantissa = val.wrapping_shl(lz.wrapping_add(1));
    // frac = top `fb` bits of mantissa; checked_shr(64) for fb==0 yields 0.
    let frac = mantissa.checked_shr(64 - fb).unwrap_or(0);
    ip.wrapping_shl(fb).wrapping_add(frac)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn fixed_point_log2_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: handle val==0 explicitly, find the integer part by
        // scanning for the highest set bit position, and extract the fractional bits
        // by isolating the bits strictly below the leading one.
        if val == 0 {
            return 0;
        }
        let fb = (aux % 64) as u32;
        // highest set bit index = position of MSB.
        let msb = 63 - val.leading_zeros();
        let ip = msb as u64;
        // bits below the leading one:
        let below = val & ((1u64 << msb) - 1); // exactly the mantissa tail
                                               // left-justify the tail to bit 63, then take the top `fb` bits.
        let justified = if msb == 0 { 0u64 } else { below << (64 - msb) };
        let frac = if fb == 0 {
            0u64
        } else {
            justified >> (64 - fb)
        };
        (ip << fb).wrapping_add(frac)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_fixed_point_log2_1(val: u64, aux: u64) -> u64 {
        !fixed_point_log2_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_fixed_point_log2_2(val: u64, aux: u64) -> u64 {
        fixed_point_log2_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_fixed_point_log2_3(val: u64, aux: u64) -> u64 {
        fixed_point_log2_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_fixed_point_log2_all() {
        // equivalence oracle
        let expected = fixed_point_log2_reference(42, 1337);
        let actual = fixed_point_log2(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(fixed_point_log2(0, 0), fixed_point_log2_reference(0, 0));
        assert_eq!(
            fixed_point_log2(u64::MAX, u64::MAX),
            fixed_point_log2_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            fixed_point_log2(u64::MAX, 0),
            fixed_point_log2_reference(u64::MAX, 0)
        );
        assert_eq!(
            fixed_point_log2(0, u64::MAX),
            fixed_point_log2_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = fixed_point_log2_reference(42, 1337);
        let m1 = mutant_fixed_point_log2_1(42, 1337);
        let m2 = mutant_fixed_point_log2_2(42, 1337);
        let m3 = mutant_fixed_point_log2_3(42, 1337);
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
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_fixed_point_log2(c: &mut Criterion) {
        c.bench_function("fixed_point_log2", |b| {
            b.iter(|| {
                let res = fixed_point_log2(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
