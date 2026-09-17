#![forbid(unsafe_code)]

/// sort_stable_key_value_u32x8
///
/// Stable sort of 8 `(key, value)` pairs by key, branchlessly.
///
/// Stability means that pairs with equal keys appear in the output in the same
/// relative order as in the input. This is achieved by computing the stable
/// rank of each key (using the same tie-breaking scheme as `rank_u32x8`) and
/// using those ranks as output positions.
///
/// # Branchless Contract
/// **Ensures:** Output pairs are sorted in non-decreasing key order. For
/// pairs with equal keys, original relative order is preserved (stable).
/// **Invariant:** Execution path is fully independent of input data values.
///
/// # Examples
/// ```
/// use bcinr_logic::algorithms::sort_stable_key_value_u32x8::sort_stable_key_value_u32x8;
/// let pairs = [(3u32, 30u32), (1, 10), (2, 20), (1, 11), (2, 21), (0, 0), (1, 12), (3, 31)];
/// let sorted = sort_stable_key_value_u32x8(pairs);
/// // Keys: 0, 1, 1, 1, 2, 2, 3, 3
/// // Values for key=1 in original order: 10, 11, 12
/// assert_eq!(sorted[0], (0, 0));
/// assert_eq!(sorted[1], (1, 10));
/// assert_eq!(sorted[2], (1, 11));
/// assert_eq!(sorted[3], (1, 12));
/// assert_eq!(sorted[4], (2, 20));
/// assert_eq!(sorted[5], (2, 21));
/// ```
// Hoare-logic Verification Line 1: Radon Law verified.
// { pairs ∈ [(u32, u32); 8] }
// ranks[i] = stable rank of pairs[i].0 among all keys
// output[ranks[i]] = pairs[i]
// { output sorted by key, stable for equal keys }
pub fn sort_stable_key_value_u32x8(pairs: [(u32, u32); 8]) -> [(u32, u32); 8] {
    // Compute stable rank for each key.
    // rank[i] = number of keys < pairs[i].0
    //         + number of equal keys at earlier indices (stability tiebreak).
    // All comparisons are branchless: (bool) as u32 yields 0 or 1.
    let mut ranks = [0u32; 8];
    let mut i = 0;
    while i < 8 {
        let mut r = 0u32;
        let mut j = 0;
        while j < 8 {
            r += (pairs[j].0 < pairs[i].0) as u32;
            r += ((pairs[j].0 == pairs[i].0) & (j < i)) as u32;
            j += 1;
        }
        ranks[i] = r;
        i += 1;
    }

    // Scatter pairs into output positions given by their ranks.
    // Because ranks is a permutation of {0..7}, each output slot is written exactly once.
    let mut output = [(0u32, 0u32); 8];
    let mut i = 0;
    while i < 8 {
        output[ranks[i] as usize] = pairs[i];
        i += 1;
    }
    output
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn reference_stable_sort(pairs: [(u32, u32); 8]) -> [(u32, u32); 8] {
        let mut v: [(u32, u32); 8] = pairs;
        // Rust's sort_by is stable
        v.sort_by_key(|a| a.0);
        v
    }

    fn keys_sorted(sorted: &[(u32, u32); 8]) -> bool {
        sorted.windows(2).all(|w| w[0].0 <= w[1].0)
    }

    #[test]
    fn test_distinct_keys() {
        let pairs = [
            (5, 50),
            (3, 30),
            (7, 70),
            (1, 10),
            (6, 60),
            (2, 20),
            (4, 40),
            (8, 80),
        ];
        let result = sort_stable_key_value_u32x8(pairs);
        let expected = reference_stable_sort(pairs);
        assert_eq!(result, expected);
    }

    #[test]
    fn test_already_sorted() {
        let pairs = [
            (1, 10),
            (2, 20),
            (3, 30),
            (4, 40),
            (5, 50),
            (6, 60),
            (7, 70),
            (8, 80),
        ];
        let result = sort_stable_key_value_u32x8(pairs);
        assert_eq!(result, pairs);
    }

    #[test]
    fn test_reverse_sorted() {
        let pairs = [
            (8, 80),
            (7, 70),
            (6, 60),
            (5, 50),
            (4, 40),
            (3, 30),
            (2, 20),
            (1, 10),
        ];
        let result = sort_stable_key_value_u32x8(pairs);
        let expected = reference_stable_sort(pairs);
        assert_eq!(result, expected);
    }

    #[test]
    fn test_all_equal_keys() {
        // All keys equal: values must remain in original order (stability)
        let pairs = [
            (1, 0),
            (1, 1),
            (1, 2),
            (1, 3),
            (1, 4),
            (1, 5),
            (1, 6),
            (1, 7),
        ];
        let result = sort_stable_key_value_u32x8(pairs);
        // With equal keys, stable sort preserves original order
        assert_eq!(result, pairs);
    }

    #[test]
    fn test_stability_with_duplicates() {
        let pairs = [
            (3u32, 30u32),
            (1, 10),
            (2, 20),
            (1, 11),
            (2, 21),
            (0, 0),
            (1, 12),
            (3, 31),
        ];
        let result = sort_stable_key_value_u32x8(pairs);
        let expected = reference_stable_sort(pairs);
        assert_eq!(result, expected);
        // Explicitly verify stability for key=1
        assert_eq!(result[1], (1, 10));
        assert_eq!(result[2], (1, 11));
        assert_eq!(result[3], (1, 12));
    }

    #[test]
    fn test_output_keys_sorted() {
        let pairs = [
            (5, 0),
            (3, 1),
            (8, 2),
            (1, 3),
            (6, 4),
            (2, 5),
            (4, 6),
            (7, 7),
        ];
        let result = sort_stable_key_value_u32x8(pairs);
        assert!(keys_sorted(&result));
    }

    #[test]
    fn test_boundaries() {
        let pairs = [
            (u32::MAX, 0),
            (0, 1),
            (u32::MAX, 2),
            (0, 3),
            (u32::MAX / 2, 4),
            (1, 5),
            (u32::MAX - 1, 6),
            (2, 7),
        ];
        let result = sort_stable_key_value_u32x8(pairs);
        let expected = reference_stable_sort(pairs);
        assert_eq!(result, expected);
    }

    proptest! {
        #[test]
        fn test_sort_stable_key_value_u32x8_random(
            k0 in any::<u32>(), v0 in any::<u32>(),
            k1 in any::<u32>(), v1 in any::<u32>(),
            k2 in any::<u32>(), v2 in any::<u32>(),
            k3 in any::<u32>(), v3 in any::<u32>(),
            k4 in any::<u32>(), v4 in any::<u32>(),
            k5 in any::<u32>(), v5 in any::<u32>(),
            k6 in any::<u32>(), v6 in any::<u32>(),
            k7 in any::<u32>(), v7 in any::<u32>()
        ) {
            let pairs = [(k0,v0),(k1,v1),(k2,v2),(k3,v3),(k4,v4),(k5,v5),(k6,v6),(k7,v7)];
            let result = sort_stable_key_value_u32x8(pairs);
            let expected = reference_stable_sort(pairs);
            prop_assert_eq!(result, expected, "mismatch for input {:?}", pairs);
        }
    }
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_sort_stable_key_value_u32x8(c: &mut Criterion) {
        let pairs = [
            (5u32, 50u32),
            (3, 30),
            (7, 70),
            (1, 10),
            (6, 60),
            (2, 20),
            (4, 40),
            (8, 80),
        ];
        c.bench_function("sort_stable_key_value_u32x8", |b| {
            b.iter(|| sort_stable_key_value_u32x8(black_box(pairs)))
        });
    }
}
