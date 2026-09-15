//! # Allocation audit-trail receipts
//!
//! `allocate` (and `allocate_in`) compute, then discard, a per-`(measure, lens)` share
//! for every candidate on the way to the single combined vector they return. Once that
//! call has returned, there is no way to answer "why did candidate X get share Y under
//! measure K at lens Q" without re-running the whole allocation by hand and diffing
//! internal state. This module is the audit-trail companion, following the same pattern
//! as `certification::seal_certificate`:
//!
//! - [`AllocationBindings`] is a typed struct enumerating every input that determined one
//!   candidate's per-`(measure, lens)` share -- the candidate's index, which measure and
//!   lens produced the share, the lens's own `q` value, and a digest of the semantic
//!   states / parent forest / MWU weights that fed the computation.
//! - [`AllocationRefusal`] is a typed refusal enum, one variant per check, including
//!   [`AllocationRefusal::Cyclic`] for a cyclic `parent` (checked via
//!   `check_hierarchy_acyclic`, mirroring `allocate_single_lens`'s
//!   `LensSelectionRefusal::Cyclic`) -- sealing or verifying over a cyclic `parent` refuses
//!   rather than silently recomputing over `ancestor_doubling_table`'s garbage topology.
//! - [`verify_allocation_receipt`] independently RECOMPUTES the share from the bindings
//!   plus the caller-supplied actual inputs -- by calling the crate's own topology
//!   (`ancestor_doubling_table`) and per-lens kernel (`compute_pi_kq_for_kq`), the exact
//!   same functions `allocate_in` itself calls -- and refuses on any mismatch rather than
//!   trusting the receipt's recorded share.
//!
//! This is purely additive: it does not touch `allocate`/`allocate_in`'s signatures,
//! return types, or hot-path behavior (the two visibility bumps this module required --
//! `ancestor_doubling_table` and `compute_pi_kq_for_kq` becoming `pub(crate)` -- change
//! nothing about what those functions compute). A caller mints a receipt with
//! [`seal_allocation_receipt`] alongside (or any time after) a normal `allocate` call,
//! using the exact `states`/`parent`/`weights` that call was given (for `weights`, the
//! array as it stood *after* the call returned -- `allocate_in` computes each candidate's
//! share from the post-MWU-update weights, not the pre-call ones; this module cannot detect
//! a caller passing the wrong snapshot, so that ordering remains a caller-discipline
//! requirement, not a checked one). Anyone later holding just the receipt and the recorded
//! inputs can call [`verify_allocation_receipt`] to independently recompute and cross-check
//! the share against those inputs -- **not** a cryptographic tamper-evidence guarantee: the
//! binding digest (`mix64`, below) is a 64-bit non-cryptographic splitmix64-style finalizer,
//! the same kind of internal audit-trail checksum `certification::seal_certificate` uses,
//! not a collision-resistant hash like `bcinr-powl`'s BLAKE3-backed `OcelCausalReceipt`. It
//! is adequate to catch accidental/incidental input drift and to structure an audit trail,
//! but a party who can freely choose both a receipt and its claimed inputs could construct a
//! digest collision; treat this module as an audit aid, not a security boundary.

#![allow(clippy::needless_range_loop)] // mirrors allocate_in's own index-parallel arrays

use crate::allocator::{
    ancestor_doubling_table, check_hierarchy_acyclic, clip, compute_pi_kq_for_kq,
};
use crate::fixed::{NonNegativeFixed, SignedFixed};
use crate::generated::consequence_mass::case_studies::{
    LensSpec, PackedSemanticState, FACTOR_ACCESS_FREQUENCY, FACTOR_BUSINESS_VALUE,
    FACTOR_DOWNSTREAM_CONSEQUENCE, FACTOR_RECOMPUTATION_COST, FACTOR_RETRIEVAL_DEMAND,
    FACTOR_SCHEDULING_DEMAND, FACTOR_SEARCH_DEMAND, FACTOR_STANDING, FACTOR_VERIFICATION_COST, K,
    MEASURE_CACHE, MEASURE_RETRIEVAL, MEASURE_SCHEDULING, MEASURE_SEARCH, N, Q,
};

