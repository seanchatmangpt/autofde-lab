//! BCINR-CMCA-B2: empirical residual classification for
//! `consequence_mass_traced`'s descendant-flow split.
//!
//! Order matters here, and it is fixed by Checkpoint A's lesson: fixture
//! corpus -> trace collection -> residual classification -> candidate law ->
//! hostile falsifier -> promotion. `allocate()`'s "leaves sum to ONE" claim
//! was false in a real, legitimate branch (`hostile_mutants.rs`'s
//! `CORRECT_MU_COST`), found only by building a fixture and reading its
//! actual output. This file exists to do the same thing for
//! `consequence_mass`'s analogous claim before any law is written down.
//!
//! `residual_corpus_summary` is the Phase 3 instrument: it asserts only
//! structural sanity (every fixture admits, every fixture produces at least
//! one step) and prints a `ResidualSummary` under `--nocapture` for the
//! human classification step. It is deliberately not yet a falsifier -- the
//! permanent law tests come after real output is read.

// Exercises `cascade`/`escort`/`reference_escort` (alloc-gated modules): without
// the feature this target compiles to zero tests, keeping the default-feature
// matrix green instead of failing to resolve gated imports.
#![cfg(feature = "alloc")]

use std::collections::BTreeMap;

use bcinr_cmca::cascade::{consequence_mass_traced, AllocationTrace, CascadeTree};
use bcinr_cmca::fixed::NonNegativeFixed;

fn mass(x: f64) -> NonNegativeFixed {
    NonNegativeFixed::from_bits((x * 65536.0).round() as u32)
}

type Fixture = (CascadeTree, Vec<i32>, &'static str);

// ---------------------------------------------------------------------
// Fixture corpus (Phase 2)
// ---------------------------------------------------------------------

/// root -> {a, b, c}, balanced masses.
fn fixture_balanced_positive() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(1.0), mass(1.0), mass(1.0)],
    )
    .unwrap();
    (tree, vec![1], "balanced_positive")
}

/// root -> {a, b, c}, wildly unequal masses.
fn fixture_highly_skewed() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(1000.0), mass(1.0), mass(0.001)],
    )
    .unwrap();
    (tree, vec![1], "highly_skewed")
}

/// root -> {a, b, c}, one child has zero mass (but not all).
fn fixture_zero_containing_siblings() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(2.0), NonNegativeFixed::ZERO, mass(3.0)],
    )
    .unwrap();
    (tree, vec![1], "zero_containing_siblings")
}

/// root -> {a, b}, both children zero mass. Under `lens == 1`, weight = mass,
/// so both weights are zero and this must refuse (`DegenerateSiblingSet`) --
/// covered as its own observation, not force-fit into the trace corpus.
/// Under `lens == 0` (coverage), weight = ONE regardless of mass, so it
/// should NOT refuse -- this is the fixture that actually exercises the
/// all-zero-siblings case inside the trace.
fn fixture_all_zero_siblings() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0)],
        vec![mass(1.0), NonNegativeFixed::ZERO, NonNegativeFixed::ZERO],
    )
    .unwrap();
    (tree, vec![0], "all_zero_siblings_q0")
}

/// root -> {a, b, c}, negative lens (`-1`) over valid positive masses.
fn fixture_negative_lens_positive_masses() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(1.0), mass(2.0), mass(4.0)],
    )
    .unwrap();
    (tree, vec![-1], "negative_lens_positive_masses")
}

fn fixture_q_zero() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(2.0), mass(5.0), mass(9.0)],
    )
    .unwrap();
    (tree, vec![0], "q_zero")
}

fn fixture_q_one() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(2.0), mass(5.0), mass(9.0)],
    )
    .unwrap();
    (tree, vec![1], "q_one")
}

fn fixture_q_two() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(2.0), mass(5.0), mass(9.0)],
    )
    .unwrap();
    (tree, vec![2], "q_two")
}

/// A 5-level chain-of-pairs tree: root -> {a,b}; a -> {a1,a2}; a1 -> {a1x,a1y}.
fn fixture_deep_tree() -> Fixture {
    let tree = CascadeTree::new(
        vec![
            None,    // 0 root
            Some(0), // 1 a
            Some(0), // 2 b
            Some(1), // 3 a1
            Some(1), // 4 a2
            Some(3), // 5 a1x
            Some(3), // 6 a1y
        ],
        vec![
            mass(1.0),
            mass(1.0),
            mass(1.0),
            mass(1.0),
            mass(1.0),
            mass(1.0),
            mass(1.0),
        ],
    )
    .unwrap();
    (tree, vec![1], "deep_tree")
}

