//! CMCA-101: real stepped-caller integration test for the dwell-time
//! hysteresis mode-switch signal (`dom_mode`/`prev_mode`/`last_switch_t`/
//! `tau_d`) in `allocator::allocate()`/`allocate_in()`.
//!
//! Ticket: docs/jira/cmca/CMCA-101.md. Prior to this test, no caller
//! anywhere threaded `last_switch_t`/`prev_mode`/`weights` forward across
//! successive `t` values -- every existing test/example called `allocate`
//! once (fresh state each call), which cannot exercise a mechanism defined
//! entirely in terms of state carried between calls. This test drives a
//! sequence of calls, threading state forward exactly as
//! `ORIGINAL_REQUEST.md:1355` / `stability_proof_draft.md:101-127`
//! describe: `if (t - last_switch_t < tau_D) reject_mode_switch()`.
//!
//! Assertions are state-based (Chicago style): on the real `prev_mode` /
//! `last_switch_t` returned in the `&mut` output parameters and the real
//! `pi_res` allocation vector, never on call counts or mock interactions.

#![cfg(not(any(
    feature = "mutant_1",
    feature = "mutant_2",
    feature = "mutant_3",
    feature = "mutant_4",
    feature = "mutant_5"
)))]

use bcinr_cmca::allocator::{
    allocate, AdaptiveUpdate, AdmittedControlState, CertificateReceipt, CertifiedLearning,
    EnvelopeReceipt, OutcomeReceipt,
};
use bcinr_cmca::fixed::NonNegativeFixed;
use bcinr_cmca::generated::consequence_mass::case_studies::{
    ETA, LAMBDA, LENS_REGISTRY, N, OBJECT_REGISTRY, Q,
};
use bcinr_cmca::generated::stability_profile::{CERTIFICATE_DIGEST, MODE_DWELL_ROUNDS_MIN};

fn get_proof() -> Option<AdaptiveUpdate<CertifiedLearning>> {
    AdaptiveUpdate::admit_adaptive_update(
        AdmittedControlState::admit_control_state(0),
        CertificateReceipt::admit_certificate(0),
        EnvelopeReceipt::admit_envelope(0),
        OutcomeReceipt::admit_outcome(0),
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ONE,
        CertifiedLearning::admit_learning(),
    )
}

