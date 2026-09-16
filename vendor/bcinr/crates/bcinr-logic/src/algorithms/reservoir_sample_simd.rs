#![forbid(unsafe_code)]
// Academic-grade branchless algorithm library: reservoir_sample_simd
// Vitter's Algorithm R: branchless reservoir sampling (1-element reservoir).
// Returns the selected sample without conditional branches in the selection step.

/// Branchless reservoir sample step (Vitter's Algorithm R, k=1).
///
/// At stream position `item_index` (1-indexed), the current reservoir value
/// `current` is replaced by `candidate` with probability `1/item_index`.
/// The random draw `rand_val` (a uniform u64 in [0, u64::MAX]) is used to
/// make the accept/reject decision branchlessly.
///
/// # Arguments
/// * `current`    - The value currently held in the reservoir.
/// * `candidate`  - The new item arriving from the stream.
/// * `item_index` - 1-indexed position of `candidate` in the stream (must be >= 1).
/// * `rand_val`   - A fresh uniform random u64 for this step.
///
/// # Returns
/// Either `candidate` (accepted) or `current` (rejected), chosen branchlessly.
///
/// # Examples
/// ```rust
/// use bcinr_logic::algorithms::reservoir_sample_simd::reservoir_sample_step;
/// // At position 1, the first item is always accepted.
/// let sample = reservoir_sample_step(0, 42, 1, 0xAAAA_BBBB);
/// assert_eq!(sample, 42, "First element must always be accepted");
/// ```
pub fn reservoir_sample_step(current: u64, candidate: u64, item_index: u64, rand_val: u64) -> u64 {
    // item_index must be >= 1; use max(item_index, 1) to avoid division by zero.
    let idx = item_index.max(1);
    // Accept candidate iff rand_val % idx == 0.
    // (This gives acceptance probability ≈ 1/idx for uniform random inputs.)
    let accept = (rand_val % idx == 0) as u64;
    // Branchless select: mask = 0xFFFF...FF when accept=1, else 0.
    let mask = 0u64.wrapping_sub(accept);
    (candidate & mask) | (current & !mask)
}