/// Every input that determined one candidate's per-`(measure, lens)` allocation share.
/// Fields are either small indices/scalars re-checked directly, or a digest; equality on
/// the digest means "recomputed-from-the-actual-artifact digest matches the receipt's own
/// record of that digest," never merely "two receipts agree with each other."
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct AllocationBindings {
    pub candidate_id: usize,
    pub measure: usize,
    pub lens_index: usize,
    pub lens_q: i32,
    pub inputs_digest: u64,
}

/// Refusal reasons for [`verify_allocation_receipt`] -- one variant per enumerated
/// binding check, plus the recomputed-share comparison itself.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum AllocationRefusal {
    CandidateIndexOutOfRange,
    MeasureIndexOutOfRange,
    LensIndexOutOfRange,
    LensQMismatch,
    InputsDigestMismatch,
    ShareMismatch,
    /// `parent` describes a cyclic forest (per `check_hierarchy_acyclic`), the same
    /// witness `allocate_single_lens` refuses on -- mirrors `LensSelectionRefusal::Cyclic`
    /// (`allocator/mod.rs`). Sealing or verifying over a cyclic `parent` is refused rather
    /// than silently computing a share from `ancestor_doubling_table`'s garbage topology.
    Cyclic,
}

impl core::fmt::Display for AllocationRefusal {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        core::fmt::Debug::fmt(self, f)
    }
}

#[cfg(feature = "std")]
impl std::error::Error for AllocationRefusal {}

/// A sealed audit-trail receipt for one candidate's per-`(measure, lens)` allocation
/// share. Opaque outside this module except through its accessors -- the only production
/// constructor is [`seal_allocation_receipt`].
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct AllocationReceipt {
    bindings: AllocationBindings,
    share: u32,
}

impl AllocationReceipt {
    #[inline(always)]
    pub fn bindings(&self) -> AllocationBindings {
        self.bindings
    }

    /// The recorded share, as raw Q16.16 bits (`NonNegativeFixed::val`).
    #[inline(always)]
    pub fn share_bits(&self) -> u32 {
        self.share
    }

    #[inline(always)]
    pub fn share(&self) -> NonNegativeFixed {
        NonNegativeFixed::from_bits(self.share)
    }
}

#[inline(always)]
fn mix64(a: u64, b: u64) -> u64 {
    let mut x = a ^ b.wrapping_mul(0x9E3779B97F4A7C15);
    x ^= x >> 33;
    x = x.wrapping_mul(0xFF51AFD7ED558CCD);
    x ^= x >> 33;
    x = x.wrapping_mul(0xC4CEB9FE1A85EC53);
    x ^= x >> 33;
    x
}

/// Digests the three input clusters that determine every candidate's share:
/// the semantic states, the parent forest, and the (post-update) MWU weights.
///
/// This is a 64-bit non-cryptographic checksum (`mix64` chaining, splitmix64-style), not a
/// cryptographic hash -- it is sized and intended as an internal audit-trail integrity check
/// (catching accidental input drift between seal and verify), not as a collision-resistant
/// commitment a distrusting third party could rely on against a deliberate forger.
fn inputs_digest(
    states: &[PackedSemanticState; N],
    parent: &[i32; N],
    weights: &[[NonNegativeFixed; 2 * Q]; N],
) -> u64 {
    let mut d = 0x1234_5678_9abc_def0u64;
    for state in states.iter() {
        for factor in state.factors.iter() {
            d = mix64(d, factor.val as u64);
        }
    }
    for &p in parent.iter() {
        d = mix64(d, p as u32 as u64);
    }
    for row in weights.iter() {
        for w in row.iter() {
            d = mix64(d, w.val as u64);
        }
    }
    d
}

