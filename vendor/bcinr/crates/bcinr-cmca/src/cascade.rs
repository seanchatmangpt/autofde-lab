//! Arbitrary-arity, arbitrary-depth multifractal consequence cascade.
//!
//! # Why this exists alongside [`crate::allocator`]
//!
//! [`crate::allocator::allocate`] is the *certified* cascade: branchless
//! ($CC=1$), allocation-free, side-channel resilient -- and, as the price of
//! those properties, hard-bounded to `N = 8` nodes and depth `<= 8`
//! (`parent[x & 7]`, eight literal `flow_step` calls) with a single scalar `q`
//! applied identically at every level. Those bounds are not a defect of that
//! function; they are what make it constant-time. Widening it would destroy
//! the property that justifies it.
//!
//! This module is the *analysis* cascade: it allocates, it branches, and in
//! exchange it takes a tree of any shape and a **lens per level**. It is meant
//! for structural allocation over a real hierarchy (e.g. a POWL 2.0 process
//! tree, whose depth and arity are set by the process, not by a register
//! width), not for a hot control loop. Both compute the same measure; pick by
//! whether you need the constant-time guarantee or the unbounded shape.
//!
//! # The measure
//!
//! At each parent `p` with children `c_1..c_k`, the local *escort*
//! distribution at lens `q` is
//!
//! ```text
//!   L_q(c_i | p) = m(c_i)^q / SUM_j m(c_j)^q
//! ```
//!
//! and a node's consequence mass is the product down its root path:
//!
//! ```text
//!   pi(v) = PRODUCT over edges (p -> c) on root..v of L_q(c | p)
//! ```
//!
//! This is a multiplicative cascade of escort measures -- the standard
//! multifractal construction. What makes it genuinely *multi*fractal rather
//! than one global exponent is that `q` is read **per depth**: `lenses[d]`
//! applies to nodes at depth `d`. A single-element `lenses` slice reproduces
//! the monofractal, one-exponent behaviour of the certified path.
//!
//! # Determinism
//!
//! Lenses are integers, and `m^q` is computed by repeated `saturating_mul`
//! (and one `saturating_div` for negative `q`) over Q16.16
//! `NonNegativeFixed` -- no `powf`, no libm, no floating point anywhere. The
//! result is bit-identical on every platform, exactly as the certified path
//! is. Integer lenses are not a restriction in practice: the lens vocabulary
//! this crate is built around (exploitation `2`, proportional `1`, coverage
//! `0`, rare `-1`) is already integral.

extern crate alloc;

use alloc::vec;
use alloc::vec::Vec;

use crate::fixed::NonNegativeFixed;

/// Largest `|q|` a lens may take. Bounds the repeated-multiplication loop in
/// [`escort_weight`]; `2` (exploitation) through `-1` (rare) sit far inside it.
///
/// Derived from [`crate::generated_profile::MAX_LENS_MAGNITUDE`] -- the
/// ontology-declared policy constant -- rather than duplicated as a literal,
/// so regenerating the profile from the graph cannot leave this copy stale.
/// The allocator (always compiled; this module is `alloc`-gated) references
/// the generated original directly.
pub const MAX_LENS_MAGNITUDE: u32 = crate::generated_profile::MAX_LENS_MAGNITUDE;

/// A tree of masses to cascade over. `parent[i]` is `None` for a root.
///
/// Multiple roots are allowed: they are treated as one sibling group and
/// normalized against each other, matching `allocator`'s own `root_w_sum`
/// handling.
///
/// `rho[v]` splits an internal node's flow between the two paths of the
/// measure (see [`consequence_mass`]): `ONE` is pure descendant (flow reaches
/// leaves only by passing through every intervening level), `ZERO` is pure
/// flat (flow lands directly on the subtree's leaves, skipping the levels
/// between). [`CascadeTree::new`] pins `rho = ONE` for every node;
/// [`CascadeTree::with_rho`] takes it per node.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CascadeTree {
    parent: Vec<Option<usize>>,
    mass: Vec<NonNegativeFixed>,
    rho: Vec<NonNegativeFixed>,
}

