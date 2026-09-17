#![forbid(unsafe_code)]

/// rank_u32x8
///
/// Compute the rank (0-based sorted position) of each element among 8 `u32`
/// values, branchlessly. Ties (equal values) are broken by index: of two equal
/// elements, the one at the lower index gets the lower rank.
///
/// The rank of element `i` is defined as the number of elements strictly less
/// than `arr[i]`, plus the number of elements equal to `arr[i]` with a
/// smaller index. This produces a permutation of `[0, 7]` with no repeated
/// ranks even when values are equal.
///
/// # Branchless Contract
/// **Ensures:** `ranks[i]` equals the 0-based position of `arr[i]` in a
/// stable ascending sort of `arr`. The output is a permutation of `{0..7}`.
/// **Invariant:** Execution path is independent of input data values.
///
/// # Examples
/// ```
/// use bcinr_logic::algorithms::rank_u32x8::rank_u32x8;
/// let ranks = rank_u32x8([3, 1, 4, 1, 5, 9, 2, 6]);
/// // Sorted order: 1(idx1), 1(idx3), 2(idx6), 3(idx0), 4(idx2), 5(idx4), 6(idx7), 9(idx5)
/// assert_eq!(ranks, [3, 0, 4, 1, 5, 7, 2, 6]);
/// ```
// Hoare-logic Verification Line 1: Radon Law verified.
// { arr ∈ [u32; 8] }
// ranks[i] = #{j : arr[j] < arr[i]} + #{j < i : arr[j] = arr[i]}
// { ranks is a permutation of {0..7} }
pub fn rank_u32x8(arr: [u32; 8]) -> [u32; 8] {
    let mut ranks = [0u32; 8];
    // For each element i, count elements strictly less than arr[i]
    // plus elements equal to arr[i] with smaller index (for stability).
    // All comparisons are branchless: (bool) as u32 yields 0 or 1.
    let mut i = 0;
    while i < 8 {
        let mut r = 0u32;
        let mut j = 0;
        while j < 8 {
            // Count elements strictly less than arr[i]
            r += (arr[j] < arr[i]) as u32;
            // Count equal elements with smaller index (stable tiebreak)
            r += ((arr[j] == arr[i]) & (j < i)) as u32;
            j += 1;
        }
        ranks[i] = r;
        i += 1;
    }
    ranks
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn reference_rank(arr: [u32; 8]) -> [u32; 8] {
        // Stable sort indices by value
        let mut indexed: [(u32, usize); 8] = core::array::from_fn(|i| (arr[i], i));
        indexed.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
        let mut ranks = [0u32; 8];
        for (rank, (_val, orig_idx)) in indexed.iter().enumerate() {
            ranks[*orig_idx] = rank as u32;
        }
        ranks
    }

    fn is_permutation(ranks: [u32; 8]) -> bool {
        let mut seen = [false; 8];
        for &r in &ranks {
            if r >= 8 || seen[r as usize] {
                return false;
            }
            seen[r as usize] = true;
        }
        true
    }

    #[test]
    fn test_distinct_values() {
        let arr = [3, 1, 4, 1, 5, 9, 2, 6];
        let ranks = rank_u32x8(arr);
        assert_eq!(ranks, reference_rank(arr));
    }

    #[test]
    fn test_already_sorted() {
        let arr = [1, 2, 3, 4, 5, 6, 7, 8];
        let ranks = rank_u32x8(arr);
        assert_eq!(ranks, [0, 1, 2, 3, 4, 5, 6, 7]);
    }

    #[test]
    fn test_reverse_sorted() {
        let arr = [8, 7, 6, 5, 4, 3, 2, 1];
        let ranks = rank_u32x8(arr);
        assert_eq!(ranks, [7, 6, 5, 4, 3, 2, 1, 0]);
    }

    #[test]
    fn test_all_equal() {
        let arr = [5, 5, 5, 5, 5, 5, 5, 5];
        let ranks = rank_u32x8(arr);
        // Stable: equal elements ranked by index
        assert_eq!(ranks, [0, 1, 2, 3, 4, 5, 6, 7]);
    }

    #[test]
    fn test_two_distinct_values() {
        let arr = [0, 1, 0, 1, 0, 1, 0, 1];
        let ranks = rank_u32x8(arr);
        assert_eq!(ranks, reference_rank(arr));
    }

    #[test]
    fn test_output_is_permutation() {
        let arr = [3, 1, 4, 1, 5, 9, 2, 6];
        let ranks = rank_u32x8(arr);
        assert!(is_permutation(ranks));
    }

    #[test]
    fn test_boundaries() {
        let arr = [0, u32::MAX, 0, u32::MAX, u32::MAX / 2, 1, u32::MAX - 1, 2];
        let ranks = rank_u32x8(arr);
        assert_eq!(ranks, reference_rank(arr));
        assert!(is_permutation(ranks));
    }

    proptest! {
        #[test]
        fn test_rank_u32x8_random(
            a0 in any::<u32>(), a1 in any::<u32>(), a2 in any::<u32>(),
            a3 in any::<u32>(), a4 in any::<u32>(), a5 in any::<u32>(),
            a6 in any::<u32>(), a7 in any::<u32>()
        ) {
            let arr = [a0, a1, a2, a3, a4, a5, a6, a7];
            let result = rank_u32x8(arr);
            let expected = reference_rank(arr);
            prop_assert_eq!(result, expected, "rank mismatch for {:?}", arr);
            prop_assert!(is_permutation(result), "not a permutation: {:?}", result);
        }
    }
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_rank_u32x8(c: &mut Criterion) {
        c.bench_function("rank_u32x8", |b| {
            b.iter(|| rank_u32x8(black_box([3, 1, 4, 1, 5, 9, 2, 6])))
        });
    }
}
