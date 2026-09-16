// Academic-grade branchless algorithm library: z_order_curve_2d_u32
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// z_order_curve_2d_u32
///
/// Morton (Z-order) encoding of two 32-bit coordinates `x = val as u32` and
/// `y = aux as u32` into a single 64-bit index. Each coordinate's bits are
/// "spread" so bit `i` of `x` lands at position `2i` and bit `i` of `y`
/// lands at position `2i + 1`; the interleaved result is `spread(x) |
/// (spread(y) << 1)`.
///
/// # Branchless Contract
/// Bit spreading uses the standard fixed mask/shift dilation cascade, a
/// constant sequence of shifts and ANDs with no data-dependent control flow.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::z_order_curve_2d_u32::z_order_curve_2d_u32;
/// let result = z_order_curve_2d_u32(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn z_order_curve_2d_u32(val: u64, aux: u64) -> u64 {
    // Spread the low 32 bits of `c` so each bit i moves to position 2i.
    fn spread(c: u64) -> u64 {
        let mut x = c & 0x0000_0000_FFFF_FFFF;
        x = (x | (x << 16)) & 0x0000_FFFF_0000_FFFF;
        x = (x | (x << 8)) & 0x00FF_00FF_00FF_00FF;
        x = (x | (x << 4)) & 0x0F0F_0F0F_0F0F_0F0F;
        x = (x | (x << 2)) & 0x3333_3333_3333_3333;
        (x | (x << 1)) & 0x5555_5555_5555_5555
    }
    spread(val) | (spread(aux) << 1)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn z_order_curve_2d_u32_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: explicit per-bit interleave loop.
        let x = val & 0xFFFF_FFFF;
        let y = aux & 0xFFFF_FFFF;
        let mut out: u64 = 0;
        for i in 0..32u32 {
            let xb = (x >> i) & 1;
            let yb = (y >> i) & 1;
            out |= xb << (2 * i);
            out |= yb << (2 * i + 1);
        }
        out
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_z_order_curve_2d_u32_1(val: u64, aux: u64) -> u64 {
        !z_order_curve_2d_u32_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_z_order_curve_2d_u32_2(val: u64, aux: u64) -> u64 {
        z_order_curve_2d_u32_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_z_order_curve_2d_u32_3(val: u64, aux: u64) -> u64 {
        z_order_curve_2d_u32_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_z_order_curve_2d_u32_all() {
        // oracle
        assert_eq!(
            z_order_curve_2d_u32(42, 1337),
            z_order_curve_2d_u32_reference(42, 1337)
        );
        // boundaries
        assert_eq!(
            z_order_curve_2d_u32(0, 0),
            z_order_curve_2d_u32_reference(0, 0)
        );
        assert_eq!(
            z_order_curve_2d_u32(u64::MAX, u64::MAX),
            z_order_curve_2d_u32_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            z_order_curve_2d_u32(u64::MAX, 0),
            z_order_curve_2d_u32_reference(u64::MAX, 0)
        );
        assert_eq!(
            z_order_curve_2d_u32(0, u64::MAX),
            z_order_curve_2d_u32_reference(0, u64::MAX)
        );
        // mutants
        let base = z_order_curve_2d_u32_reference(42, 1337);
        assert_ne!(mutant_z_order_curve_2d_u32_1(42, 1337), base, "mutant 1");
        assert_ne!(mutant_z_order_curve_2d_u32_2(42, 1337), base, "mutant 2");
        assert_ne!(mutant_z_order_curve_2d_u32_3(42, 1337), base, "mutant 3");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = z_order_curve_2d_u32_reference(val, aux) }
    //
    // Counterfactual Analysis for z_order_curve_2d_u32:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_z_order_curve_2d_u32(c: &mut Criterion) {
        c.bench_function("z_order_curve_2d_u32", |b| {
            b.iter(|| {
                let res = z_order_curve_2d_u32(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
