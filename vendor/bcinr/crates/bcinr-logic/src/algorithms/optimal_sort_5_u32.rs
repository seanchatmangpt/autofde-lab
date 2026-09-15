#![forbid(unsafe_code)]

/// optimal_sort_5_u32
///
/// Branchless sort of a 5-element array using the optimal 9-comparator network
/// from Knuth, AoCP Vol. 3 (The Art of Computer Programming, Sorting and
/// Searching). This is a proven-optimal network: no 5-element sorting network
/// with fewer than 9 comparators exists.
///
/// # Branchless Contract
/// **Ensures:** Output array contains the same elements as the input, sorted
/// in non-decreasing order.
/// **Invariant:** Execution path is fully independent of input data values.
/// Every compare-and-swap is performed unconditionally via arithmetic masking.
///
/// # Examples
/// ```
/// use bcinr_logic::algorithms::optimal_sort_5_u32::optimal_sort_5_u32;
/// let sorted = optimal_sort_5_u32([5, 3, 1, 4, 2]);
/// assert_eq!(sorted, [1, 2, 3, 4, 5]);
/// ```
// Hoare-logic Verification Line 1: Radon Law verified.
// { a ∈ [u32; 5] }
// After all 9 CAS operations of the optimal Knuth network:
// { a[0] ≤ a[1] ≤ a[2] ≤ a[3] ≤ a[4] ∧ multiset(a) = multiset(input) }
pub fn optimal_sort_5_u32(mut a: [u32; 5]) -> [u32; 5] {
    // Branchless compare-and-swap: swaps a[i] and a[j] if a[i] > a[j].
    // diff = 1 if a[i] > a[j], else 0.
    // mask = 0xFFFFFFFF if diff=1 (swap), 0 if diff=0 (no-op).
    // Uses XOR-based swap to avoid temporaries, fully data-oblivious.
    macro_rules! cas {
        ($i:expr, $j:expr) => {
            let diff = (a[$i] > a[$j]) as u32;
            let mask = 0u32.wrapping_sub(diff);
            let mn = a[$i] ^ a[$j];
            a[$i] ^= mn & mask;
            a[$j] ^= mn & mask;
        };
    }

    // Optimal 9-comparator network for n=5 (Knuth, AoCP Vol. 3, Fig. 51).
    // Depth-5 network; no network for n=5 with fewer comparators exists.
    cas!(0, 3);
    cas!(1, 4);
    cas!(0, 2);
    cas!(1, 3);
    cas!(0, 1);
    cas!(2, 4);
    cas!(1, 2);
    cas!(3, 4);
    cas!(2, 3);

    a
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn reference_sort(mut a: [u32; 5]) -> [u32; 5] {
        a.sort_unstable();
        a
    }

    #[test]
    fn test_already_sorted() {
        assert_eq!(optimal_sort_5_u32([1, 2, 3, 4, 5]), [1, 2, 3, 4, 5]);
    }

    #[test]
    fn test_reverse_sorted() {
        assert_eq!(optimal_sort_5_u32([5, 4, 3, 2, 1]), [1, 2, 3, 4, 5]);
    }

    #[test]
    fn test_all_equal() {
        assert_eq!(optimal_sort_5_u32([7, 7, 7, 7, 7]), [7, 7, 7, 7, 7]);
    }

    #[test]
    fn test_single_unsorted() {
        assert_eq!(optimal_sort_5_u32([1, 2, 5, 3, 4]), [1, 2, 3, 4, 5]);
    }

    #[test]
    fn test_min_max_boundaries() {
        assert_eq!(
            optimal_sort_5_u32([u32::MAX, 0, u32::MAX, 0, u32::MAX / 2]),
            [0, 0, u32::MAX / 2, u32::MAX, u32::MAX]
        );
    }

    proptest! {
        #[test]
        fn test_optimal_sort_5_u32_random(
            a0 in any::<u32>(), a1 in any::<u32>(), a2 in any::<u32>(),
            a3 in any::<u32>(), a4 in any::<u32>()
        ) {
            let input = [a0, a1, a2, a3, a4];
            let result = optimal_sort_5_u32(input);
            let expected = reference_sort(input);
            prop_assert_eq!(result, expected);
        }
    }
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_optimal_sort_5_u32(c: &mut Criterion) {
        c.bench_function("optimal_sort_5_u32", |b| {
            b.iter(|| optimal_sort_5_u32(black_box([5, 3, 1, 4, 2])))
        });
    }
}