/// Drives `allocate()` across a sequence of successive `t` values with a
/// genuinely two-level tree: root (0) has children {1, 2}, and node 1 is
/// itself internal with children {3, 4, 5, 6, 7}. A flat one-level star
/// (root with only leaf children) will NOT work here: `compute_kappa`
/// (CMCA-107's divergence guard) is identically zero at any node whose
/// direct children are all leaves, since `subtree_leaves(v) == children(v)`
/// makes `s_leaf(c) == s_meas(c)` for every child -- the guard would never
/// admit a weight update no matter how skewed the payoffs are. With node 1
/// internal, node 0's `subtree_leaves` (`{2, 3, 4, 5, 6, 7}`) differs from
/// its direct children's own masses (`{1, 2}`), so kappa at the *root* is
/// genuinely nonzero for this crate's real `OBJECT_REGISTRY` masses. This
/// resolves CMCA-107's kappa=0 degeneracy only at the root -- the node the
/// assertions below actually exercise. It does **not** resolve the same
/// degeneracy at node 1: node 1's own direct children (`{3, 4, 5, 6, 7}`)
/// are all leaves, so `is_subtree_leaf[c] == {c}` for each and
/// `kappa(1)` is identically zero for the whole run (CMCA-121), meaning
/// node 1's own MWU weight update is dead code in this test. That residual
/// degeneracy is out of scope here; this test only claims the root-level
/// fix.
///
/// `payoffs[0][1]` (the "descend" slot of lens 0) is biased heavily
/// relative to every other root slot, so after the first *admitted* update
/// the dominant mode at the root wants to flip from 0 to 1 -- and the test
/// watches the dwell-time lock hold that flip back until `tau_d` rounds
/// have elapsed since the last switch, then take effect exactly on
/// schedule. CMCA-121: the spec property this proves
/// (`N_switch(0,T) <= N0 + T/tau_D`, `stability_proof_draft.md:101-106`,
/// `ORIGINAL_REQUEST.md:1355`) is stated over a *sequence* of switches, so
/// after the first switch lands the test re-arms with a payoff bias
/// favoring a switch back to mode 0 and drives a second phase, proving the
/// dwell-time lock is re-applied (measured from the *new* `last_switch_t`,
/// not the original one) rather than only checked once.
#[test]
fn dwell_time_lock_holds_switch_until_tau_d_then_switches() {
    let tau_d = MODE_DWELL_ROUNDS_MIN; // 461 in the current profile
    let zeta = NonNegativeFixed::from_bits(800); // <= ZETA_W_MAX (819 raw @ Q16.16)

    // Root (0) has 7 children (1..7): an internal node, so its weights are
    // eligible for the MWU update that feeds dom_mode.
    let parent = [-1, 0, 0, 1, 1, 1, 1, 1];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    // Bias root slot 1 (q_idx=0's "descend" weight) heavily; every other
    // root slot (and every non-root node) gets zero payoff.
    let mut payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    payoffs[0][1] = NonNegativeFixed::from_num(50);

    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let mut last_switch_t = 0u32;
    let mut prev_mode = 0u32;
    let proof = get_proof();

    assert_eq!(prev_mode, 0, "starts in mode 0 by construction");

    let mut switched_at = None;

    for t in 0..=tau_d {
        let result = allocate(
            &OBJECT_REGISTRY,
            &LENS_REGISTRY,
            &LAMBDA,
            ETA,
            &parent,
            &mut weights,
            &payoffs,
            zeta,
            NonNegativeFixed::ZERO,
            &mu,
            &costs,
            t,
            &mut last_switch_t,
            &mut prev_mode,
            tau_d,
            CERTIFICATE_DIGEST,
            proof.as_ref(),
        )
        .unwrap_or_else(|e| panic!("allocate refused at t={t}: {e:?}"));
        let _ = result;

        if prev_mode != 0 && switched_at.is_none() {
            switched_at = Some(t);
        }

        if switched_at.is_none() {
            // Hysteresis holds: dwell time has not elapsed since the last
            // (t=0) switch epoch, so the mode must not have moved yet no
            // matter how skewed the root weights already are.
            assert_eq!(
                prev_mode, 0,
                "mode switched at t={t}, before tau_d={tau_d} rounds since last_switch_t={last_switch_t} elapsed"
            );
            assert_eq!(
                last_switch_t, 0,
                "last_switch_t moved at t={t} without a real mode switch"
            );
        }
    }

    // The dwell time (tau_d rounds since the initial last_switch_t=0) must
    // have elapsed by t=tau_d, and the root's dominant weight (already
    // skewed toward slot 1 after the very first update) must have finally
    // been allowed to take effect as a real mode switch -- this is the
    // state-based proof that the mechanism does something, not just that
    // it compiles.
    assert_eq!(
        switched_at,
        Some(tau_d),
        "expected the dwell-locked switch to land exactly at t=tau_d={tau_d}, got {switched_at:?}"
    );
    assert_eq!(prev_mode, 1, "dominant mode should have switched to slot 1");
    assert_eq!(
        last_switch_t, tau_d,
        "last_switch_t should record the epoch of the real switch"
    );

    // CMCA-121 phase 2: prove the dwell-time lock re-arms for a *second*
    // switch, measured from the new `last_switch_t` (= tau_d), not the
    // original one. A stale-baseline bug (e.g. `can_switch` computed
    // against the t=0 epoch instead of the real last_switch_t) would only
    // manifest here, not in phase 1. Re-bias payoffs to favor switching
    // back to mode 0 (root slot 0 -- lens 0's "flat" slot in the (0, 1)
    // pair): zero out the mode-1 bias and heavily weight slot 0 instead.
    payoffs[0][1] = NonNegativeFixed::ZERO;
    payoffs[0][0] = NonNegativeFixed::from_num(50);

    let second_switch_deadline = last_switch_t + tau_d;
    let mut switched_back_at = None;

    for t in (tau_d + 1)..=second_switch_deadline {
        let result = allocate(
            &OBJECT_REGISTRY,
            &LENS_REGISTRY,
            &LAMBDA,
            ETA,
            &parent,
            &mut weights,
            &payoffs,
            zeta,
            NonNegativeFixed::ZERO,
            &mu,
            &costs,
            t,
            &mut last_switch_t,
            &mut prev_mode,
            tau_d,
            CERTIFICATE_DIGEST,
            proof.as_ref(),
        )
        .unwrap_or_else(|e| panic!("allocate refused at t={t}: {e:?}"));
        let _ = result;

        if prev_mode != 1 && switched_back_at.is_none() {
            switched_back_at = Some(t);
        }

        if switched_back_at.is_none() {
            // Hysteresis holds again: dwell time has not elapsed since the
            // *second* switch epoch (last_switch_t=tau_d), so the mode must
            // stay at 1 no matter how skewed the root weights already are
            // toward slot 0.
            assert_eq!(
                prev_mode, 1,
                "mode switched back at t={t}, before a full tau_d={tau_d} rounds since the new last_switch_t={tau_d} elapsed"
            );
            assert_eq!(
                last_switch_t, tau_d,
                "last_switch_t moved at t={t} without a real second switch"
            );
        }
    }

    assert_eq!(
        switched_back_at,
        Some(second_switch_deadline),
        "expected the re-armed dwell-locked switch back to mode 0 to land exactly at t={second_switch_deadline} (= last_switch_t + tau_d), got {switched_back_at:?}"
    );
    assert_eq!(
        prev_mode, 0,
        "dominant mode should have switched back to slot 0 on the second transition"
    );
    assert_eq!(
        last_switch_t, second_switch_deadline,
        "last_switch_t should record the epoch of the second real switch, not the first"
    );
}