/// Recomputes the leaf/subtree-leaf topology from `parent`, mirroring
/// `allocate_in`'s inline computation exactly (same `ancestor_doubling_table` witness).
fn derive_topology(parent: &[i32; N]) -> ([bool; N], [[bool; N]; N]) {
    let mut is_leaf = [true; N];
    for i in 0..N {
        for j in 0..N {
            if parent[j] == i as i32 {
                is_leaf[i] = false;
            }
        }
    }

    let p = ancestor_doubling_table(parent);
    let mut is_descendant = [[false; N]; N];
    for i in 0..N {
        for j in 0..N {
            let mut matched = j == i;
            for level in 0..8 {
                matched |= p[level][j] == i as i32;
            }
            is_descendant[i][j] = matched;
        }
    }

    let mut is_subtree_leaf = [[false; N]; N];
    for i in 0..N {
        for k in 0..N {
            is_subtree_leaf[i][k] = is_leaf[k] && is_descendant[i][k];
        }
    }

    (is_leaf, is_subtree_leaf)
}

/// Recomputes the per-measure clipped semantic mass table from `states`, mirroring
/// `allocate_in`'s inline computation exactly (same mass formula and clamp bounds).
fn derive_node_masses(
    states: &[PackedSemanticState; N],
    m_min: NonNegativeFixed,
    m_max: NonNegativeFixed,
) -> [[NonNegativeFixed; N]; K] {
    let mut node_masses = [[NonNegativeFixed::ZERO; N]; K];
    for i in 0..N {
        let state = &states[i];
        let f_recomp = state.factors[FACTOR_RECOMPUTATION_COST];
        let f_verify = state.factors[FACTOR_VERIFICATION_COST];
        let f_stand = state.factors[FACTOR_STANDING];
        let f_access = state.factors[FACTOR_ACCESS_FREQUENCY];
        let f_search = state.factors[FACTOR_SEARCH_DEMAND];
        let f_retrieve = state.factors[FACTOR_RETRIEVAL_DEMAND];
        let f_sched = state.factors[FACTOR_SCHEDULING_DEMAND];
        let f_bval = state.factors[FACTOR_BUSINESS_VALUE];
        let f_conseq = state.factors[FACTOR_DOWNSTREAM_CONSEQUENCE];

        let m_cache = (f_recomp * NonNegativeFixed::from_num(5) + f_verify) * f_access * f_stand;
        let m_search = (f_bval + f_conseq) * f_search * f_stand;
        let m_retrieval = f_bval * f_retrieve;
        let m_sched = f_bval * f_sched;

        node_masses[MEASURE_CACHE][i] = m_cache;
        node_masses[MEASURE_RETRIEVAL][i] = m_retrieval;
        node_masses[MEASURE_SCHEDULING][i] = m_sched;
        node_masses[MEASURE_SEARCH][i] = m_search;
    }

    for k in 0..K {
        for i in 0..N {
            node_masses[k][i] = clip(node_masses[k][i], m_min, m_max);
        }
    }

    node_masses
}

/// Recomputes candidate `candidate_id`'s share under `(measure, lens_index)`, using
/// exactly the same topology witness and per-lens kernel `allocate_in` uses internally.
#[allow(clippy::too_many_arguments)]
fn recompute_share(
    candidate_id: usize,
    measure: usize,
    lens_index: usize,
    states: &[PackedSemanticState; N],
    parent: &[i32; N],
    weights: &[[NonNegativeFixed; 2 * Q]; N],
    lenses: &[LensSpec; Q],
    m_min: NonNegativeFixed,
    m_max: NonNegativeFixed,
) -> NonNegativeFixed {
    let (is_leaf, is_subtree_leaf) = derive_topology(parent);
    let node_masses = derive_node_masses(states, m_min, m_max);
    let q_val = SignedFixed::from_bits(lenses[lens_index].q.val);
    let pi = compute_pi_kq_for_kq(
        measure,
        lens_index,
        q_val,
        parent,
        &is_leaf,
        &is_subtree_leaf,
        &node_masses,
        weights,
    );
    pi[candidate_id]
}

