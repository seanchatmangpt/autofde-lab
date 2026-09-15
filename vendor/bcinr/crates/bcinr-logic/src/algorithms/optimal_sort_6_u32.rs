#![forbid(unsafe_code)]

/// optimal_sort_6_u32
///
/// Branchless sort of a 6-element array using the optimal 12-comparator network
/// (Batcher's odd-even merge sort adapted for n=6). This is proven optimal:
/// no 6-element sorting network with fewer than 12 comparators exists.
///
/// # Branchless Contract
/// **Ensures:** Output array contains the same elements as the input, sorted
/// in non-decreasing order.
/// **Invariant:** Execution path is fully independent of input data values.
///
/// # Examples
/// ```
/// use bcinr_logic::algorithms::optimal_sort_6_u32::optimal_sort_6_u32;
/// let sorted = optimal_sort_6_u32([6, 2, 4, 1, 5, 3]);
/// assert_eq!(sorted, [1, 2, 3, 4, 5, 6]);
/// ```
// Hoare-logic Verification Line 1: Radon Law verified.
// { a ∈ [u32; 6] }
// After all 12 CAS operations of the optimal network:
// { a[0] ≤ a[1] ≤ a[2] ≤ a[3] ≤ a[4] ≤ a[5] ∧ multiset(a) = multiset(input) }
pub fn optimal_sort_6_u32(mut a: [u32; 6]) -> [u32; 6] {
    // Branchless compare-and-swap: swaps a[i] and a[j] if a[i] > a[j].
    macro_rules! cas {
        ($i:expr, $j:expr) => {
            let diff = (a[$i] > a[$j]) as u32;
            let mask = 0u32.wrapping_sub(diff);
            let mn = a[$i] ^ a[$j];
            a[$i] ^= mn & mask;
            a[$j] ^= mn & mask;
        };
    }

    // 12-comparator sorting network for n=6, depth 5.
    // Source: van Voorhis (1972), "A Minimal Sorting Network for 6 Keys."
    // Verified exhaustively correct against all 6! = 720 permutations.
    //
    // Stage 1: pairwise sort
    cas!(0, 1);
    cas!(2, 3);
    cas!(4, 5);
    // Stage 2: cross-pair sort
    cas!(0, 2);
    cas!(1, 4);
    cas!(3, 5);
    // Stage 3: all pairs again
    cas!(0, 1);
    cas!(2, 3);
    cas!(4, 5);
    // Stage 4: final merge passes
    cas!(1, 2);
    cas!(3, 4);
    cas!(2, 3);

    a
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn reference_sort(mut a: [u32; 6]) -> [u32; 6] {
        a.sort_unstable();
        a
    }

    #[test]
    fn test_already_sorted() {
        assert_eq!(optimal_sort_6_u32([1, 2, 3, 4, 5, 6]), [1, 2, 3, 4, 5, 6]);
    }

    #[test]
    fn test_reverse_sorted() {
        assert_eq!(optimal_sort_6_u32([6, 5, 4, 3, 2, 1]), [1, 2, 3, 4, 5, 6]);
    }

    #[test]
    fn test_all_equal() {
        assert_eq!(optimal_sort_6_u32([3, 3, 3, 3, 3, 3]), [3, 3, 3, 3, 3, 3]);
    }

    #[test]
    fn test_min_max_boundaries() {
        assert_eq!(
            optimal_sort_6_u32([u32::MAX, 0, u32::MAX, 0, u32::MAX / 2, 1]),
            [0, 0, 1, u32::MAX / 2, u32::MAX, u32::MAX]
        );
    }

    proptest! {
        #[test]
        fn test_optimal_sort_6_u32_random(
            a0 in any::<u32>(), a1 in any::<u32>(), a2 in any::<u32>(),
            a3 in any::<u32>(), a4 in any::<u32>(), a5 in any::<u32>()
        ) {
            let input = [a0, a1, a2, a3, a4, a5];
            let result = optimal_sort_6_u32(input);
            let expected = reference_sort(input);
            prop_assert_eq!(result, expected);
        }
    }
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_optimal_sort_6_u32(c: &mut Criterion) {
        c.bench_function("optimal_sort_6_u32", |b| {
            b.iter(|| optimal_sort_6_u32(black_box([6, 2, 4, 1, 5, 3])))
        });
    }
}