/// root -> 9 children, one level, wide fan-out.
fn fixture_wide_tree() -> Fixture {
    let n = 10usize;
    let parent: Vec<Option<usize>> = core::iter::once(None)
        .chain(core::iter::repeat(Some(0)).take(n - 1))
        .collect();
    let m: Vec<NonNegativeFixed> = (0..n).map(|i| mass(1.0 + i as f64)).collect();
    let tree = CascadeTree::new(parent, m).unwrap();
    (tree, vec![1], "wide_tree")
}

/// root -> a -> b -> c (single-child chain, arity 1 at every split).
fn fixture_single_child_chain() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(1), Some(2)],
        vec![mass(1.0), mass(1.0), mass(1.0), mass(1.0)],
    )
    .unwrap();
    (tree, vec![1], "single_child_chain")
}

/// root -> {a, b}; a -> {a1}; leaves at depth 1 (b) and depth 2 (a1) both exist.
fn fixture_mixed_depth() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(1)],
        vec![mass(1.0), mass(1.0), mass(1.0), mass(1.0)],
    )
    .unwrap();
    (tree, vec![1], "mixed_depth")
}

/// root -> {a, b}, smallest representable positive Q16.16 value on one child.
fn fixture_min_positive_fixed_point() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0)],
        vec![mass(1.0), NonNegativeFixed::from_bits(1), mass(1.0)],
    )
    .unwrap();
    (tree, vec![1], "min_positive_fixed_point")
}

/// root -> {a, b}, a large admitted mass on one child (near the top of the
/// range `escort_weight`'s repeated multiplication can carry without
/// overflowing at `MAX_LENS_MAGNITUDE`) alongside a small one.
fn fixture_max_admitted_fixed_point() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0)],
        vec![mass(1.0), mass(60000.0), mass(1.0)],
    )
    .unwrap();
    (tree, vec![1], "max_admitted_fixed_point")
}

/// root -> {a, b, c}, mass ratio 1:3:7 -- none of these splits divide the
/// parent share evenly in Q16.16.
fn fixture_rounding_heavy_split() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(1.0), mass(3.0), mass(7.0)],
    )
    .unwrap();
    (tree, vec![1], "rounding_heavy_split")
}

/// Adapted from `hostile_mutants.rs`'s adversarial shape: masses spanning
/// several orders of magnitude under a higher lens, the kind of input that
/// surfaced `allocate()`'s fallback regime in Checkpoint A.
fn fixture_hostile_mutant_derived() -> Fixture {
    // Masses spanning several orders of magnitude, but kept under ~256 real
    // units so mass^2 (this fixture's lens) stays inside Q16.16's u32 range
    // (escort_weight refuses on overflow rather than wrapping).
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(0.01), mass(1.0), mass(50.0), mass(200.0)],
    )
    .unwrap();
    (tree, vec![2], "hostile_mutant_derived")
}

fn fixture_child_order_permutation_a() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(2.0), mass(5.0), mass(9.0)],
    )
    .unwrap();
    (tree, vec![1], "child_order_permutation_a")
}

/// Same multiset of child masses as `_a`, different construction order.
fn fixture_child_order_permutation_b() -> Fixture {
    let tree = CascadeTree::new(
        vec![None, Some(0), Some(0), Some(0)],
        vec![mass(1.0), mass(9.0), mass(5.0), mass(2.0)],
    )
    .unwrap();
    (tree, vec![1], "child_order_permutation_b")
}

fn all_fixtures() -> Vec<Fixture> {
    vec![
        fixture_balanced_positive(),
        fixture_highly_skewed(),
        fixture_zero_containing_siblings(),
        fixture_all_zero_siblings(),
        fixture_negative_lens_positive_masses(),
        fixture_q_zero(),
        fixture_q_one(),
        fixture_q_two(),
        fixture_deep_tree(),
        fixture_wide_tree(),
        fixture_single_child_chain(),
        fixture_mixed_depth(),
        fixture_min_positive_fixed_point(),
        fixture_max_admitted_fixed_point(),
        fixture_rounding_heavy_split(),
        fixture_hostile_mutant_derived(),
        fixture_child_order_permutation_a(),
        fixture_child_order_permutation_b(),
    ]
}

// ---------------------------------------------------------------------
// Analysis (Phase 3)
// ---------------------------------------------------------------------