/// Typed refusal from the cascade. Every variant is a real condition under
/// which no correct answer exists -- none is a silent degradation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CascadeRefusal {
    /// `parent` and `mass` describe different numbers of nodes.
    LengthMismatch { parents: usize, masses: usize },
    /// `parent[node]` names a node index that does not exist.
    ParentOutOfRange {
        node: usize,
        parent: usize,
        len: usize,
    },
    /// Walking `node` toward a root exceeded the node count, so the `parent`
    /// relation contains a cycle. The `N`-generic counterpart of
    /// [`crate::allocator::check_hierarchy_acyclic`]'s bounded ancestor
    /// doubling.
    Cyclic { node: usize },
    /// A non-empty tree in which every node has a parent -- no root to start
    /// the cascade from. Implied by `Cyclic` in most cases but reported
    /// distinctly when the tree is small enough to have no cycle witness.
    NoRoot,
    /// A lens exceeded [`MAX_LENS_MAGNITUDE`].
    ExponentOutOfRange { lens: i32, max_magnitude: u32 },
    /// A sibling group's escort weights all came out zero, so the local
    /// distribution `w_i / SUM w_j` has no denominator. Refused rather than
    /// guarded to `ONE`, which is exactly the silent-degradation failure the
    /// cyclic-parent bug in `allocator` used to have.
    DegenerateSiblingSet { parent: Option<usize> },
    /// The escort weights over a node's *subtree leaves* all came out zero
    /// while that node has a non-zero flat part (`rho < ONE`), so the flat
    /// path has no denominator. Only reachable when the flat path actually
    /// carries mass -- a degenerate leaf set under `rho == ONE` is harmless
    /// and is not refused.
    DegenerateSubtreeLeaves { node: usize },
    /// A zero-mass node under a negative lens. `0^q` for `q < 0` is
    /// unbounded, so its escort weight is undefined -- there is no correct
    /// finite answer, and saturating to `MAX` would silently make a
    /// zero-mass node dominate every sibling.
    ZeroMassUnderNegativeLens { node: usize, lens: i32 },
    /// A Q16.16 operation saturated or divided by zero, so the value carried
    /// forward is not the value the mathematics calls for.
    ///
    /// `NonNegativeFixed` computes this: `saturating_mul` and friends set
    /// `err` to a `StabilityRefusal` discriminant and leave it `u32::MAX` when
    /// clean. Every arithmetic stage in this module now consumes that channel
    /// through [`admit_fixed`] rather than taking `.to_bits()` and dropping it,
    /// because an error that exists inside a value but never reaches the
    /// `Result` is indistinguishable from a correct answer.
    ///
    /// Note this module has no max-shift stabilisation: `m^q` is materialised
    /// by repeated multiplication, so overflow is genuinely reachable here.
    /// (The certified allocator *does* max-shift, which makes overflow
    /// structurally impossible and routine underflow benign -- the two modules
    /// need different treatment for that reason.)
    NumericFault {
        operation: NumericContext,
        node: usize,
        error_code: u32,
    },
    /// `m^q` collapsed to zero from a non-zero mass: the value is not
    /// negligible, it is unrepresentable at this precision.
    ///
    /// `saturating_mul` flags overflow but NOT underflow, so this cannot be
    /// read off the error channel and is detected structurally. Distinguishing
    /// it matters: a true zero mass is a fact about the input, whereas a mass
    /// that *became* zero is a fact about Q16.16, and only the second is a
    /// representability failure.
    EscortUnderflow {
        node: usize,
        lens: i32,
        mass_bits: u32,
    },
}

/// Where in the cascade an arithmetic fault arose.
///
/// Carried on [`CascadeRefusal::NumericFault`] so a refusal names the stage
/// that could not be represented, not merely that something overflowed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NumericContext {
    /// `m^q` by repeated multiplication.
    EscortWeight { lens: i32 },
    /// `1 / m^|q|` for a negative lens.
    EscortReciprocal { lens: i32 },
    /// Summing a sibling group's escort weights.
    SiblingSum,
    /// Summing a subtree's leaf escort weights.
    SubtreeLeafSum,
    /// `w_i / SUM w_j`.
    ShareDivision,
    /// `rho * flow`.
    DescendantSplit,
    /// `(1 - rho) * flow`.
    FlatSplit,
    /// Accumulating flow into a child.
    FlowAccumulation,
    /// Accumulating the flat path into a subtree leaf.
    FlatAccumulation,
    /// `flow + flat` at a node.
    FinalAccumulation,
}

/// Admit a fixed-point value only if the operation that produced it was
/// exact, converting the value-internal error channel into a typed refusal.
///
/// This is the single choke point the module routes every arithmetic result
/// through. `NonNegativeFixed::err` is `u32::MAX` when clean and a
/// `StabilityRefusal` discriminant otherwise.
#[inline]
pub fn admit_fixed(
    value: NonNegativeFixed,
    operation: NumericContext,
    node: usize,
) -> Result<NonNegativeFixed, CascadeRefusal> {
    if value.err == u32::MAX {
        return Ok(value);
    }
    Err(CascadeRefusal::NumericFault {
        operation,
        node,
        error_code: value.err,
    })
}

impl CascadeTree {
    /// Build a tree with `rho = ONE` everywhere -- the pure descendant
    /// cascade, in which flow reaches a leaf only by passing through every
    /// intervening level. Validates index ranges and length agreement;
    /// acyclicity is checked later, by [`consequence_mass`], where the depth
    /// walk that would detect it happens anyway.
    pub fn new(
        parent: Vec<Option<usize>>,
        mass: Vec<NonNegativeFixed>,
    ) -> Result<Self, CascadeRefusal> {
        let rho = vec![NonNegativeFixed::ONE; parent.len()];
        Self::with_rho(parent, mass, rho)
    }

    /// Build a tree with an explicit per-node `rho`, the general two-path
    /// measure. See [`consequence_mass`] for what the two paths are.
    pub fn with_rho(
        parent: Vec<Option<usize>>,
        mass: Vec<NonNegativeFixed>,
        rho: Vec<NonNegativeFixed>,
    ) -> Result<Self, CascadeRefusal> {
        if parent.len() != mass.len() {
            return Err(CascadeRefusal::LengthMismatch {
                parents: parent.len(),
                masses: mass.len(),
            });
        }
        if parent.len() != rho.len() {
            return Err(CascadeRefusal::LengthMismatch {
                parents: parent.len(),
                masses: rho.len(),
            });
        }
        let len = parent.len();
        for (node, slot) in parent.iter().enumerate() {
            if let Some(p) = slot {
                if *p >= len {
                    return Err(CascadeRefusal::ParentOutOfRange {
                        node,
                        parent: *p,
                        len,
                    });
                }
            }
        }
        Ok(Self { parent, mass, rho })
    }

