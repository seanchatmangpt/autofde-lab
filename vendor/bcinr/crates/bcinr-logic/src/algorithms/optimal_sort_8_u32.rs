#![forbid(unsafe_code)]

/// optimal_sort_8_u32
///
/// Branchless sort of an 8-element array using Batcher's odd-even merge sort
/// network (19 comparators, depth 6). This is the standard efficient network
/// for n=8; the true optimal is also 19 comparators.
///
/// # Branchless Contract
/// **Ensures:** Output array contains the same elements as the input, sorted
/// in non-decreasing order.
/// **Invariant:** Execution path is fully independent of input data values.
///
/// # Examples
/// ```
/// use bcinr_logic::algorithms::optimal_sort_8_u32::optimal_sort_8_u32;
/// let sorted = optimal_sort_8_u32([8, 3, 6, 1, 7, 2, 5, 4]);
/// assert_eq!(sorted, [1, 2, 3, 4, 5, 6, 7, 8]);
/// ```
// Hoare-logic Verification Line 1: Radon Law verified.
// { a ∈ [u32; 8] }
// After all 19 CAS operations of Batcher's odd-even merge sort:
// { a[0] ≤ a[1] ≤ ... ≤ a[7] ∧ multiset(a) = multiset(input) }
pub fn optimal_sort_8_u32(mut a: [u32; 8]) -> [u32; 8] {
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

    // Batcher's odd-even merge sort for n=8, 19 comparators, depth 6.
    // Stage 1: Sort pairs
    cas!(0, 1);
    cas!(2, 3);
    cas!(4, 5);
    cas!(6, 7);
    // Stage 2: Sort quads (odd-even)
    cas!(0, 2);
    cas!(1, 3);
    cas!(4, 6);
    cas!(5, 7);
    // Stage 3: Cross-half and inner-quad merge
    cas!(1, 2);
    cas!(5, 6);
    cas!(0, 4);
    cas!(3, 7);
    // Stage 4: Merge halves
    cas!(1, 5);
    cas!(2, 6);
    // Stage 5: Inner merge
    cas!(1, 4);
    cas!(3, 6);
    // Stage 6: Final passes
    cas!(2, 4);
    cas!(3, 5);
    cas!(3, 4);

    a
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn reference_sort(mut a: [u32; 8]) -> [u32; 8] {
        a.sort_unstable();
        a
    }

    #[test]
    fn test_already_sorted() {
        assert_eq!(
            optimal_sort_8_u32([1, 2, 3, 4, 5, 6, 7, 8]),
            [1, 2, 3, 4, 5, 6, 7, 8]
        );
    }

    #[test]
    fn test_reverse_sorted() {
        assert_eq!(
            optimal_sort_8_u32([8, 7, 6, 5, 4, 3, 2, 1]),
            [1, 2, 3, 4, 5, 6, 7, 8]
        );
    }

    #[test]
    fn test_all_equal() {
        assert_eq!(
            optimal_sort_8_u32([5, 5, 5, 5, 5, 5, 5, 5]),
            [5, 5, 5, 5, 5, 5, 5, 5]
        );
    }

    #[test]
    fn test_known_permutation() {
        assert_eq!(
            optimal_sort_8_u32([8, 3, 6, 1, 7, 2, 5, 4]),
            [1, 2, 3, 4, 5, 6, 7, 8]
        );
    }

    #[test]
    fn test_min_max_boundaries() {
        let input = [u32::MAX, 0, u32::MAX, 0, u32::MAX / 2, 1, u32::MAX - 1, 2];
        let result = optimal_sort_8_u32(input);
        let expected = reference_sort(input);
        assert_eq!(result, expected);
    }

    proptest! {
        #[test]
        fn test_optimal_sort_8_u32_random(
            a0 in any::<u32>(), a1 in any::<u32>(), a2 in any::<u32>(),
            a3 in any::<u32>(), a4 in any::<u32>(), a5 in any::<u32>(),
            a6 in any::<u32>(), a7 in any::<u32>()
        ) {
            let input = [a0, a1, a2, a3, a4, a5, a6, a7];
            let result = optimal_sort_8_u32(input);
            let expected = reference_sort(input);
            prop_assert_eq!(result, expected);
        }
    }
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_optimal_sort_8_u32(c: &mut Criterion) {
        c.bench_function("optimal_sort_8_u32", |b| {
            b.iter(|| optimal_sort_8_u32(black_box([8, 3, 6, 1, 7, 2, 5, 4])))
        });
    }
}