/// Second case required by the acceptance criteria: a dwell time that has
/// NOT elapsed keeps the mode locked for the entire run (hysteresis holds
/// with no switch at all when the run is shorter than tau_d).
#[test]
fn dwell_time_lock_prevents_switch_when_run_is_shorter_than_tau_d() {
    let tau_d = MODE_DWELL_ROUNDS_MIN; // 461
    let zeta = NonNegativeFixed::from_bits(800);

    let parent = [-1, 0, 0, 1, 1, 1, 1, 1];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    let mut payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    payoffs[0][1] = NonNegativeFixed::from_num(50);

    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let mut last_switch_t = 0u32;
    let mut prev_mode = 0u32;
    let proof = get_proof();

    // Run for fewer rounds than tau_d requires.
    let short_run_end = tau_d - 1;
    for t in 0..short_run_end {
        allocate(
            &OBJECT_REGISTRY,
            &LENS_REGISTRY,
            &LAMBDA,
            ETA,
            &parent,
            &mut weights,
            &payoffs,
            zeta,
            NonNegativeFixed::ZERO,
            &mu,
            &costs,
            t,
            &mut last_switch_t,
            &mut prev_mode,
            tau_d,
            CERTIFICATE_DIGEST,
            proof.as_ref(),
        )
        .unwrap_or_else(|e| panic!("allocate refused at t={t}: {e:?}"));
    }

    assert_eq!(
        prev_mode, 0,
        "dwell time never elapsed within the run (t < tau_d since last_switch_t=0), so the mode must still be locked at its original value"
    );
    assert_eq!(
        last_switch_t, 0,
        "last_switch_t must not have moved without an actual switch"
    );
}