    #[must_use]
    pub fn rho(&self) -> &[NonNegativeFixed] {
        &self.rho
    }

    #[must_use]
    pub fn len(&self) -> usize {
        self.parent.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.parent.is_empty()
    }

    #[must_use]
    pub fn parent(&self) -> &[Option<usize>] {
        &self.parent
    }

    #[must_use]
    pub fn mass(&self) -> &[NonNegativeFixed] {
        &self.mass
    }
}

/// `m^q` in Q16.16, by repeated multiplication -- no `powf`, no libm. Shared
/// by [`escort_weight`] and [`escort_weight_support`] for every `lens != 0`,
/// where the two conventions coincide (see both functions' docs for why
/// `lens == 0` is the one case they must differ on).
fn escort_power(
    mass: NonNegativeFixed,
    lens: i32,
    node: usize,
) -> Result<NonNegativeFixed, CascadeRefusal> {
    let magnitude = lens.unsigned_abs();
    if magnitude > MAX_LENS_MAGNITUDE {
        return Err(CascadeRefusal::ExponentOutOfRange {
            lens,
            max_magnitude: MAX_LENS_MAGNITUDE,
        });
    }
    debug_assert_ne!(
        lens, 0,
        "escort_power is only for lens != 0; callers handle lens == 0 themselves"
    );
    let mut accumulated = NonNegativeFixed::ONE;
    for _ in 0..magnitude {
        accumulated = accumulated.saturating_mul(mass);
    }
    let accumulated = admit_fixed(accumulated, NumericContext::EscortWeight { lens }, node)?;
    if accumulated.to_bits() == 0 && mass.to_bits() != 0 {
        return Err(CascadeRefusal::EscortUnderflow {
            node,
            lens,
            mass_bits: mass.to_bits(),
        });
    }
    if lens > 0 {
        return Ok(accumulated);
    }
    if accumulated.to_bits() == 0 {
        return Err(CascadeRefusal::ZeroMassUnderNegativeLens { node, lens });
    }
    admit_fixed(
        NonNegativeFixed::ONE.saturating_div(accumulated),
        NumericContext::EscortReciprocal { lens },
        node,
    )
}

/// `m^q` in Q16.16, by repeated multiplication -- no `powf`, no libm.
///
/// `q == 0` is `ONE` for any mass (including zero: the *sibling coverage*
/// convention weights every sibling equally by construction, whether or not
/// it carries mass). This is the convention this crate's production call
/// site (`consequence_mass`) actually uses at `q == 0`, and is now the same
/// convention [`uniform_sibling_weight`] implements directly -- this
/// function keeps its historical name and signature for API compatibility
/// (`escort.rs`'s exact-lens dispatch and existing correspondence tests call
/// it by name), but for `lens == 0` it now delegates to
/// [`uniform_sibling_weight`], and for `lens != 0` to the shared
/// `escort_power` helper, rather than duplicating either.
///
/// See [`escort_weight_support`] for the other convention (*support
/// coverage*: zero mass gets zero weight at `q == 0`, excluding it from the
/// uniform measure instead of including it) -- the two differ only at
/// `lens == 0`; see `escort.rs`'s module docs for the Lean ancestry of this
/// distinction (`ReferenceLens.coverage` vs `uniformSiblingCoverage`).
pub fn escort_weight(
    mass: NonNegativeFixed,
    lens: i32,
    node: usize,
) -> Result<NonNegativeFixed, CascadeRefusal> {
    if lens == 0 {
        // MAX_LENS_MAGNITUDE is a `u32`, so `lens.unsigned_abs() == 0 <=
        // MAX_LENS_MAGNITUDE` always holds -- no domain check needed here.
        return Ok(uniform_sibling_weight(mass, node));
    }
    escort_power(mass, lens, node)
}

/// The *sibling coverage* per-node escort weight: `ONE` for every sibling at
/// `q == 0`, regardless of mass. Only meaningful at `lens == 0` -- callers
/// choosing between coverage conventions call this directly instead of
/// `escort_weight(mass, 0, node)` to make that choice visible at the call
/// site (see `consequence_mass`'s use below).
///
/// This is "1/n" in the sense that follows from how the caller uses it, not
/// from anything this function computes on its own: `consequence_mass`
/// normalizes every sibling's weight by their sum, and `n` equal `ONE`
/// weights normalize to `ONE / n` each. This function has no way to know
/// `n` (it sees one node at a time) and does not attempt to -- it commits
/// only to "every sibling gets the same weight," which is the part of
/// "1/n always" that is actually this function's job.
#[must_use]
pub fn uniform_sibling_weight(_mass: NonNegativeFixed, _node: usize) -> NonNegativeFixed {
    NonNegativeFixed::ONE
}

/// The *support coverage* per-node escort weight: `m^q` in Q16.16, with
/// `q == 0` returning `ZERO` for a zero mass (excluded from the uniform
/// measure) and `ONE` otherwise, rather than `ONE` unconditionally.
///
/// For `lens != 0` this is identical to [`escort_weight`] -- `m^q` is
/// already zero for a zero mass under a positive lens, and a zero mass
/// under a negative lens refuses the same way in both (there is no
/// coverage question once the lens itself is nonzero; the ambiguity is
/// specific to `q == 0`, where "which siblings does the uniform measure
/// range over" is a real, currently-uncertified modeling choice -- see
/// `escort.rs`'s module docs, `ReferenceLens.coverage`).
///
/// No production call site in this crate currently selects support
/// coverage; it is exposed so a caller that needs it does not have to
/// duplicate `escort_power` to get it.
pub fn escort_weight_support(
    mass: NonNegativeFixed,
    lens: i32,
    node: usize,
) -> Result<NonNegativeFixed, CascadeRefusal> {
    if lens == 0 {
        if mass.to_bits() == 0 {
            return Ok(NonNegativeFixed::ZERO);
        }
        return Ok(NonNegativeFixed::ONE);
    }
    escort_power(mass, lens, node)
}

