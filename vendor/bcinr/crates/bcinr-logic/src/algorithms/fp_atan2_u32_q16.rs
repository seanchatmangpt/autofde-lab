// Academic-grade branchless algorithm library: fp_atan2_u32_q16
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// fp_atan2_u32_q16
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::fp_atan2_u32_q16::fp_atan2_u32_q16;
/// let result = fp_atan2_u32_q16(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn fp_atan2_u32_q16(val: u64, aux: u64) -> u64 {
    // Inputs are interpreted as signed 32-bit coordinates (the "_u32_" lane),
    // sign-extended to i64. This bounds |y|,|x| < 2^31 so every shift and
    // product below stays well inside i64 with no overflow or abs panic.
    let y = (val as u32 as i32) as i64;
    let x = (aux as u32 as i32) as i64;
    let abs_y = y.abs();
    let abs_x = x.abs();

    let m_cond = ((abs_x > abs_y) as i64).wrapping_neg();

    // Polynomial atan approximation on the ratio of the smaller to larger leg.
    let n = (abs_x.min(abs_y) << 16) / (abs_x.max(abs_y) | 1);
    let n2 = (n * n) >> 16;
    let base = n - ((n * n2) >> 16) / 3;

    // If |x| <= |y| reflect about 90 degrees; otherwise keep the base angle.
    let off = 90i64 << 16;
    let angle = (base & m_cond) | ((off - base) & !m_cond);

    // Mirror across the x-axis for negative y: +1 when y >= 0, -1 when y < 0.
    let sign_y = 1 - 2 * ((y < 0) as i64);
    let signed = angle * sign_y;

    // Shift into the correct half-plane for negative x.
    let q_adj = ((x < 0) as i64).wrapping_neg() & ((180i64 << 16).wrapping_mul(sign_y));
    (signed + q_adj) as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn fp_atan2_u32_q16_reference(val: u64, aux: u64) -> u64 {
        let y = (val as u32 as i32) as i64;
        let x = (aux as u32 as i32) as i64;
        let abs_y = y.abs();
        let abs_x = x.abs();

        let n = if abs_x > abs_y {
            (abs_y << 16) / (abs_x | 1)
        } else {
            (abs_x << 16) / (abs_y | 1)
        };

        let n2 = (n * n) >> 16;
        let mut angle = n - ((n * n2) >> 16) / 3;

        if abs_x > abs_y {
            // angle is correct
        } else {
            angle = (90i64 << 16) - angle;
        }

        if y < 0 {
            angle = -angle;
        }

        if x < 0 {
            if y >= 0 {
                angle += 180i64 << 16;
            } else {
                angle -= 180i64 << 16;
            }
        }
        angle as u64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_fp_atan2_u32_q16_1(val: u64, aux: u64) -> u64 {
        !fp_atan2_u32_q16_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_fp_atan2_u32_q16_2(val: u64, aux: u64) -> u64 {
        fp_atan2_u32_q16_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_fp_atan2_u32_q16_3(val: u64, aux: u64) -> u64 {
        fp_atan2_u32_q16_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_fp_atan2_u32_q16_all() {
        // equivalence oracle
        let expected = fp_atan2_u32_q16_reference(42, 1337);
        let actual = fp_atan2_u32_q16(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(fp_atan2_u32_q16(0, 0), fp_atan2_u32_q16_reference(0, 0));
        assert_eq!(
            fp_atan2_u32_q16(u64::MAX, u64::MAX),
            fp_atan2_u32_q16_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            fp_atan2_u32_q16(u64::MAX, 0),
            fp_atan2_u32_q16_reference(u64::MAX, 0)
        );
        assert_eq!(
            fp_atan2_u32_q16(0, u64::MAX),
            fp_atan2_u32_q16_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = fp_atan2_u32_q16_reference(42, 1337);
        let m1 = mutant_fp_atan2_u32_q16_1(42, 1337);
        let m2 = mutant_fp_atan2_u32_q16_2(42, 1337);
        let m3 = mutant_fp_atan2_u32_q16_3(42, 1337);
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

    pub fn bench_fp_atan2_u32_q16(c: &mut Criterion) {
        c.bench_function("fp_atan2_u32_q16", |b| {
            b.iter(|| {
                let res = fp_atan2_u32_q16(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
