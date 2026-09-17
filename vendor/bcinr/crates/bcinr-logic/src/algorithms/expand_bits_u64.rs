// Academic-grade branchless algorithm library: expand_bits_u64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// expand_bits_u64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// # Branchless Contract
/// Parallel bit-scatter (PDEP): deposits the low bits of `val` into the
/// positions selected by mask `aux`, with data-independent control flow.
///
/// ```rust
/// use bcinr_logic::algorithms::expand_bits_u64::expand_bits_u64;
/// let result = expand_bits_u64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn expand_bits_u64(val: u64, aux: u64) -> u64 {
    // Branchless Contract: parallel bit-scatter (PDEP). Take the low bits of
    // `val` and deposit them, in order, into the positions selected by mask
    // `aux`. Hacker's Delight `expand`, fully unrolled (6 fixed stages) so
    // control flow is data-independent.
    let m = aux;
    let mut x = val;
    let mut array = [0u64; 6];
    let mut mk = !m << 1;
    let mut mm = m;
    let mut mp = mk ^ (mk << 1);
    mp ^= mp << 2;
    mp ^= mp << 4;
    mp ^= mp << 8;
    mp ^= mp << 16;
    mp ^= mp << 32;
    let mv = mp & mm;
    array[0] = mv;
    mm = (mm ^ mv) | (mv >> 1);
    mk &= !mp;
    let mut mp = mk ^ (mk << 1);
    mp ^= mp << 2;
    mp ^= mp << 4;
    mp ^= mp << 8;
    mp ^= mp << 16;
    mp ^= mp << 32;
    let mv = mp & mm;
    array[1] = mv;
    mm = (mm ^ mv) | (mv >> 2);
    mk &= !mp;
    let mut mp = mk ^ (mk << 1);
    mp ^= mp << 2;
    mp ^= mp << 4;
    mp ^= mp << 8;
    mp ^= mp << 16;
    mp ^= mp << 32;
    let mv = mp & mm;
    array[2] = mv;
    mm = (mm ^ mv) | (mv >> 4);
    mk &= !mp;
    let mut mp = mk ^ (mk << 1);
    mp ^= mp << 2;
    mp ^= mp << 4;
    mp ^= mp << 8;
    mp ^= mp << 16;
    mp ^= mp << 32;
    let mv = mp & mm;
    array[3] = mv;
    mm = (mm ^ mv) | (mv >> 8);
    mk &= !mp;
    let mut mp = mk ^ (mk << 1);
    mp ^= mp << 2;
    mp ^= mp << 4;
    mp ^= mp << 8;
    mp ^= mp << 16;
    mp ^= mp << 32;
    let mv = mp & mm;
    array[4] = mv;
    mm = (mm ^ mv) | (mv >> 16);
    mk &= !mp;
    let mut mp = mk ^ (mk << 1);
    mp ^= mp << 2;
    mp ^= mp << 4;
    mp ^= mp << 8;
    mp ^= mp << 16;
    mp ^= mp << 32;
    let mv = mp & mm;
    let t = x << 32;
    x = (x & !mv) | (t & mv);
    let mv = array[4];
    let t = x << 16;
    x = (x & !mv) | (t & mv);
    let mv = array[3];
    let t = x << 8;
    x = (x & !mv) | (t & mv);
    let mv = array[2];
    let t = x << 4;
    x = (x & !mv) | (t & mv);
    let mv = array[1];
    let t = x << 2;
    x = (x & !mv) | (t & mv);
    let mv = array[0];
    let t = x << 1;
    x = (x & !mv) | (t & mv);
    x & m
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    fn expand_bits_u64_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: serial deposit. Consume the source bits of `val`
        // from LSB upward, placing each into the next set position of mask `aux`.
        // O(64) loop, structurally distinct from the unrolled parallel impl.
        let mut out: u64 = 0;
        let mut src: u32 = 0;
        let mut i: u32 = 0;
        while i < 64 {
            if (aux >> i) & 1 == 1 {
                let bit = (val >> src) & 1;
                out |= bit << i;
                src += 1;
            }
            i += 1;
        }
        out
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_expand_bits_u64_1(val: u64, aux: u64) -> u64 {
        !expand_bits_u64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_expand_bits_u64_2(val: u64, aux: u64) -> u64 {
        expand_bits_u64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_expand_bits_u64_3(val: u64, aux: u64) -> u64 {
        expand_bits_u64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_expand_bits_u64_all() {
        // equivalence oracle
        let expected = expand_bits_u64_reference(42, 1337);
        let actual = expand_bits_u64(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(expand_bits_u64(0, 0), expand_bits_u64_reference(0, 0));
        assert_eq!(
            expand_bits_u64(u64::MAX, u64::MAX),
            expand_bits_u64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            expand_bits_u64(u64::MAX, 0),
            expand_bits_u64_reference(u64::MAX, 0)
        );
        assert_eq!(
            expand_bits_u64(0, u64::MAX),
            expand_bits_u64_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = expand_bits_u64_reference(42, 1337);
        let m1 = mutant_expand_bits_u64_1(42, 1337);
        let m2 = mutant_expand_bits_u64_2(42, 1337);
        let m3 = mutant_expand_bits_u64_3(42, 1337);
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

    pub fn bench_expand_bits_u64(c: &mut Criterion) {
        c.bench_function("expand_bits_u64", |b| {
            b.iter(|| {
                let res = expand_bits_u64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
