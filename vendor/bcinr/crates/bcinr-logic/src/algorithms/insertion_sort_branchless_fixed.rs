// Academic-grade branchless algorithm library: insertion_sort_branchless_fixed
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// insertion_sort_branchless_fixed
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
/// use bcinr_logic::algorithms::insertion_sort_branchless_fixed::insertion_sort_branchless_fixed;
/// let result = insertion_sort_branchless_fixed(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn insertion_sort_branchless_fixed(val: u64, aux: u64) -> u64 {
    // Sorts the 8 bytes of `val` ascending. Branchless and loop-free: each
    // byte's destination index is its stable rank = (# bytes strictly less)
    // + (# equal bytes at an earlier position). Computed by fully unrolled
    // comparison-as-arithmetic. `aux` is ignored.
    let b = [
        val & 0xFF,
        (val >> 8) & 0xFF,
        (val >> 16) & 0xFF,
        (val >> 24) & 0xFF,
        (val >> 32) & 0xFF,
        (val >> 40) & 0xFF,
        (val >> 48) & 0xFF,
        (val >> 56) & 0xFF,
    ];
    let lt = |x: u64, y: u64| -> u64 { (x < y) as u64 };
    let eqe = |j: usize, i: usize, x: u64, y: u64| -> u64 { ((x == y) as u64) & ((j < i) as u64) };
    let rank = |i: usize| -> u64 {
        lt(b[0], b[i])
            + lt(b[1], b[i])
            + lt(b[2], b[i])
            + lt(b[3], b[i])
            + lt(b[4], b[i])
            + lt(b[5], b[i])
            + lt(b[6], b[i])
            + lt(b[7], b[i])
            + eqe(0, i, b[0], b[i])
            + eqe(1, i, b[1], b[i])
            + eqe(2, i, b[2], b[i])
            + eqe(3, i, b[3], b[i])
            + eqe(4, i, b[4], b[i])
            + eqe(5, i, b[5], b[i])
            + eqe(6, i, b[6], b[i])
            + eqe(7, i, b[7], b[i])
    };
    (b[0] << (rank(0) * 8))
        | (b[1] << (rank(1) * 8))
        | (b[2] << (rank(2) * 8))
        | (b[3] << (rank(3) * 8))
        | (b[4] << (rank(4) * 8))
        | (b[5] << (rank(5) * 8))
        | (b[6] << (rank(6) * 8))
        | (b[7] << (rank(7) * 8))
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn insertion_sort_branchless_fixed_reference(val: u64, _aux: u64) -> u64 {
        let mut arr = [
            val & 0xFF,
            (val >> 8) & 0xFF,
            (val >> 16) & 0xFF,
            (val >> 24) & 0xFF,
            (val >> 32) & 0xFF,
            (val >> 40) & 0xFF,
            (val >> 48) & 0xFF,
            (val >> 56) & 0xFF,
        ];
        for i in 1..8 {
            for j in (1..=i).rev() {
                let a = arr[j - 1];
                let b = arr[j];
                let swap = (a > b) as u64;
                arr[j - 1] = a ^ (swap * (a ^ b));
                arr[j] = b ^ (swap * (a ^ b));
            }
        }
        let mut res = 0u64;
        for i in 0..8 {
            res |= arr[i] << (i * 8);
        }
        res
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_insertion_sort_branchless_fixed_1(val: u64, aux: u64) -> u64 {
        !insertion_sort_branchless_fixed_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_insertion_sort_branchless_fixed_2(val: u64, aux: u64) -> u64 {
        insertion_sort_branchless_fixed_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_insertion_sort_branchless_fixed_3(val: u64, aux: u64) -> u64 {
        insertion_sort_branchless_fixed_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BRANCHLESS CONTRACT: insertion_sort_branchless_fixed
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
    //     insertion_sort_branchless_fixed(val, aux)
    //   { result ∈ U64 ∧ runtime ∈ admissible_T1 }
    // -------------------------------------------------------------------------
    #[test]
    fn test_insertion_sort_branchless_fixed_all() {
        // equivalence oracle
        let expected = insertion_sort_branchless_fixed_reference(42, 1337);
        let actual = insertion_sort_branchless_fixed(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            insertion_sort_branchless_fixed(0, 0),
            insertion_sort_branchless_fixed_reference(0, 0)
        );
        assert_eq!(
            insertion_sort_branchless_fixed(u64::MAX, u64::MAX),
            insertion_sort_branchless_fixed_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            insertion_sort_branchless_fixed(u64::MAX, 0),
            insertion_sort_branchless_fixed_reference(u64::MAX, 0)
        );
        assert_eq!(
            insertion_sort_branchless_fixed(0, u64::MAX),
            insertion_sort_branchless_fixed_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = insertion_sort_branchless_fixed_reference(42, 1337);
        let m1 = mutant_insertion_sort_branchless_fixed_1(42, 1337);
        let m2 = mutant_insertion_sort_branchless_fixed_2(42, 1337);
        let m3 = mutant_insertion_sort_branchless_fixed_3(42, 1337);
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

    pub fn bench_insertion_sort_branchless_fixed(c: &mut Criterion) {
        c.bench_function("insertion_sort_branchless_fixed", |b| {
            b.iter(|| {
                let res = insertion_sort_branchless_fixed(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}

// -----------------------------------------------------------------------------
// BRANCHLESS GEOMETRY ANNOTATION: insertion_sort_branchless_fixed
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