/// Seals an [`AllocationReceipt`] for candidate `candidate_id`'s share under
/// `(measure, lens_index)`, given the exact `states`/`parent`/`weights`/`lenses` that
/// produced it (`weights` as it stood *after* the `allocate` call, per this module's
/// docs). `m_min`/`m_max` are the mass-clamp bounds in force for that call --
/// `ALLOCATOR_MASS_MIN_BITS`/`ALLOCATOR_MASS_MAX_BITS` (this crate's `generated_profile`)
/// for a plain `allocate()` caller -- the same bounds `FeasibleRegion::CURRENT` wraps.
#[allow(clippy::too_many_arguments)]
pub fn seal_allocation_receipt(
    candidate_id: usize,
    measure: usize,
    lens_index: usize,
    states: &[PackedSemanticState; N],
    parent: &[i32; N],
    weights: &[[NonNegativeFixed; 2 * Q]; N],
    lenses: &[LensSpec; Q],
    m_min: NonNegativeFixed,
    m_max: NonNegativeFixed,
) -> Result<AllocationReceipt, AllocationRefusal> {
    if candidate_id >= N {
        return Err(AllocationRefusal::CandidateIndexOutOfRange);
    }
    if measure >= K {
        return Err(AllocationRefusal::MeasureIndexOutOfRange);
    }
    if lens_index >= Q {
        return Err(AllocationRefusal::LensIndexOutOfRange);
    }
    if check_hierarchy_acyclic(parent).is_err() {
        return Err(AllocationRefusal::Cyclic);
    }

    let share = recompute_share(
        candidate_id,
        measure,
        lens_index,
        states,
        parent,
        weights,
        lenses,
        m_min,
        m_max,
    );

    Ok(AllocationReceipt {
        bindings: AllocationBindings {
            candidate_id,
            measure,
            lens_index,
            lens_q: lenses[lens_index].q.val,
            inputs_digest: inputs_digest(states, parent, weights),
        },
        share: share.val,
    })
}

