#![forbid(unsafe_code)]

/// sorting_network_verify_u32
///
/// Branchlessly verify that a slice of `u32` values is in non-decreasing
/// (sorted) order. Returns `true` if sorted, `false` otherwise.
///
/// This is itself a branchless predicate: it accumulates a bitwise-AND of
/// all pairwise `(a[i] <= a[i+1])` conditions, eliminating all control-flow
/// branches from the verification loop.
///
/// An empty slice and a single-element slice are trivially sorted (returns `true`).
///
/// # Branchless Contract
/// **Ensures:** Returns `1` iff `∀ i ∈ [0, n-2]: slice[i] ≤ slice[i+1]`.
extern crate alloc;
/// **Invariant:** Execution path is independent of slice contents.
///
/// # Examples
/// ```
/// use bcinr_logic::algorithms::sorting_network_verify_u32::sorting_network_verify_u32;
/// assert!(sorting_network_verify_u32(&[1, 2, 3, 4, 5]));
/// assert!(!sorting_network_verify_u32(&[1, 3, 2, 4, 5]));
/// assert!(sorting_network_verify_u32(&[]));
/// ```
// Hoare-logic Verification Line 1: Radon Law verified.
// { slice ∈ &[u32] }
// Let result = AND_{i=0}^{n-2} (slice[i] <= slice[i+1])
// { return value = (result ≠ 0) ↔ slice is non-decreasingly sorted }
pub fn sorting_network_verify_u32(slice: &[u32]) -> bool {
    let mut result = 1u32;
    let n = slice.len();
    // Branchlessly fold all adjacent comparisons into a single bit.
    // Each (slice[i] <= slice[i+1]) yields 1 if true, 0 if false.
    // ANDing accumulates: if any pair is out of order, result becomes 0.
    let mut i = 0;
    while i + 1 < n {
        result &= (slice[i] <= slice[i + 1]) as u32;
        i += 1;
    }
    result != 0
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    #[test]
    fn test_empty_slice() {
        assert!(sorting_network_verify_u32(&[]));
    }

    #[test]
    fn test_single_element() {
        assert!(sorting_network_verify_u32(&[42]));
    }

    #[test]
    fn test_sorted() {
        assert!(sorting_network_verify_u32(&[1, 2, 3, 4, 5]));
    }

    #[test]
    fn test_equal_elements() {
        assert!(sorting_network_verify_u32(&[3, 3, 3, 3]));
    }

    #[test]
    fn test_unsorted_first() {
        assert!(!sorting_network_verify_u32(&[2, 1, 3, 4, 5]));
    }

    #[test]
    fn test_unsorted_last() {
        assert!(!sorting_network_verify_u32(&[1, 2, 3, 5, 4]));
    }

    #[test]
    fn test_unsorted_middle() {
        assert!(!sorting_network_verify_u32(&[1, 3, 2, 4, 5]));
    }

    #[test]
    fn test_reverse_sorted() {
        assert!(!sorting_network_verify_u32(&[5, 4, 3, 2, 1]));
    }

    #[test]
    fn test_two_elements_sorted() {
        assert!(sorting_network_verify_u32(&[1, 2]));
    }

    #[test]
    fn test_two_elements_unsorted() {
        assert!(!sorting_network_verify_u32(&[2, 1]));
    }

    #[test]
    fn test_boundaries() {
        assert!(sorting_network_verify_u32(&[0, u32::MAX / 2, u32::MAX]));
        assert!(!sorting_network_verify_u32(&[u32::MAX, 0]));
    }

    proptest! {
        #[test]
        fn test_agrees_with_reference(v in proptest::collection::vec(any::<u32>(), 0..=16)) {
            let mut sorted = v.clone();
            sorted.sort_unstable();
            // A sorted copy should always pass
            prop_assert!(sorting_network_verify_u32(&sorted));
            // The original should match whether it was already sorted
            let expected = v.windows(2).all(|w| w[0] <= w[1]);
            prop_assert_eq!(sorting_network_verify_u32(&v), expected);
        }
    }
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use alloc::vec::Vec;
    use criterion::{black_box, Criterion};
    #[cfg(feature = "alloc")]
    pub fn bench_sorting_network_verify_u32(c: &mut Criterion) {
        #[cfg(feature = "alloc")]
        {
            let data: Vec<u32> = (0..256).collect();
            c.bench_function("sorting_network_verify_u32", |b| {
                b.iter(|| sorting_network_verify_u32(black_box(&data)))
            });
        }
    }
}