/// Depth of every node (roots at depth 0), refusing on a cyclic `parent`.
///
/// Walks each node toward a root, capping the walk at the node count: a
/// well-formed forest reaches a root within `len` hops from any node, so
/// exceeding that is exactly a cycle witness.
fn depths(tree: &CascadeTree) -> Result<Vec<usize>, CascadeRefusal> {
    let len = tree.len();
    let mut depth = vec![0usize; len];
    for (node, slot) in depth.iter_mut().enumerate() {
        let mut steps = 0usize;
        let mut cursor = node;
        while let Some(p) = tree.parent[cursor] {
            steps += 1;
            if steps > len {
                return Err(CascadeRefusal::Cyclic { node });
            }
            cursor = p;
        }
        *slot = steps;
    }
    Ok(depth)
}

/// Consequence mass for every node, under a lens per level and the two-path
/// flow split.
///
/// # The two paths
///
/// At an internal node `v` carrying flow `f`, the measure splits:
///
/// ```text
///   descendant part = rho[v] * f
///       -> immediate children, weighted by an escort over CHILDREN
///   flat part       = (ONE - rho[v]) * f
///       -> every leaf of v's subtree, weighted by an escort over those
///          LEAVES, skipping every intervening level
/// ```
///
/// This mirrors `allocator::flow_step`'s `desc_part`/`flat_part` split
/// exactly, so this function is the `N`-generic, per-level-lens
/// generalization of the certified measure rather than a different one that
/// happens to share a name. `rho == ONE` everywhere reduces it to the pure
/// multiplicative escort cascade `pi(v) = PRODUCT of L_q(child | parent)`,
/// bit-for-bit.
///
/// # Lenses
///
/// `lenses[d]` is the exponent applied to nodes at depth `d`; depths past the
/// end of the slice reuse its last entry (so a one-element slice is the
/// single-exponent, monofractal case, and an empty slice is the coverage lens
/// `q = 0` throughout). Escort weights for the flat path use the *leaf's* own
/// depth, which is what makes the flat path per-level too.
///
/// # What the returned values mean
///
/// One value per node, in the tree's own index order. For a leaf it is the
/// total mass that arrived, by either path
/// (`flow + flat`, matching `allocator`'s `res[x] = flat_alloc[x] +
/// alloc_flow[x]`). For an internal node it is the flow that *passed through*
/// it before splitting -- which is what makes "how much does this subtree
/// matter" answerable at every depth, where `allocator`'s leaf-only output
/// cannot answer it.
///
/// # Descendant-flow conservation (BCINR-CMCA-B2)
///
/// At each internal node, the flow into its children never exceeds the flow
/// that arrived at the node -- `child_sum(v) <= input_share(v)`, always, no
/// exceptions. This is provable, not merely observed: both fixed-point
/// operations in the split (`saturating_div` for each child's share,
/// `saturating_mul` for that share's contribution) truncate toward zero and
/// never round up, and the shares are an exact partition of `1` in real-number
/// terms -- so floor-then-floor of an exact partition can only lose value,
/// never manufacture it. The residual (`input_share - child_sum`) can be
/// nonzero (Q16.16 flooring means an *exact* `ONE`-sum is not guaranteed),
/// but it is one-sided: [`consequence_mass_traced`]'s
/// `AllocationStep::residual_bits` is never negative, verified across 18
/// named fixtures plus a synthetic stress corpus at arities 2..=20 with
/// adversarial (pairwise-coprime) mass ratios -- see
/// `tests/cascade_residual_classification.rs`. A conservative, operation-count-
/// derived envelope also holds throughout that corpus: `residual_bits(v) <=
/// 2 * children(v).len()`, i.e. at most one Q16.16 ULP of loss per child per
/// truncating operation, though this is an empirically-robust ceiling rather
/// than a tight closed-form bound.
///
/// This claim is deliberately narrower than "leaves sum to `ONE`" (an
/// earlier version of this doc comment made that claim before
/// [`consequence_mass_traced`] existed to check it) -- the analogous claim on
/// `allocator::allocate`'s output was checked the same way and found to have
/// a real, legitimate exception (a documented fallback branch), so this
/// crate does not assume a mathematically plausible conservation law without
/// measuring it against the actual arithmetic first.
pub fn consequence_mass(
    tree: &CascadeTree,
    lenses: &[i32],
) -> Result<Vec<NonNegativeFixed>, CascadeRefusal> {
    consequence_mass_with_sink(tree, lenses, &mut NoTrace)
}

/// Records provenance from one [`consequence_mass_with_sink`] walk. Two
/// implementations: [`NoTrace`] (zero bookkeeping, what [`consequence_mass`]
/// uses) and `VecTrace` (collects [`AllocationStep`]s, what
/// [`consequence_mass_traced`] uses) -- both run the identical walk with the
/// identical arithmetic; the only difference is whether anything is
/// listening.
trait AllocationTraceSink {
    fn record(&mut self, step: AllocationStep);
}

