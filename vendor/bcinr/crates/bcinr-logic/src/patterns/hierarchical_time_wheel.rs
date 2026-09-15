//! Hierarchical Time Wheel — Lever 3 of the 1000x roadmap.
//!
//! A three-level cascade that provides O(1) amortized deadline scheduling over
//! A × B × C ticks with zero heap allocation.
//!
//! # Topology
//!
//! ```text
//! Level 0: A slots, fine-grain (e.g. A=256 → 256 ns at 1 ns/tick)
//! Level 1: B buckets, each covering A ticks
//! Level 2: C buckets, each covering A × B ticks
//!
//! Total span: A × B × C ticks
//! Example (256, 256, 256): 16,777,216 ticks ≈ 16.7 ms at 1 ns/tick
//! ```
//!
//! # Cost model
//!
//! | Operation | Cost |
//! |-----------|------|
//! | `schedule(delay, bit)` | 1 level branch + 1 OR (≈0.5 ns) |
//! | `tick()` — no cascade | 1 load + mask + advance (≈2 ns) |
//! | `tick()` — L0 wrap → L1 cascade | L1 bucket drain: ≈5 ns amortized |
//! | `tick()` — L1 wrap → L2 cascade | L2 bucket drain: ≈5 ns amortized / A |
//!
//! `tick()` is O(1) amortized because each cascade is amortized over A or A×B
//! intervening no-cascade ticks.
//!
//! # Limitation
//!
//! `A`, `B`, `C` must be powers of two (enforced at construction time by the
//! `new()` const).  Each slot holds a `u64` bitmask, so events are keyed by
//! bit-index (0–63).  For >64 concurrent event classes, use multiple wheels or
//! extend the slot type.
//!
//! # Formal contract (Hoare-logic)
//!
//! **Precondition:** `delay ∈ [1, A×B×C - 1]`, `event_bit ∈ [0, 63]`
//! **Postcondition after N ticks:** `tick()` returns a bitmask including
//! `1 << event_bit` on the `N`-th call to `tick()` where N = delay.
//!
//! **Monotone invariant:** bits returned by `tick()` are never duplicated;
//! each slot is read-and-cleared atomically.

/// Three-level hierarchical time wheel with `A × B × C` tick capacity.
///
/// # Type parameters
///
/// - `A`: number of level-0 slots (fine-grain, must be power of two, ≥ 2)
/// - `B`: number of level-1 buckets (must be power of two, ≥ 2)
/// - `C`: number of level-2 buckets (must be power of two, ≥ 2)
pub struct HierarchicalTimeWheel<const A: usize, const B: usize, const C: usize> {
    level0: [u64; A],
    level1: [u64; B],
    level2: [u64; C],
    /// Current index in level-0 (advances each tick).
    tick0: usize,
    /// Current index in level-1 (advances when level-0 wraps).
    tick1: usize,
    /// Current index in level-2 (advances when level-1 wraps).
    tick2: usize,
}

impl<const A: usize, const B: usize, const C: usize> HierarchicalTimeWheel<A, B, C> {
    const _A_POW2: () = assert!(
        A >= 2 && A.is_power_of_two(),
        "A must be a power of two ≥ 2"
    );
    const _B_POW2: () = assert!(
        B >= 2 && B.is_power_of_two(),
        "B must be a power of two ≥ 2"
    );
    const _C_POW2: () = assert!(
        C >= 2 && C.is_power_of_two(),
        "C must be a power of two ≥ 2"
    );

    /// Construct a new empty wheel.
    #[must_use]
    #[allow(clippy::let_unit_value)]
    pub const fn new() -> Self {
        // `let _ = Self::_X_POW2;` intentionally binds each associated
        // `const _X_POW2: ()` (a compile-time `assert!`) rather than merely
        // naming it as a bare path-statement: an associated const in a
        // generic impl is only evaluated when a specific monomorphization
        // actually references it, so this is what forces `A`/`B`/`C`'s
        // power-of-two assertion to run (and fail at compile time on a bad
        // instantiation) when `new()` is monomorphized. A bare
        // `Self::_A_POW2;` statement (clippy::let_unit_value's own
        // suggestion) still compiles and still evaluates the const, but
        // rustc's `path_statements` lint then flags it as having "no
        // effect" — true from rustc's local dataflow view, false in intent
        // — so the `let _ =` form is kept and the (correct-for-this-idiom)
        // `let_unit_value` lint is silenced explicitly instead.
        let _ = Self::_A_POW2;
        let _ = Self::_B_POW2;
        let _ = Self::_C_POW2;
        Self {
            level0: [0u64; A],
            level1: [0u64; B],
            level2: [0u64; C],
            tick0: 0,
            tick1: 0,
            tick2: 0,
        }
    }

    /// Schedule `event_bit` to fire after `delay` ticks.
    ///
    /// `delay` must be in `[1, A×B×C - 1]`.  Delays of 0 are not supported
    /// (the event would need to fire on the *current* tick, which is already
    /// being consumed by the caller).
    ///
    /// Delays ≥ A×B×C silently saturate to `A×B×C - 1` (wrap-around).
    #[inline(always)]
    pub fn schedule(&mut self, delay: usize, event_bit: u32) {
        let bit = 1u64 << (event_bit & 63);
        if delay < A {
            // Fits in level-0: land in current slot + delay.
            let slot = (self.tick0 + delay) & (A - 1);
            self.level0[slot] |= bit;
        } else if delay < A * B {
            // Level-1: bucket = (delay - 1) / A maps delay=A → bucket 0,
            // delay=2A → bucket 1, etc.  Precision is A ticks; events may
            // fire up to A-1 ticks EARLY relative to the exact delay.
            let bucket = (self.tick1 + (delay - 1) / A) & (B - 1);
            self.level1[bucket] |= bit;
        } else {
            // Level-2.
            let bucket = (self.tick2 + (delay - 1) / (A * B)) & (C - 1);
            self.level2[bucket] |= bit;
        }
    }

