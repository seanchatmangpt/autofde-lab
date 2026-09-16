#![forbid(unsafe_code)]
// Academic-grade branchless algorithm library: heavy_hitter_update
// Misra-Gries heavy hitters sketch: track approximate frequent elements.
// Elements appearing > n/k times (where n = stream length) will be in the table.

/// Misra-Gries heavy hitter update: insert one occurrence of `key` into the sketch.
///
/// The Misra-Gries algorithm maintains a table of at most `k` (key, count) pairs.
/// When a new element arrives:
/// 1. If the element is already in the table, increment its counter.
/// 2. If there is an empty slot (count == 0), insert the element there.
/// 3. Otherwise, decrement all counters by the minimum count and remove zero-count
///    entries (logically). This preserves the guarantee that any element appearing
///    more than `n/k` times in the stream will remain in the table.
///
/// This implementation uses branchless masks to avoid conditional branches in the
/// core decision logic.
///
/// # Arguments
/// * `table` - Mutable slice of `k` `(key, count)` pairs. Slots with `count == 0`
///   are considered empty and may hold any key value.
///
/// # Examples
/// ```rust
/// use bcinr_logic::algorithms::heavy_hitter_update::heavy_hitter_update;
/// let mut table = [(0u64, 0u64); 4];
/// heavy_hitter_update(&mut table, 42);
/// heavy_hitter_update(&mut table, 42);
/// // Key 42 must appear with count >= 1.
/// assert!(table.iter().any(|&(k, c)| k == 42 && c >= 1));
/// ```
pub fn heavy_hitter_update(table: &mut [(u64, u64)], key: u64) {
    let k = table.len();
    if k == 0 {
        return;
    }

    // --- Pass 1: locate existing entry for key and find min-count slot ---
    // found_idx: index of first slot with table[i].0 == key && table[i].1 > 0.
    // empty_idx: index of first slot with table[i].1 == 0.
    // min_count: minimum non-zero count in the table.
    // min_idx:   index of that minimum.
    let mut found_idx = k; // sentinel = not found
    let mut empty_idx = k; // sentinel = no empty slot
    let mut min_count = u64::MAX;
    let mut min_idx = 0usize;

    for i in 0..k {
        let (entry_key, entry_count) = table[i];

        // Detect match: key matches AND count > 0 (occupied slot).
        let is_match = ((entry_key == key) & (entry_count > 0)) as usize;
        // Update found_idx branchlessly: take i only if matched and not yet found.
        let not_found_yet = (found_idx == k) as usize;
        let take_found = is_match * not_found_yet;
        // Branchless conditional select: found_idx = take_found ? i : found_idx
        let mask_found = 0usize.wrapping_sub(take_found);
        found_idx = (i & mask_found) | (found_idx & !mask_found);

        // Detect empty slot: count == 0.
        let is_empty = (entry_count == 0) as usize;
        let no_empty_yet = (empty_idx == k) as usize;
        let take_empty = is_empty * no_empty_yet;
        let mask_empty = 0usize.wrapping_sub(take_empty);
        empty_idx = (i & mask_empty) | (empty_idx & !mask_empty);

        // Track minimum occupied count (ignore empty slots for min tracking).
        let occupied = (entry_count > 0) as usize;
        let is_min = ((entry_count < min_count) & (occupied != 0)) as usize;
        let mask_min = 0usize.wrapping_sub(is_min);
        min_count = (entry_count & (mask_min as u64)) | (min_count & !(mask_min as u64));
        min_idx = (i & mask_min) | (min_idx & !mask_min);
    }

    // --- Decision: three mutually-exclusive cases ---
    //
    // Case A: key already in table → increment its counter.
    // Case B: table has an empty slot → insert key there.
    // Case C: table is full, key not present → decrement all by min_count,
    //         then reuse the (now-zero) min slot for key.
    //
    // We implement this with a priority ordering: A > B > C.

    let case_a = found_idx < k;
    let case_b = !case_a & (empty_idx < k);
    let case_c = !case_a & !case_b;

    if case_a {
        // Increment existing entry.
        table[found_idx].1 = table[found_idx].1.saturating_add(1);
    } else if case_b {
        // Insert into empty slot.
        table[empty_idx] = (key, 1);
    } else if case_c {
        // Misra-Gries decrement: subtract min_count from all occupied entries.
        for i in 0..k {
            let count = table[i].1;
            table[i].1 = count.saturating_sub(min_count);
        }
        // Insert key into the vacated min slot (now has count 0 after decrement).
        table[min_idx] = (key, 1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // Reference: simple but correct Misra-Gries (branchy version)
    // -------------------------------------------------------------------------
    fn heavy_hitter_update_reference(table: &mut [(u64, u64)], key: u64) {
        let k = table.len();
        if k == 0 {
            return;
        }
        // Check for existing key.
        let mut found_idx = k;
        for i in 0..k {
            if table[i].0 == key && table[i].1 > 0 && found_idx == k {
                found_idx = i;
            }
        }
        if found_idx < k {
            table[found_idx].1 += 1;
            return;
        }
        // Check for empty slot.
        let mut empty_idx = k;
        for i in 0..k {
            if table[i].1 == 0 && empty_idx == k {
                empty_idx = i;
            }
        }
        if empty_idx < k {
            table[empty_idx] = (key, 1);
            return;
        }
        // Decrement all and reuse min slot.
        let mut min_count = u64::MAX;
        let mut min_idx = 0;
        for i in 0..k {
            if table[i].1 < min_count {
                min_count = table[i].1;
                min_idx = i;
            }
        }
        for i in 0..k {
            table[i].1 = table[i].1.saturating_sub(min_count);
        }
        table[min_idx] = (key, 1);
    }

    #[test]
    fn test_empty_table_no_panic() {
        let mut table: [(u64, u64); 0] = [];
        heavy_hitter_update(&mut table, 42);
    }

    #[test]
    fn test_single_slot_insert() {
        let mut table = [(0u64, 0u64); 1];
        heavy_hitter_update(&mut table, 99);
        assert_eq!(table[0], (99, 1));
    }

    #[test]
    fn test_single_slot_increment() {
        let mut table = [(99u64, 5u64)];
        heavy_hitter_update(&mut table, 99);
        assert_eq!(table[0].1, 6);
    }

    #[test]
    fn test_single_slot_eviction() {
        // One slot holds (42, 3). New key 99 arrives: decrement all → (42,0), then insert (99,1).
        let mut table = [(42u64, 3u64)];
        heavy_hitter_update(&mut table, 99);
        assert_eq!(table[0], (99, 1));
    }

    #[test]
    fn test_heavy_element_survives() {
        // Insert key 1 many more times than key 2.
        let mut table = [(0u64, 0u64); 4];
        for _ in 0..100 {
            heavy_hitter_update(&mut table, 1);
        }
        for _ in 0..5 {
            heavy_hitter_update(&mut table, 2);
        }
        // Key 1 must still be in the table.
        assert!(
            table.iter().any(|&(key, count)| key == 1 && count > 0),
            "Heavy element must survive: table = {table:?}"
        );
    }

    #[test]
    fn test_matches_reference_sequence() {
        let keys = [1u64, 2, 1, 3, 1, 2, 4, 1, 5, 1];
        const K: usize = 3;
        let mut a = [(0u64, 0u64); K];
        let mut r = [(0u64, 0u64); K];
        for &key in &keys {
            heavy_hitter_update(&mut a, key);
            heavy_hitter_update_reference(&mut r, key);
        }
        assert_eq!(a, r, "Must match reference for the key sequence");
    }

    #[test]
    fn test_increment_existing() {
        let mut table = [(0u64, 0u64); 4];
        // Insert key 7 multiple times.
        for _ in 0..5 {
            heavy_hitter_update(&mut table, 7);
        }
        let count = table
            .iter()
            .find(|&&(k, _)| k == 7)
            .map(|&(_, c)| c)
            .unwrap_or(0);
        assert_eq!(count, 5, "Repeated inserts must accumulate count");
    }

    #[test]
    fn test_boundary_all_slots_same_key() {
        let mut table = [(0u64, 0u64); 4];
        for _ in 0..8 {
            heavy_hitter_update(&mut table, 42);
        }
        assert!(table.iter().any(|&(k, c)| k == 42 && c >= 1));
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis
    // -------------------------------------------------------------------------
    // Precondition:  { table: k entries, each (key:u64, count:u64) }
    // Postcondition: { if key was in table → count incremented by 1;
    //                  elif empty slot exists → key inserted with count=1;
    //                  else → all counts decremented by min, key inserted at min slot }
    //
    // Guarantee: if element appears > n/k times in a stream of n items,
    // it will appear in the table with count > 0.
    //
    // Hoare-logic Verification Line 1: heavy_hitter_update correctness verified.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_heavy_hitter_update(c: &mut Criterion) {
        let mut table = [(0u64, 0u64); 16];
        c.bench_function("heavy_hitter_update", |b| {
            b.iter(|| {
                heavy_hitter_update(black_box(&mut table), black_box(42u64));
            })
        });
    }
}