/// The [`AllocationTraceSink`] [`consequence_mass`] uses: discards every
/// step immediately, no allocation beyond what the walk already does for
/// its own internal `Vec`s (see `cascade.rs`'s module docs -- this crate
/// already requires `alloc` unconditionally here, so this sink saves the
/// *extra* per-step bookkeeping work, not all allocation).
struct NoTrace;
impl AllocationTraceSink for NoTrace {
    #[inline(always)]
    fn record(&mut self, _step: AllocationStep) {}
}

#[derive(Default)]
struct VecTrace {
    steps: Vec<AllocationStep>,
}
impl AllocationTraceSink for VecTrace {
    fn record(&mut self, step: AllocationStep) {
        self.steps.push(step);
    }
}

/// One internal node's descendant-flow split: how much flow arrived at
/// `node` before splitting into its children (`input_share` --
/// `tree.rho[node] * flow[node]`, i.e. the descendant part, not the flat
/// part), and how each child's share of it was computed.
///
/// Does **not** record the separate flat-path (subtree-leaf) distribution --
/// that is a second, independent split `consequence_mass`'s walk performs
/// for the same node when its flat part is nonzero, landing mass directly on
/// descendant leaves rather than on immediate children. Recording it is
/// out of scope for this checkpoint; see [`AllocationTrace`]'s docs.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AllocationStep {
    pub node: usize,
    pub parent: Option<usize>,
    /// Depth of `node` from its root (0 = root). Named `wave` to match the
    /// vocabulary `process_to_mermaid_annotated`'s `wave_of_child` already
    /// uses for the same concept.
    pub wave: usize,
    pub input_share: NonNegativeFixed,
    /// `(child, this node's contribution to that child's flow)` -- the
    /// increment this split added, not the child's cumulative flow (which
    /// may also receive contributions from other ancestors' flat splits).
    pub child_shares: Vec<(usize, NonNegativeFixed)>,
    pub child_sum: NonNegativeFixed,
    /// `input_share.to_bits() as i64 - child_sum.to_bits() as i64`, signed
    /// so a caller can tell whether the split under- or over-spent, not
    /// just by how much. Recorded, not asserted: this field is what this
    /// checkpoint exists to measure. Do not assume it is always zero --
    /// `allocator::allocate`'s analogous "output sums to ONE" claim was
    /// checked this way and found to have a real, legitimate exception.
    pub residual_bits: i64,
}

/// Full provenance from one [`consequence_mass_traced`] call.
#[derive(Clone, Debug, PartialEq)]
pub struct AllocationTrace {
    /// One entry per internal node that performed a descendant-flow split,
    /// in the order `consequence_mass`'s own depth-sorted walk visits them
    /// (ascending depth; see `order.sort_by_key(|node| depth[*node])`
    /// below) -- deterministic for identical `(tree, lenses)`.
    pub steps: Vec<AllocationStep>,
    /// Identical, in the identical order, to [`consequence_mass`]'s return
    /// value for the same `(tree, lenses)` -- bit-for-bit, not just
    /// approximately (see `tests::traced_leaves_match_untraced_bit_for_bit`).
    pub leaves: Vec<NonNegativeFixed>,
}

/// [`consequence_mass`] with its per-node descendant-flow splits recorded
/// instead of discarded. Same walk, same arithmetic --
/// `consequence_mass_traced(tree, lenses)?.leaves ==
/// consequence_mass(tree, lenses)?` bit-for-bit, always (see
/// `tests::traced_leaves_match_untraced_bit_for_bit`).
pub fn consequence_mass_traced(
    tree: &CascadeTree,
    lenses: &[i32],
) -> Result<AllocationTrace, CascadeRefusal> {
    let mut sink = VecTrace::default();
    let leaves = consequence_mass_with_sink(tree, lenses, &mut sink)?;
    Ok(AllocationTrace {
        steps: sink.steps,
        leaves,
    })
}