#[derive(Clone, Debug)]
struct ResidualObservation {
    fixture: &'static str,
    node: usize,
    parent: Option<usize>,
    wave: usize,
    child_count: usize,
    input_share_bits: u32,
    child_sum_bits: u32,
    residual_bits: i64,
    any_zero_mass_child: bool,
    all_zero_mass_children: bool,
    exactly_divisible: bool,
}

fn observe(fixture: &'static str, trace: &AllocationTrace) -> Vec<ResidualObservation> {
    trace
        .steps
        .iter()
        .map(|step| {
            let zero_children = step
                .child_shares
                .iter()
                .filter(|(_, share)| share.to_bits() == 0)
                .count();
            ResidualObservation {
                fixture,
                node: step.node,
                parent: step.parent,
                wave: step.wave,
                child_count: step.child_shares.len(),
                input_share_bits: step.input_share.to_bits(),
                child_sum_bits: step.child_sum.to_bits(),
                residual_bits: step.residual_bits,
                any_zero_mass_child: zero_children > 0,
                all_zero_mass_children: zero_children == step.child_shares.len()
                    && !step.child_shares.is_empty(),
                exactly_divisible: step.child_shares.is_empty()
                    || step.input_share.to_bits() % step.child_shares.len() as u32 == 0,
            }
        })
        .collect()
}

/// Fields are read only through the `Debug` derive (`eprintln!("{summary:#?}")`
/// in `residual_corpus_summary`), which the dead-code lint doesn't count as a
/// read.
#[derive(Debug)]
#[allow(dead_code)]
struct ResidualSummary {
    total_steps: usize,
    zero: usize,
    positive: usize,
    negative: usize,
    min: i64,
    max: i64,
    max_abs: i64,
    by_lens: BTreeMap<i32, Vec<i64>>,
    by_arity: BTreeMap<usize, Vec<i64>>,
    by_depth: BTreeMap<usize, Vec<i64>>,
    by_zero_pattern: BTreeMap<&'static str, Vec<i64>>,
    by_divisibility: BTreeMap<bool, Vec<i64>>,
    extremal_fixtures: Vec<&'static str>,
}

fn summarize(observations: &[(ResidualObservation, i32)]) -> ResidualSummary {
    let mut zero = 0;
    let mut positive = 0;
    let mut negative = 0;
    let mut min = i64::MAX;
    let mut max = i64::MIN;
    let mut by_lens: BTreeMap<i32, Vec<i64>> = BTreeMap::new();
    let mut by_arity: BTreeMap<usize, Vec<i64>> = BTreeMap::new();
    let mut by_depth: BTreeMap<usize, Vec<i64>> = BTreeMap::new();
    let mut by_zero_pattern: BTreeMap<&'static str, Vec<i64>> = BTreeMap::new();
    let mut by_divisibility: BTreeMap<bool, Vec<i64>> = BTreeMap::new();

    for (obs, lens) in observations {
        let r = obs.residual_bits;
        match r.cmp(&0) {
            core::cmp::Ordering::Equal => zero += 1,
            core::cmp::Ordering::Greater => positive += 1,
            core::cmp::Ordering::Less => negative += 1,
        }
        min = min.min(r);
        max = max.max(r);
        by_lens.entry(*lens).or_default().push(r);
        by_arity.entry(obs.child_count).or_default().push(r);
        by_depth.entry(obs.wave).or_default().push(r);
        let pattern = if obs.all_zero_mass_children {
            "all"
        } else if obs.any_zero_mass_child {
            "some"
        } else {
            "none"
        };
        by_zero_pattern.entry(pattern).or_default().push(r);
        by_divisibility
            .entry(obs.exactly_divisible)
            .or_default()
            .push(r);
    }

    let max_abs = min.unsigned_abs().max(max.unsigned_abs()) as i64;
    let extremal_fixtures: Vec<&'static str> = observations
        .iter()
        .filter(|(obs, _)| obs.residual_bits == min || obs.residual_bits == max)
        .map(|(obs, _)| obs.fixture)
        .collect();

    ResidualSummary {
        total_steps: observations.len(),
        zero,
        positive,
        negative,
        min,
        max,
        max_abs,
        by_lens,
        by_arity,
        by_depth,
        by_zero_pattern,
        by_divisibility,
        extremal_fixtures,
    }
}