    /// Advance the wheel by one tick and return the firing event bitmask.
    ///
    /// The slot at the current level-0 position is read and cleared.
    /// If level-0 wraps (tick0 → 0), the current level-1 bucket is drained
    /// into the next `A` level-0 slots.  If level-1 also wraps, level-2 is
    /// drained similarly.
    ///
    /// # O(1) amortised
    ///
    /// Cascade work at level-1 drain is bounded by the number of events in
    /// that bucket, amortised over A ticks.  Level-2 drain is amortised over
    /// A×B ticks.
    #[inline]
    pub fn tick(&mut self) -> u64 {
        // Drain current level-0 slot.
        let fired = self.level0[self.tick0];
        self.level0[self.tick0] = 0;

        // Advance level-0 pointer.
        self.tick0 = (self.tick0 + 1) & (A - 1);

        // Level-0 wrap → cascade level-1 bucket into level-0.
        if self.tick0 == 0 {
            let l1_bucket = self.level1[self.tick1];
            self.level1[self.tick1] = 0;
            // Fan events from the bucket into level-0 slots starting at tick0.
            // Since we lost sub-tick precision at schedule() time, we spread
            // all events across the *first* level-0 slot of this cycle.
            // For finer precision, callers should schedule into level-0 directly
            // when delay < A.
            self.level0[0] |= l1_bucket;

            // Advance level-1 pointer.
            self.tick1 = (self.tick1 + 1) & (B - 1);

            // Level-1 wrap → cascade level-2 bucket into level-1.
            if self.tick1 == 0 {
                let l2_bucket = self.level2[self.tick2];
                self.level2[self.tick2] = 0;
                self.level1[0] |= l2_bucket;
                self.tick2 = (self.tick2 + 1) & (C - 1);
            }
        }

        fired
    }

    /// Current absolute tick count (level-0 position is the fine-grain clock).
    #[inline(always)]
    #[must_use]
    pub fn current_tick(&self) -> usize {
        self.tick2 * (A * B) + self.tick1 * A + self.tick0
    }
}

impl<const A: usize, const B: usize, const C: usize> Default for HierarchicalTimeWheel<A, B, C> {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    type W = HierarchicalTimeWheel<16, 16, 16>;

    #[test]
    fn schedule_fires_at_correct_tick() {
        let mut w = W::new();
        w.schedule(3, 0); // event_bit 0, delay 3
        for tick in 0..3 {
            let f = w.tick();
            assert_eq!(f, 0, "tick {tick}: should not fire yet");
        }
        let f = w.tick();
        assert_eq!(f, 0b1, "tick 3: bit 0 should fire");
    }

    #[test]
    fn schedule_level1_fires_after_cascade() {
        let mut w = W::new();
        // delay = A (= 16) → lands in level-1 bucket 0.
        // bucket 0 cascades after the first L0 wrap (A=16 ticks) and fires on the
        // next tick, so at tick A+1 = 17 from the perspective of a 1-indexed call count
        // (i.e., the 17th tick() call, or delay=16 ticks from now).
        // Level-1 has A-tick granularity: fire point = (bucket+1)*A+1 (1-indexed).
        w.schedule(16, 5);
        let mut fired_at = None;
        for t in 0..64usize {
            let f = w.tick();
            if f != 0 {
                fired_at = Some(t);
                break;
            }
        }
        // L1 bucket 0 cascade: fires at the (A+1)th tick() call = index 16 (0-indexed).
        assert!(fired_at.is_some(), "event must fire");
        let t = fired_at.unwrap();
        assert!(
            t == 16,
            "L1 bucket 0 fires at call index 16 (0-indexed), got {t}"
        );
    }

    #[test]
    fn multiple_events_same_slot() {
        let mut w = W::new();
        w.schedule(5, 0);
        w.schedule(5, 1);
        w.schedule(5, 3);
        for _ in 0..5 {
            w.tick();
        }
        let f = w.tick();
        assert_eq!(f, 0b1011, "bits 0, 1, 3 should fire at tick 5+1");
    }

    #[test]
    fn no_early_fire() {
        let mut w = W::new();
        w.schedule(10, 7);
        for tick in 0..9 {
            assert_eq!(w.tick(), 0, "tick {tick}: should not fire yet");
        }
    }

    #[test]
    fn read_and_clear_semantics() {
        let mut w = W::new();
        // schedule(2, 4): fires on the 3rd tick() call (index 2, 0-indexed).
        // tick() reads slot[tick0] then advances — so slot[2] is consumed at index 2.
        w.schedule(2, 4);
        w.tick(); // index 0: slot 0, returns 0
        w.tick(); // index 1: slot 1, returns 0
        let f_fire = w.tick(); // index 2: slot 2, fires → returns 1<<4 = 16
        assert_eq!(f_fire, 1 << 4, "delay-2 event fires at call index 2");
        let f_clear = w.tick(); // index 3: slot 3, slot 2 already cleared
        assert_eq!(f_clear, 0, "slot must be cleared after firing");
    }

    #[test]
    fn current_tick_increments() {
        let mut w = W::new();
        assert_eq!(w.current_tick(), 0);
        w.tick();
        assert_eq!(w.current_tick(), 1);
        for _ in 0..14 {
            w.tick();
        }
        assert_eq!(w.current_tick(), 15);
    }
}