fn consequence_mass_with_sink(
    tree: &CascadeTree,
    lenses: &[i32],
    sink: &mut impl AllocationTraceSink,
) -> Result<Vec<NonNegativeFixed>, CascadeRefusal> {
    let len = tree.len();
    if len == 0 {
        return Ok(Vec::new());
    }
    // Order matters: a parent vector with no `None` entry always contains a
    // cycle on a finite node set, so running `depths` first made `NoRoot`
    // unreachable -- every root-free tree was reported as `Cyclic` instead of
    // the more specific diagnosis. Checking rootedness first leaves both
    // variants live: `Cyclic` now witnesses a cycle among nodes that coexists
    // with a root elsewhere in the forest (e.g. parent = [None, Some(2), Some(1)]).
    if !tree.parent.iter().any(Option::is_none) {
        return Err(CascadeRefusal::NoRoot);
    }
    let depth = depths(tree)?;

    let lens_at = |d: usize| -> i32 {
        if lenses.is_empty() {
            0
        } else {
            lenses[d.min(lenses.len() - 1)]
        }
    };

    // One escort weight per node, reused by both the child escort and the
    // subtree-leaf escort -- `allocator` likewise derives `child_w` and
    // `leaf_w` from the same per-node masses.
    //
    // Classified explicitly (Checkpoint A): at `lens == 0` this walk wants
    // *sibling coverage*, not *support coverage* -- the module doc above
    // ("the coverage lens weights every sibling equally by construction")
    // and `escort.rs`'s correspondence tests both commit to every sibling
    // (including a zero-mass one) sharing the flow equally, which is
    // `uniform_sibling_weight`, not `escort_weight_support`. Calling
    // `uniform_sibling_weight` directly here makes that choice visible at
    // the call site instead of leaving it implicit inside `escort_weight`'s
    // `lens == 0` branch.
    let mut weight = Vec::with_capacity(len);
    for (node, (&mass, &node_depth)) in tree.mass.iter().zip(depth.iter()).enumerate() {
        let lens = lens_at(node_depth);
        let w = if lens == 0 {
            uniform_sibling_weight(mass, node)
        } else {
            escort_power(mass, lens, node)?
        };
        weight.push(w);
    }

    let is_leaf: Vec<bool> = (0..len)
        .map(|node| !tree.parent.contains(&Some(node)))
        .collect();
    let children: Vec<Vec<usize>> = (0..len)
        .map(|v| (0..len).filter(|c| tree.parent[*c] == Some(v)).collect())
        .collect();

    // Subtree leaves per node, built by walking each leaf up to its root. The
    // depth walk already proved acyclicity, so this terminates.
    let mut subtree_leaves: Vec<Vec<usize>> = vec![Vec::new(); len];
    for leaf in (0..len).filter(|node| is_leaf[*node]) {
        let mut cursor = tree.parent[leaf];
        while let Some(ancestor) = cursor {
            subtree_leaves[ancestor].push(leaf);
            cursor = tree.parent[ancestor];
        }
    }

    // `flow` is what arrives via the descendant path; `flat` is what lands
    // directly on a leaf from some ancestor's flat part.
    let mut flow = vec![NonNegativeFixed::ZERO; len];
    let mut flat = vec![NonNegativeFixed::ZERO; len];

    let roots: Vec<usize> = (0..len)
        .filter(|node| tree.parent[*node].is_none())
        .collect();
    let mut root_total = NonNegativeFixed::ZERO;
    for &root in &roots {
        root_total = admit_fixed(
            root_total.saturating_add(weight[root]),
            NumericContext::SiblingSum,
            root,
        )?;
    }
    if root_total.to_bits() == 0 {
        return Err(CascadeRefusal::DegenerateSiblingSet { parent: None });
    }
    for &root in &roots {
        flow[root] = admit_fixed(
            weight[root].saturating_div(root_total),
            NumericContext::ShareDivision,
            root,
        )?;
    }

    // Depth order guarantees a node's inbound flow is final before it splits.
    let mut order: Vec<usize> = (0..len).collect();
    order.sort_by_key(|node| depth[*node]);

    for v in order {
        if is_leaf[v] {
            continue;
        }
        let descendant_part = admit_fixed(
            tree.rho[v].saturating_mul(flow[v]),
            NumericContext::DescendantSplit,
            v,
        )?;
        let flat_part = NonNegativeFixed::ONE
            .saturating_sub(tree.rho[v])
            .saturating_mul(flow[v]);
        let flat_part = admit_fixed(flat_part, NumericContext::FlatSplit, v)?;

        let mut child_total = NonNegativeFixed::ZERO;
        for &c in &children[v] {
            child_total = admit_fixed(
                child_total.saturating_add(weight[c]),
                NumericContext::SiblingSum,
                c,
            )?;
        }
        if child_total.to_bits() == 0 {
            return Err(CascadeRefusal::DegenerateSiblingSet { parent: Some(v) });
        }
        let mut child_shares: Vec<(usize, NonNegativeFixed)> =
            Vec::with_capacity(children[v].len());
        let mut child_sum = NonNegativeFixed::ZERO;
        for &c in &children[v] {
            let share = admit_fixed(
                weight[c].saturating_div(child_total),
                NumericContext::ShareDivision,
                c,
            )?;
            let contribution = admit_fixed(
                descendant_part.saturating_mul(share),
                NumericContext::FlowAccumulation,
                c,
            )?;
            flow[c] = admit_fixed(
                flow[c].saturating_add(contribution),
                NumericContext::FlowAccumulation,
                c,
            )?;
            child_sum = child_sum.saturating_add(contribution);
            child_shares.push((c, contribution));
        }
        sink.record(AllocationStep {
            node: v,
            parent: tree.parent[v],
            wave: depth[v],
            input_share: descendant_part,
            residual_bits: descendant_part.to_bits() as i64 - child_sum.to_bits() as i64,
            child_shares,
            child_sum,
        });

        // Only walk the flat path when it actually carries mass: under
        // `rho == ONE` a degenerate subtree-leaf set is harmless, and
        // refusing on it would break the pure-cascade case for no reason.
        if flat_part.to_bits() == 0 {
            continue;
        }
        let mut leaf_total = NonNegativeFixed::ZERO;
        for &x in &subtree_leaves[v] {
            leaf_total = admit_fixed(
                leaf_total.saturating_add(weight[x]),
                NumericContext::SubtreeLeafSum,
                x,
            )?;
        }
        if leaf_total.to_bits() == 0 {
            return Err(CascadeRefusal::DegenerateSubtreeLeaves { node: v });
        }
        for &x in &subtree_leaves[v] {
            let share = admit_fixed(
                weight[x].saturating_div(leaf_total),
                NumericContext::ShareDivision,
                x,
            )?;
            flat[x] = admit_fixed(
                flat[x].saturating_add(flat_part.saturating_mul(share)),
                NumericContext::FlatAccumulation,
                x,
            )?;
        }
    }

    (0..len)
        .map(|node| {
            admit_fixed(
                flow[node].saturating_add(flat[node]),
                NumericContext::FinalAccumulation,
                node,
            )
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mass(x: f32) -> NonNegativeFixed {
        NonNegativeFixed::from_bits((x * 65536.0).round() as u32)
    }

    // -- Checkpoint A: escort_weight_support / uniform_sibling_weight split --
    //
    // These are written before the two functions exist (TDD red phase) and
    // pin down the one behavioral difference the ticket cares about:
    // `q == 0` on a zero-mass node. `escort_weight` (unsplit) treats this as
    // *sibling coverage* (weight ONE, matching every other sibling); the
    // Lean reference (`ReferenceLens.coverage`, see `escort.rs`'s module
    // docs) instead treats it as *support coverage* (weight ZERO, the node
    // is excluded from the uniform measure because it carries no mass).
    // `escort_weight` cannot express both at once through one name, hence
    // the split.

    #[test]
    fn escort_weight_support_is_zero_at_q_zero_for_zero_mass() {
        // Support coverage: a mass-carrying sibling excludes the zero-mass
        // one entirely, rather than weighting it equally.
        assert_eq!(
            escort_weight_support(NonNegativeFixed::ZERO, 0, 0).unwrap(),
            NonNegativeFixed::ZERO
        );
    }

    #[test]
    fn escort_weight_support_is_one_at_q_zero_for_nonzero_mass() {
        assert_eq!(
            escort_weight_support(mass(3.0), 0, 0).unwrap(),
            NonNegativeFixed::ONE
        );
    }

    #[test]
    fn escort_weight_support_matches_escort_weight_for_nonzero_lens() {
        // Away from q == 0 the two conventions coincide: `m^q` is already
        // zero for a zero mass under a positive lens, and both functions
        // refuse identically under a negative lens (there is no coverage
        // question once the lens itself is nonzero).
        for lens in [-2, -1, 1, 2] {
            for m in [mass(0.0), mass(0.5), mass(1.0), mass(3.0)] {
                assert_eq!(
                    escort_weight_support(m, lens, 0),
                    escort_weight(m, lens, 0),
                    "lens={lens} m={m:?}"
                );
            }
        }
    }

    #[test]
    fn uniform_sibling_weight_is_one_regardless_of_mass() {
        // Sibling coverage: every sibling gets the same weight whether or
        // not it carries mass -- normalizing by `n` equal weights is what
        // makes this "1/n" once `consequence_mass`'s sibling-sum division
        // runs; the per-node primitive itself just needs to be constant.
        assert_eq!(
            uniform_sibling_weight(NonNegativeFixed::ZERO, 0),
            NonNegativeFixed::ONE
        );
        assert_eq!(uniform_sibling_weight(mass(7.0), 0), NonNegativeFixed::ONE);
    }

    // -- Checkpoint A: ULP-precision witness --
    //
    // The ticket for this checkpoint asked to "reinstate the 498-ULP
    // witness as a fixture." An exhaustive search of this crate's git
    // history (`git log --all -S"498"`, `git log --all --grep=ULP -i`)
    // and its current tests (`falsification_adversarial.rs`'s
    // `falsify_q16_16_division_precision_loss`, at most 2 ULP;
    // `cascade_residual_classification.rs`'s `stress_corpus_bounds_check`,
    // observed max 10 residual bits across arities 2..=20) turned up no
    // fixture, past or present, exhibiting anything close to 498 ULP of
    // loss anywhere in `escort_weight`/`escort_power`/`consequence_mass`.
    // `escort_power`'s own domain (`MAX_LENS_MAGNITUDE == 16` repeated
    // multiplications) structurally bounds how much a single escort weight
    // can lose: each `saturating_mul` truncates by strictly less than one
    // ULP of its input, so 16 chained multiplications cannot manufacture
    // anywhere near 498 ULP of loss on their own -- a swept measurement
    // below confirms this.
    //
    // This is therefore a *reconstruction*, not a reinstatement: no
    // original 498-ULP artifact was found to recover. What follows sweeps
    // the admitted domain (every integer lens in
    // `-MAX_LENS_MAGNITUDE..=MAX_LENS_MAGNITUDE`, a representative mass
    // grid biased toward the values that maximize compounding truncation --
    // near `ONE` from below, and near the smallest representable nonzero
    // mass) against an independent `f64` oracle (the same independent-oracle
    // form `tests/reference.rs` and `tests/differential.rs` already use for
    // this crate; not a translation of `escort_power`'s own control
    // structure), records the actual observed maximum ULP loss, and pins it
    // as a named witness so a future regression is caught by name instead of
    // by a round-numbered guess.
    #[test]
    fn escort_power_ulp_loss_witness() {
        let mut max_loss: i64 = 0;
        let mut witness: Option<(u32, i32, u32, u32)> = None; // (mass_bits, lens, exact_bits, actual_bits)

        // Mass grid: near ONE from below (worst case for positive lenses,
        // where repeated truncation compounds a value close to the top of
        // its range), a few interior points, and the smallest representable
        // nonzero mass (worst case for negative lenses, which reciprocate).
        let mass_bits_grid: [u32; 7] = [1, 100, 32768, 65500, 65535, 65536, 131072];

        for &mb in &mass_bits_grid {
            let m = NonNegativeFixed::from_bits(mb);
            let m_real = f64::from(mb) / 65536.0;
            for lens in 1..=(MAX_LENS_MAGNITUDE as i32) {
                for signed_lens in [lens, -lens] {
                    let Ok(actual) = escort_power(m, signed_lens, 0) else {
                        continue; // refusal (e.g. ZeroMassUnderNegativeLens, EscortUnderflow) -- not a precision question
                    };
                    // Independent oracle: plain f64 exponentiation, not a
                    // translation of escort_power's repeated-multiplication
                    // control structure.
                    let exact_real = m_real.powi(signed_lens);
                    if !exact_real.is_finite() || exact_real < 0.0 || exact_real > 65535.0 {
                        continue; // outside Q16.16's representable range -- saturation, not a precision comparison
                    }
                    let exact_bits = (exact_real * 65536.0).round() as i64;
                    let loss = (exact_bits - actual.to_bits() as i64).abs();
                    if loss > max_loss {
                        max_loss = loss;
                        witness = Some((mb, signed_lens, exact_bits as u32, actual.to_bits()));
                    }
                }
            }
        }

        extern crate std;
        std::eprintln!(
            "escort_power ULP-loss witness: max_loss={max_loss} details={witness:?} \
             (compare against the ticket's claimed 498 -- no such value was found or reproduced \
             for this admitted domain)"
        );

        // The structural bound this measurement is checking: 16 chained
        // saturating_mul truncations (or one reciprocal on top of them)
        // cannot lose anywhere near 498 ULP. Pinned generously above the
        // observed value so a real regression (e.g. a dropped truncation
        // guard, or a reciprocal computed against the wrong accumulator)
        // is still caught, without hand-tuning to the exact figure.
        assert!(
            max_loss <= 32,
            "escort_power ULP-loss witness regressed: max_loss={max_loss} details={witness:?} \
             (previously observed <= a small single-digit/low-double-digit bound; nowhere near \
             the ticket's claimed 498)"
        );
    }

    #[test]
    fn escort_weight_at_q_zero_still_matches_uniform_sibling_weight() {
        // `escort_weight`'s existing lens==0 branch is sibling coverage
        // (documented in `escort.rs`'s module docs and pinned by
        // `cmca_h_lean_correspondence.rs`) -- this must not silently
        // change to support coverage as a side effect of the split.
        assert_eq!(
            escort_weight(NonNegativeFixed::ZERO, 0, 0).unwrap(),
            uniform_sibling_weight(NonNegativeFixed::ZERO, 0)
        );
    }

    /// A 3-level tree: root -> {a, b} -> {a1, a2} (only `a` has children).
    /// Small enough to reason about by hand, deep enough to exercise more
    /// than one descendant-flow split.
    fn small_tree() -> CascadeTree {
        CascadeTree::new(
            vec![None, Some(0), Some(0), Some(1), Some(1)],
            vec![
                mass(1.0), // root -- must be nonzero: with one root, root_total
                // is exactly this weight, and zero would refuse as
                // DegenerateSiblingSet rather than build the tree.
                mass(3.0), // a
                mass(1.0), // b
                mass(2.0), // a1
                mass(1.0), // a2
            ],
        )
        .unwrap()
    }

    #[test]
    fn traced_leaves_match_untraced_bit_for_bit() {
        let tree = small_tree();
        let lenses = [1i32];
        let untraced = consequence_mass(&tree, &lenses).unwrap();
        let traced = consequence_mass_traced(&tree, &lenses).unwrap();
        assert_eq!(traced.leaves, untraced, "projection equivalence");
    }

    #[test]
    fn trace_is_deterministic_across_identical_calls() {
        let tree = small_tree();
        let lenses = [1i32];
        let first = consequence_mass_traced(&tree, &lenses).unwrap();
        let second = consequence_mass_traced(&tree, &lenses).unwrap();
        assert_eq!(first, second);
    }

    #[test]
    fn trace_steps_only_cover_internal_nodes_and_reference_real_children() {
        let tree = small_tree();
        let lenses = [1i32];
        let trace = consequence_mass_traced(&tree, &lenses).unwrap();

        // Internal nodes are root (0) and a (1); b, a1, a2 are leaves and
        // must not appear as a step's `node`.
        let stepped_nodes: alloc::vec::Vec<usize> = trace.steps.iter().map(|s| s.node).collect();
        assert_eq!(
            stepped_nodes,
            alloc::vec![0, 1],
            "depth-ascending order, internal nodes only"
        );

        for step in &trace.steps {
            for &(child, _) in &step.child_shares {
                assert_eq!(
                    tree.parent[child],
                    Some(step.node),
                    "every recorded child must actually be a child of the stepped node"
                );
            }
        }
    }

    /// Not a conservation law -- a measurement. Confirms `residual_bits` is
    /// computed the way its docs say (`input_share - child_sum`), on this
    /// tree's actual numbers, rather than asserting it must be zero.
    #[test]
    fn residual_bits_matches_its_own_definition() {
        let tree = small_tree();
        let lenses = [1i32];
        let trace = consequence_mass_traced(&tree, &lenses).unwrap();
        for step in &trace.steps {
            let expected = step.input_share.to_bits() as i64 - step.child_sum.to_bits() as i64;
            assert_eq!(step.residual_bits, expected);
        }
    }
}