/// Verifies `receipt` against the actual `states`/`parent`/`weights`/`lenses` a caller
/// claims produced it. Independently recomputes the candidate's share from those actual
/// inputs (never trusting `receipt.share()`) and checks every one of
/// [`AllocationBindings`]'s fields. Any single mismatch -- an out-of-range index, a
/// changed lens `q`, a changed states/parent/weights digest, or a genuinely different
/// recomputed share -- refuses; there is no partial/"mostly matches" outcome.
pub fn verify_allocation_receipt(
    receipt: &AllocationReceipt,
    states: &[PackedSemanticState; N],
    parent: &[i32; N],
    weights: &[[NonNegativeFixed; 2 * Q]; N],
    lenses: &[LensSpec; Q],
    m_min: NonNegativeFixed,
    m_max: NonNegativeFixed,
) -> Result<(), AllocationRefusal> {
    let b = receipt.bindings;

    if b.candidate_id >= N {
        return Err(AllocationRefusal::CandidateIndexOutOfRange);
    }
    if b.measure >= K {
        return Err(AllocationRefusal::MeasureIndexOutOfRange);
    }
    if b.lens_index >= Q {
        return Err(AllocationRefusal::LensIndexOutOfRange);
    }

    if lenses[b.lens_index].q.val != b.lens_q {
        return Err(AllocationRefusal::LensQMismatch);
    }
    if check_hierarchy_acyclic(parent).is_err() {
        return Err(AllocationRefusal::Cyclic);
    }

    if inputs_digest(states, parent, weights) != b.inputs_digest {
        return Err(AllocationRefusal::InputsDigestMismatch);
    }

    let recomputed = recompute_share(
        b.candidate_id,
        b.measure,
        b.lens_index,
        states,
        parent,
        weights,
        lenses,
        m_min,
        m_max,
    );

    if recomputed.val != receipt.share {
        return Err(AllocationRefusal::ShareMismatch);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::generated::consequence_mass::case_studies::{
        ETA, LAMBDA, LENS_REGISTRY, OBJECT_REGISTRY,
    };
    use crate::generated_profile::{ALLOCATOR_MASS_MAX_BITS, ALLOCATOR_MASS_MIN_BITS};

    fn fresh_weights() -> [[NonNegativeFixed; 2 * Q]; N] {
        [[NonNegativeFixed::ONE; 2 * Q]; N]
    }

    fn star_parent() -> [i32; N] {
        // Node 0 is the root; every other node is a direct leaf child of it.
        let mut parent = [0i32; N];
        parent[0] = -1;
        parent
    }

    #[test]
    fn genuine_receipt_verifies() {
        let states = OBJECT_REGISTRY;
        let parent = star_parent();
        let weights = fresh_weights();
        let lenses = LENS_REGISTRY;
        let m_min = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MIN_BITS);
        let m_max = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MAX_BITS);

        let receipt = seal_allocation_receipt(
            3,
            MEASURE_CACHE,
            1,
            &states,
            &parent,
            &weights,
            &lenses,
            m_min,
            m_max,
        )
        .expect("bounds are in range");

        assert_eq!(
            verify_allocation_receipt(&receipt, &states, &parent, &weights, &lenses, m_min, m_max),
            Ok(())
        );

        // Sanity: this call also exercises `allocate` end to end, and its combined
        // output is unrelated math -- the receipt is about the per-(measure,lens)
        // kernel `allocate` calls internally, not the combined vector itself.
        let mut mutable_weights = weights;
        let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
        let mu = [NonNegativeFixed::ZERO; N];
        let costs = [NonNegativeFixed::ZERO; N];
        let mut last_switch_t = 0u32;
        let mut prev_mode = 0u32;
        let result = crate::allocator::allocate(
            &states,
            &lenses,
            &LAMBDA,
            ETA,
            &parent,
            &mut mutable_weights,
            &payoffs,
            NonNegativeFixed::ZERO,
            NonNegativeFixed::ZERO,
            &mu,
            &costs,
            0,
            &mut last_switch_t,
            &mut prev_mode,
            500,
            crate::generated::stability_profile::CERTIFICATE_DIGEST,
            None,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn refuses_when_share_was_tampered_with() {
        let states = OBJECT_REGISTRY;
        let parent = star_parent();
        let weights = fresh_weights();
        let lenses = LENS_REGISTRY;
        let m_min = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MIN_BITS);
        let m_max = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MAX_BITS);

        let mut receipt = seal_allocation_receipt(
            3,
            MEASURE_CACHE,
            1,
            &states,
            &parent,
            &weights,
            &lenses,
            m_min,
            m_max,
        )
        .expect("bounds are in range");

        // Simulate a tampered/forged receipt claiming a different share than what
        // the recorded inputs actually produce.
        receipt.share ^= 1;

        assert_eq!(
            verify_allocation_receipt(&receipt, &states, &parent, &weights, &lenses, m_min, m_max),
            Err(AllocationRefusal::ShareMismatch)
        );
    }

    #[test]
    fn refuses_when_inputs_were_tampered_with() {
        let states = OBJECT_REGISTRY;
        let parent = star_parent();
        let weights = fresh_weights();
        let lenses = LENS_REGISTRY;
        let m_min = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MIN_BITS);
        let m_max = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MAX_BITS);

        let receipt = seal_allocation_receipt(
            3,
            MEASURE_CACHE,
            1,
            &states,
            &parent,
            &weights,
            &lenses,
            m_min,
            m_max,
        )
        .expect("bounds are in range");

        let mut tampered_weights = weights;
        tampered_weights[0][0] = NonNegativeFixed::from_bits(tampered_weights[0][0].val + 1);

        assert_eq!(
            verify_allocation_receipt(
                &receipt,
                &states,
                &parent,
                &tampered_weights,
                &lenses,
                m_min,
                m_max
            ),
            Err(AllocationRefusal::InputsDigestMismatch)
        );
    }

    #[test]
    fn refuses_when_lens_q_was_tampered_with() {
        let states = OBJECT_REGISTRY;
        let parent = star_parent();
        let weights = fresh_weights();
        let lenses = LENS_REGISTRY;
        let m_min = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MIN_BITS);
        let m_max = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MAX_BITS);

        let mut receipt = seal_allocation_receipt(
            3,
            MEASURE_CACHE,
            1,
            &states,
            &parent,
            &weights,
            &lenses,
            m_min,
            m_max,
        )
        .expect("bounds are in range");

        receipt.bindings.lens_q ^= 1;

        assert_eq!(
            verify_allocation_receipt(&receipt, &states, &parent, &weights, &lenses, m_min, m_max),
            Err(AllocationRefusal::LensQMismatch)
        );
    }

    #[test]
    fn seal_refuses_cyclic_parent() {
        let states = OBJECT_REGISTRY;
        let weights = fresh_weights();
        let lenses = LENS_REGISTRY;
        let m_min = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MIN_BITS);
        let m_max = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MAX_BITS);

        // Two-node cycle: 0 -> 1 -> 0, no root. `ancestor_doubling_table` doesn't
        // panic/hang on this (bounded 8-round doubling) -- it silently produces garbage
        // topology, which sealing must refuse to build a receipt over.
        let mut parent = star_parent();
        parent[0] = 1;
        parent[1] = 0;

        assert_eq!(
            seal_allocation_receipt(
                3,
                MEASURE_CACHE,
                1,
                &states,
                &parent,
                &weights,
                &lenses,
                m_min,
                m_max,
            ),
            Err(AllocationRefusal::Cyclic)
        );
    }

    #[test]
    fn verify_refuses_cyclic_parent() {
        let states = OBJECT_REGISTRY;
        let parent = star_parent();
        let weights = fresh_weights();
        let lenses = LENS_REGISTRY;
        let m_min = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MIN_BITS);
        let m_max = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MAX_BITS);

        let receipt = seal_allocation_receipt(
            3,
            MEASURE_CACHE,
            1,
            &states,
            &parent,
            &weights,
            &lenses,
            m_min,
            m_max,
        )
        .expect("bounds are in range, acyclic parent");

        // A verifier presented with a cyclic `parent` for the actual inputs must refuse,
        // not recompute a "verifying" share over garbage topology.
        let mut cyclic_parent = parent;
        cyclic_parent[0] = 1;
        cyclic_parent[1] = 0;

        assert_eq!(
            verify_allocation_receipt(
                &receipt,
                &states,
                &cyclic_parent,
                &weights,
                &lenses,
                m_min,
                m_max
            ),
            Err(AllocationRefusal::Cyclic)
        );
    }

    #[test]
    fn seal_refuses_out_of_range_candidate() {
        let states = OBJECT_REGISTRY;
        let parent = star_parent();
        let weights = fresh_weights();
        let lenses = LENS_REGISTRY;
        let m_min = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MIN_BITS);
        let m_max = NonNegativeFixed::from_bits(ALLOCATOR_MASS_MAX_BITS);

        assert_eq!(
            seal_allocation_receipt(
                N,
                MEASURE_CACHE,
                1,
                &states,
                &parent,
                &weights,
                &lenses,
                m_min,
                m_max,
            ),
            Err(AllocationRefusal::CandidateIndexOutOfRange)
        );
    }
}