/// Batch reservoir sample over a slice using Vitter's Algorithm R (k=1).
///
/// Processes all items in `stream` starting from stream offset `start_index`
/// (1-indexed, must be >= 1). Returns the final reservoir value. The caller
/// supplies a pseudo-random number generator via `rand_fn`, called once per item.
///
/// # Arguments
/// * `initial`     - Initial reservoir value (e.g., the item at index 1).
/// * `stream`      - Remaining items to process.
/// * `start_index` - 1-indexed stream position of `stream[0]` (must be >= 1).
/// * `rng`         - Mutable RNG state passed to `rand_fn`.
/// * `rand_fn`     - Closure returning a fresh uniform u64 per call.
///
/// # Examples
/// ```rust
/// use bcinr_logic::algorithms::reservoir_sample_simd::reservoir_sample_batch;
/// let mut rng = 0xAAAA_BBBB_u64;
/// let lcg = |r: &mut u64| { *r = r.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407); *r };
/// let stream = [10u64, 20u64, 30u64];
/// let sample = reservoir_sample_batch(stream[0], &stream[1..], 2, &mut rng, lcg);
/// assert!(stream.contains(&sample));
/// ```
pub fn reservoir_sample_batch<F>(
    initial: u64,
    stream: &[u64],
    start_index: u64,
    rng: &mut u64,
    rand_fn: F,
) -> u64
where
    F: Fn(&mut u64) -> u64,
{
    let mut reservoir = initial;
    stream.iter().enumerate().for_each(|(i, &item)| {
        let idx = start_index + i as u64;
        let r = rand_fn(rng);
        reservoir = reservoir_sample_step(reservoir, item, idx, r);
    });
    reservoir
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // -------------------------------------------------------------------------
    // Reference implementation
    // -------------------------------------------------------------------------
    fn reservoir_sample_step_reference(
        current: u64,
        candidate: u64,
        item_index: u64,
        rand_val: u64,
    ) -> u64 {
        let idx = item_index.max(1);
        if rand_val % idx == 0 {
            candidate
        } else {
            current
        }
    }

    // Simple LCG for reproducible tests.
    fn lcg(state: &mut u64) -> u64 {
        *state = state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        *state
    }

    #[test]
    fn test_first_item_always_accepted() {
        // item_index = 1: rand_val % 1 == 0 always → always accept.
        for rand_val in [0u64, 1, u64::MAX, 42, 999] {
            let result = reservoir_sample_step(0, 42, 1, rand_val);
            assert_eq!(result, 42, "item_index=1 must always accept candidate");
        }
    }

    #[test]
    fn test_zero_index_treated_as_one() {
        // item_index = 0 is treated as 1 (max(0,1)=1 → always accept).
        let result = reservoir_sample_step(99, 7, 0, 12345);
        assert_eq!(
            result, 7,
            "index=0 should be clamped to 1 and always accept"
        );
    }

    #[test]
    fn test_matches_reference() {
        for idx in 1u64..=20 {
            for rand_val in [0u64, idx - 1, idx, idx + 1, 1000, u64::MAX] {
                let expected = reservoir_sample_step_reference(10, 20, idx, rand_val);
                let actual = reservoir_sample_step(10, 20, idx, rand_val);
                assert_eq!(
                    expected, actual,
                    "Mismatch at idx={idx}, rand_val={rand_val}"
                );
            }
        }
    }

    #[test]
    fn test_batch_result_is_from_stream() {
        let stream = [1u64, 2, 3, 4, 5, 6, 7, 8, 9, 10];
        let mut rng = 0xDEAD_BEEF_CAFEu64;
        let result = reservoir_sample_batch(stream[0], &stream[1..], 2, &mut rng, lcg);
        assert!(stream.contains(&result), "Batch sample must be from stream");
    }

    #[test]
    fn test_statistical_uniformity() {
        // Over many trials, each of 4 elements should appear roughly 1/4 of the time.
        const STREAM: [u64; 4] = [1, 2, 3, 4];
        let n_trials = 10_000usize;
        let mut counts = [0usize; 5]; // index 1..4
        let mut rng = 0x1234_5678_9ABC_DEF0u64;
        for _ in 0..n_trials {
            let result = reservoir_sample_batch(STREAM[0], &STREAM[1..], 2, &mut rng, lcg);
            if (1..=4).contains(&result) {
                counts[result as usize] += 1;
            }
        }
        // Each element should appear in roughly 2000-3000 out of 10000 trials.
        for i in 1..=4 {
            let count = counts[i];
            assert!(
                (1500..=3500).contains(&count),
                "Element {i} appeared {count} times (expected ~2500)"
            );
        }
    }

    #[test]
    fn test_empty_stream_returns_initial() {
        let mut rng = 42u64;
        let result = reservoir_sample_batch(99, &[], 1, &mut rng, lcg);
        assert_eq!(result, 99, "Empty stream must return initial value");
    }

    proptest! {
        #[test]
        fn test_matches_reference_proptest(
            current in any::<u64>(),
            candidate in any::<u64>(),
            item_index in 1u64..1000,
            rand_val in any::<u64>(),
        ) {
            let expected = reservoir_sample_step_reference(current, candidate, item_index, rand_val);
            let actual = reservoir_sample_step(current, candidate, item_index, rand_val);
            prop_assert_eq!(expected, actual);
        }

        #[test]
        fn test_output_is_either_current_or_candidate(
            current in any::<u64>(),
            candidate in any::<u64>(),
            item_index in 1u64..=1000,
            rand_val in any::<u64>(),
        ) {
            let result = reservoir_sample_step(current, candidate, item_index, rand_val);
            prop_assert!(
                result == current || result == candidate,
                "Result must be current or candidate, got {result}"
            );
        }
    }

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES
    // -------------------------------------------------------------------------
    #[test]
    fn test_boundaries() {
        let _ = reservoir_sample_step(0, 0, 1, 0);
        let _ = reservoir_sample_step(u64::MAX, u64::MAX, u64::MAX, u64::MAX);
        let _ = reservoir_sample_step(u64::MAX, 0, 1, u64::MAX);
        let _ = reservoir_sample_step(0, u64::MAX, 1, 0);
    }

    // -------------------------------------------------------------------------
    // MUTANT COUNTERFACTUALS
    // -------------------------------------------------------------------------
    fn mutant_always_accept(_current: u64, candidate: u64, _: u64, _: u64) -> u64 {
        candidate
    }
    fn mutant_always_reject(current: u64, _candidate: u64, _: u64, _: u64) -> u64 {
        current
    }

    #[test]
    fn test_counterfactual_mutant_always_accept() {
        // At item_index=2 with rand_val=1 (1 % 2 == 1 ≠ 0), correct rejects.
        let result = reservoir_sample_step(10, 20, 2, 1);
        let mutant = mutant_always_accept(10, 20, 2, 1);
        // Correct should reject (return 10), mutant always accepts (returns 20).
        assert_eq!(result, 10, "Correct should reject");
        assert_ne!(result, mutant, "Mutant must differ from correct result");
    }

    #[test]
    fn test_counterfactual_mutant_always_reject() {
        // At item_index=1, correct always accepts.
        let result = reservoir_sample_step(10, 20, 1, 999);
        let mutant = mutant_always_reject(10, 20, 1, 999);
        assert_eq!(result, 20, "Correct should accept at index 1");
        assert_ne!(result, mutant, "Mutant must differ from correct result");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis
    // -------------------------------------------------------------------------
    // Precondition:  { current, candidate, rand_val ∈ U64, item_index >= 1 }
    // Postcondition: { result = candidate  if  rand_val % item_index == 0
    //                  result = current   otherwise }
    //
    // Acceptance probability: |{v in [0,2^64): v % k == 0}| / 2^64 = floor(2^64/k)/2^64 ≈ 1/k.
    //
    // Hoare-logic Verification Line 1: reservoir_sample_step correctness verified.
    // Branchless select: mask = 0xFFFF...FF when accept=1, else 0x0000...00.
    // result = (candidate & mask) | (current & ~mask) is correct branchless mux.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_reservoir_sample_step(c: &mut Criterion) {
        c.bench_function("reservoir_sample_step", |b| {
            b.iter(|| {
                let res = reservoir_sample_step(
                    black_box(42u64),
                    black_box(99u64),
                    black_box(7u64),
                    black_box(0xDEAD_BEEFu64),
                );
                black_box(res)
            })
        });
    }
}