/// Synthetic fixtures at arities the 18 named ones don't reach (up to 20),
/// with intentionally awkward mass ratios (consecutive primes) chosen to
/// resist clean division. Phase 4/5 stress corpus, not named individually --
/// existence and arity are what matters here.
fn stress_fixtures() -> Vec<Fixture> {
    // First 20 primes: no ratio between any two divides evenly, maximizing
    // the chance of a "bad" residual at each arity.
    const PRIMES: [f64; 20] = [
        2.0, 3.0, 5.0, 7.0, 11.0, 13.0, 17.0, 19.0, 23.0, 29.0, 31.0, 37.0, 41.0, 43.0, 47.0, 53.0,
        59.0, 61.0, 67.0, 71.0,
    ];
    (2..=20usize)
        .map(|arity| {
            let parent: Vec<Option<usize>> = core::iter::once(None)
                .chain(core::iter::repeat(Some(0)).take(arity))
                .collect();
            let m: Vec<NonNegativeFixed> = core::iter::once(mass(1.0))
                .chain(PRIMES[..arity].iter().map(|&p| mass(p)))
                .collect();
            let tree = CascadeTree::new(parent, m).unwrap();
            (tree, vec![1i32], "stress_prime_ratio")
        })
        .collect()
}

/// Phase 4/5: much larger sample (arities 2..=20, adversarial mass ratios)
/// to test both the derived non-negativity law and a candidate arity-scaled
/// upper bound before promoting either as a permanent test.
#[test]
fn stress_corpus_bounds_check() {
    let mut max_residual_by_arity: BTreeMap<usize, i64> = BTreeMap::new();
    let mut any_negative = false;

    for (tree, lenses, name) in stress_fixtures() {
        let trace = consequence_mass_traced(&tree, &lenses)
            .unwrap_or_else(|e| panic!("stress fixture unexpectedly refused: {e:?} ({name})"));
        for step in &trace.steps {
            if step.residual_bits < 0 {
                any_negative = true;
            }
            let arity = step.child_shares.len();
            let entry = max_residual_by_arity.entry(arity).or_insert(i64::MIN);
            *entry = (*entry).max(step.residual_bits);
        }
    }

    eprintln!("stress max residual by arity: {max_residual_by_arity:#?}");
    assert!(
        !any_negative,
        "stress corpus found a negative residual -- the non-negativity derivation is wrong"
    );
    for (&arity, &observed_max) in &max_residual_by_arity {
        // Conservative envelope, not a tight bound: two truncating operations
        // per child (the share division, then the descendant_part
        // multiplication), so at most just-under-1-ULP loss at each of two
        // points per child -- `2 * arity` is a safe, operation-count-derived
        // ceiling, not `observed_max + margin`.
        let conservative_bound = 2 * arity as i64;
        assert!(
            observed_max <= conservative_bound,
            "arity {arity}: observed max residual {observed_max} exceeds the \
             2-truncations-per-child conservative bound {conservative_bound}"
        );
    }
}

#[test]
fn residual_corpus_summary() {
    let mut observations: Vec<(ResidualObservation, i32)> = Vec::new();

    for (tree, lenses, name) in all_fixtures() {
        let trace = consequence_mass_traced(&tree, &lenses)
            .unwrap_or_else(|e| panic!("fixture {name:?} unexpectedly refused: {e:?}"));
        assert!(
            !trace.leaves.is_empty(),
            "fixture {name:?} produced no leaves"
        );
        let lens_for = |wave: usize| -> i32 {
            if lenses.is_empty() {
                0
            } else {
                lenses[wave.min(lenses.len() - 1)]
            }
        };
        for obs in observe(name, &trace) {
            let lens = lens_for(obs.wave);
            observations.push((obs, lens));
        }
    }

    assert!(
        !observations.is_empty(),
        "corpus produced zero internal-node observations -- every fixture was a single leaf"
    );

    let summary = summarize(&observations);
    eprintln!("{summary:#?}");

    // Print each raw observation too -- the summary buckets lose per-step
    // detail needed for Phase 4's classification (e.g. "is residual sign
    // correlated with arity AND zero-pattern simultaneously").
    for (obs, lens) in &observations {
        eprintln!(
            "fixture={:<28} node={:<2} parent={:?} wave={} lens={:>3} arity={} input={:>10} child_sum={:>10} residual={:>6} zero_pattern={} exactly_divisible={}",
            obs.fixture,
            obs.node,
            obs.parent,
            obs.wave,
            lens,
            obs.child_count,
            obs.input_share_bits,
            obs.child_sum_bits,
            obs.residual_bits,
            if obs.all_zero_mass_children { "all" } else if obs.any_zero_mass_child { "some" } else { "none" },
            obs.exactly_divisible,
        );
    }
}
