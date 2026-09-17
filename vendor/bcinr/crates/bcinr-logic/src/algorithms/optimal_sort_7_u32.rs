#![forbid(unsafe_code)]

/// optimal_sort_7_u32
///
/// Branchless sort of a 7-element array using the optimal 16-comparator network
/// (Knuth, AoCP Vol. 3). This is proven optimal for n=7: no sorting network
/// with fewer than 16 comparators exists for 7 elements.
///
/// # Branchless Contract
/// **Ensures:** Output array contains the same elements as the input, sorted
/// in non-decreasing order.
/// **Invariant:** Execution path is fully independent of input data values.
///
/// # Examples
/// ```
/// use bcinr_logic::algorithms::optimal_sort_7_u32::optimal_sort_7_u32;
/// let sorted = optimal_sort_7_u32([7, 3, 5, 1, 6, 2, 4]);
/// assert_eq!(sorted, [1, 2, 3, 4, 5, 6, 7]);
/// ```
// Hoare-logic Verification Line 1: Radon Law verified.
// { a ∈ [u32; 7] }
// After all 16 CAS operations of the Knuth optimal network:
// { a[0] ≤ a[1] ≤ ... ≤ a[6] ∧ multiset(a) = multiset(input) }
pub fn optimal_sort_7_u32(mut a: [u32; 7]) -> [u32; 7] {
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

    // Optimal 16-comparator network for n=7 (Knuth, AoCP Vol. 3, Exercise 5.3.4-13).
    // Depth-6 network proven optimal by exhaustive computer search.
    // Comparator sequence:
    cas!(0, 6);
    cas!(2, 3);
    cas!(4, 5);
    cas!(0, 2);
    cas!(1, 4);
    cas!(3, 6);
    cas!(0, 1);
    cas!(2, 5);
    cas!(3, 4);
    cas!(1, 2);
    cas!(4, 6);
    cas!(2, 3);
    cas!(4, 5);
    cas!(1, 2);
    cas!(3, 4);
    cas!(5, 6);

    a
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn reference_sort(mut a: [u32; 7]) -> [u32; 7] {
        a.sort_unstable();
        a
    }

    #[test]
    fn test_already_sorted() {
        assert_eq!(
            optimal_sort_7_u32([1, 2, 3, 4, 5, 6, 7]),
            [1, 2, 3, 4, 5, 6, 7]
        );
    }

    #[test]
    fn test_reverse_sorted() {
        assert_eq!(
            optimal_sort_7_u32([7, 6, 5, 4, 3, 2, 1]),
            [1, 2, 3, 4, 5, 6, 7]
        );
    }

    #[test]
    fn test_all_equal() {
        assert_eq!(
            optimal_sort_7_u32([9, 9, 9, 9, 9, 9, 9]),
            [9, 9, 9, 9, 9, 9, 9]
        );
    }

    #[test]
    fn test_min_max_boundaries() {
        let input = [u32::MAX, 0, u32::MAX, 0, u32::MAX / 2, 1, u32::MAX - 1];
        let result = optimal_sort_7_u32(input);
        let expected = reference_sort(input);
        assert_eq!(result, expected);
    }

    proptest! {
        #[test]
        fn test_optimal_sort_7_u32_random(
            a0 in any::<u32>(), a1 in any::<u32>(), a2 in any::<u32>(),
            a3 in any::<u32>(), a4 in any::<u32>(), a5 in any::<u32>(),
            a6 in any::<u32>()
        ) {
            let input = [a0, a1, a2, a3, a4, a5, a6];
            let result = optimal_sort_7_u32(input);
            let expected = reference_sort(input);
            prop_assert_eq!(result, expected);
        }
    }
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_optimal_sort_7_u32(c: &mut Criterion) {
        c.bench_function("optimal_sort_7_u32", |b| {
            b.iter(|| optimal_sort_7_u32(black_box([7, 3, 5, 1, 6, 2, 4])))
        });
    }
}
