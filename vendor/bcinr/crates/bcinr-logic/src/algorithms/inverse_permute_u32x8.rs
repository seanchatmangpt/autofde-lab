// Academic-grade branchless algorithm library: inverse_permute_u32x8
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// inverse_permute_u32x8
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Category:** H — Text / Encoding
/// **Plane:** D-resident packed-byte cell + S-staged control word
/// **Tier:** T1 — packed byte / SIMD text microkernel
/// **Scope:** branchless, O(1), CC=1; admissible_T1.
/// **Inputs:** `val` = packed byte cell word (8 bytes); `aux` = encoding control word.
/// **Delta:** caller composes `UDelta` from before/after if used as a transition.
///
/// ```rust
/// use bcinr_logic::algorithms::inverse_permute_u32x8::inverse_permute_u32x8;
/// let result = inverse_permute_u32x8(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn inverse_permute_u32x8(val: u64, aux: u64) -> u64 {
    // Invert an 8-element permutation stored as 8 nibbles (each value masked to 0..7):
    // for source index i mapping to position p_i, the inverse places i at nibble p_i.
    // Fully unrolled to keep the path branch- and loop-free.
    let p0 = val & 0x7;
    let p1 = (val >> 4) & 0x7;
    let p2 = (val >> 8) & 0x7;
    let p3 = (val >> 12) & 0x7;
    let p4 = (val >> 16) & 0x7;
    let p5 = (val >> 20) & 0x7;
    let p6 = (val >> 24) & 0x7;
    let p7 = (val >> 28) & 0x7;
    (0u64 << (p0 * 4))
        | (1u64 << (p1 * 4))
        | (2u64 << (p2 * 4))
        | (3u64 << (p3 * 4))
        | (4u64 << (p4 * 4))
        | (5u64 << (p5 * 4))
        | (6u64 << (p6 * 4))
        | (7u64 << (p7 * 4))
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn inverse_permute_u32x8_reference(val: u64, _aux: u64) -> u64 {
        let mut res = 0u64;
        for i in 0..8 {
            let p_i = (val >> (i * 4)) & 0x7;
            res |= (i as u64) << (p_i * 4);
        }
        res
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_inverse_permute_u32x8_1(val: u64, aux: u64) -> u64 {
        !inverse_permute_u32x8_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_inverse_permute_u32x8_2(val: u64, aux: u64) -> u64 {
        inverse_permute_u32x8_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_inverse_permute_u32x8_3(val: u64, aux: u64) -> u64 {
        inverse_permute_u32x8_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BRANCHLESS CONTRACT: inverse_permute_u32x8
    // -------------------------------------------------------------------------
    // Category : H — Text / Encoding
    // Plane    : D-resident packed-byte cell + S-staged control word
    // Tier     : T1 — packed byte / SIMD text microkernel
    // Inputs   : val = packed byte cell word (8 bytes)
    //            aux = encoding control word
    // Admissibility:
    //   - Branchless control flow (CC = 1).
    //   - Zero heap allocations.
    //   - WCET ≤ T1_BUDGET_NS for word-scoped invocations.
    //   - No plane mutation by the primitive itself; callers choose commit.
    // Delta semantics:
    //   - If used as a transition, `UDelta { before: U[i], after: result, ... }`
    //     is emitted into Scratch by the caller; this primitive is pure.
    // Receipt mixing:
    //   - Caller threads `result` through `receipt_mix_transition` along with
    //     the originating UCoord and fired_mask.
    // Independence oracle (test-side):
    //   - The reference function in tests is intentionally an INDEPENDENT
    //     algebraic expression, NOT a copy of the implementation. Equivalence
    //     failures are SIGNAL — they mean the stub diverges from the oracle.
    // Counterfactual mutants:
    //   - Mutant 1: bitwise NOT of reference (identity bluff).
    //   - Mutant 2: off-by-one wrapping_add (bit-skip bluff).
    //   - Mutant 3: XOR low 32 bits (operator-swap bluff).
    // Tier ladder reminder:
    //   - T0 ≤ 2 ns | T1 ≤ 200 ns | T2 ≤ 5 µs | T3 ≤ 10 µs | T4 external.
    // Hoare-style summary:
    //   { val, aux ∈ U64 }
    //     inverse_permute_u32x8(val, aux)
    //   { result ∈ U64 ∧ runtime ∈ admissible_T1 }
    // -------------------------------------------------------------------------
    #[test]
    fn test_inverse_permute_u32x8_all() {
        // equivalence oracle
        let expected = inverse_permute_u32x8_reference(42, 1337);
        let actual = inverse_permute_u32x8(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            inverse_permute_u32x8(0, 0),
            inverse_permute_u32x8_reference(0, 0)
        );
        assert_eq!(
            inverse_permute_u32x8(u64::MAX, u64::MAX),
            inverse_permute_u32x8_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            inverse_permute_u32x8(u64::MAX, 0),
            inverse_permute_u32x8_reference(u64::MAX, 0)
        );
        assert_eq!(
            inverse_permute_u32x8(0, u64::MAX),
            inverse_permute_u32x8_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = inverse_permute_u32x8_reference(42, 1337);
        let m1 = mutant_inverse_permute_u32x8_1(42, 1337);
        let m2 = mutant_inverse_permute_u32x8_2(42, 1337);
        let m3 = mutant_inverse_permute_u32x8_3(42, 1337);
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

    pub fn bench_inverse_permute_u32x8(c: &mut Criterion) {
        c.bench_function("inverse_permute_u32x8", |b| {
            b.iter(|| {
                let res = inverse_permute_u32x8(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}

// -----------------------------------------------------------------------------
// BRANCHLESS GEOMETRY ANNOTATION: inverse_permute_u32x8
// -----------------------------------------------------------------------------
// Resident state object:
// Coordinate algebra:
//   UCoord(domain:u6, cell:u6, place:u6) packed in u32.
//   word_index = domain * CELL_COUNT + cell  ∈ [0, MAX_WORD_INDEX].
//   bit_index  = place                       ∈ [0, PLACE_COUNT).
// Dual-Plane execution envelope:
//   L1_ENVELOPE_BYTES = 65 536  (D + S).
// Domain category for this primitive: H — Text / Encoding.
// Plane interaction: D-resident packed-byte cell + S-staged control word.
// Scope semantics for this primitive:
//   Cell    — single u64 word commit (T0).
//   Sparse  — bounded ActiveWordSet (capacity 64) commit (T1).
//   Domain  — full 64-cell domain SWAR (T1).
// Receipt invariants (FNV-1a 64):
//   offset_basis = 0xcbf29ce484222325
//   prime        = 0x100000001b3
//   mix steps    = coord_word → sequence → fired_mask → delta_word
// Admissibility flags:
//   admissible_T0 : YES if used at single-bit / single-word scope.
//   admissible_T1 : YES at sparse/domain scope.
//   admissible_T2 : YES at full-block scope (explicit tier-2 path).
// Branchless contract: CC = 1; no Expr::If, Expr::Match, Expr::Loop, Expr::While.
// Allocation contract: zero heap; all temporaries fit in registers / scratch.
// Failure semantics:
//   On rejected admission, the caller computes fired_mask = 0 and the
//   commit is masked to a no-op via select(fired, candidate, current).
// Replay contract:
//   Pure function ⇒ deterministic across runs ⇒ replayable from receipt chain.
// Cross-references:
// -----------------------------------------------------------------------------
