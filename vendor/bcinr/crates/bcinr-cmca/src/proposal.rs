//! # Mode-change proposal — Authority hop 1 of the C3 chain
//!
//! `ModeProposal` is the sealed output of the Observatory's lawful telemetry-evaluation
//! path (see `crate::observatory::evaluate_calibration`). It carries a proposed control
//! delta together with the digests and telemetry standing that admission must later
//! re-verify. It is never itself an admitted, shadow-executed, certified, or switch-ready
//! value — those are separate, later hops in `shadow.rs`, `certification.rs`, and
//! `mode_switch.rs`.
//!
//! Per `.claude/rules/30-authority-separation.md` and
//! `.claude/rules/cmca/authority-and-c3.md` Invariant 1, this module is the *only* place a
//! `ModeProposal` value can be constructed outside `#[cfg(test)]` fixtures. The Observatory
//! calls [`ModeProposal::propose`] (a `pub(crate)` constructor reachable only from within
//! this crate) but does not itself hold or expose a way to fabricate a proposal-shaped
//! value from arbitrary bytes.
//!
//! # Currently dead / uncompiled — not declared in `lib.rs`
//!
//! This module is **not** wired into the crate (`grep -rn "mod proposal" src/lib.rs`
//! returns nothing) and does not currently compile as part of `bcinr-cmca`. Evidence:
//!
//! - It imports `crate::observatory::ObservatoryFlagSet`, a bitset type that existed in an
//!   earlier revision of `observatory.rs` (commit `077e08a8`, "numeric fault-set and
//!   authority-chain closure for v26.7.17") but was later removed in favor of the single
//!   `ObservatoryFlag` enum this crate uses today. `ObservatoryFlagSet` no longer exists
//!   anywhere in this crate.
//! - It calls `SignedFixed::value_bits()`, a method that does not exist on
//!   `crate::fixed::SignedFixed` (which exposes `to_bits()`/`from_bits()` instead, per the
//!   `from_value_bits` -> `from_bits` rename in commit `7197c91f`, "Closure Ticket C1:
//!   Repair fixed-point semantics").
//!
//! `certification.rs`'s `use crate::proposal::mix64;` is *not* evidence this module is
//! live: `certification.rs` is itself undeclared in `lib.rs` and does not compile as part
//! of the crate either. Both files are orphaned code referencing orphaned code, left behind
//! by a real API refactor (the `ObservatoryFlagSet` removal) that this file never absorbed.
//! A future reader who wants to revive this authority hop must first reconcile its flag-set
//! API against the current `ObservatoryFlag` enum, not just re-add a `pub mod proposal;`
//! line to `lib.rs`.

use crate::fixed::SignedFixed;
use crate::observatory::ObservatoryFlagSet;

/// Deterministic 64-bit mixing function used to derive digests throughout the C3 chain.
///
/// This is not a cryptographic hash. It is a fixed, branchless, allocation-free avalanche
/// mix (SplitMix64-style) adequate for binding identity fields together for equality
/// checking inside the authoritative hot path. Slow-rail code that needs cryptographic
/// binding (BLAKE3 receipts) lives elsewhere (`bcinr-powl (receipt module)`); nothing here claims
/// cryptographic collision resistance.
#[inline(always)]
pub(crate) fn mix64(a: u64, b: u64) -> u64 {
    let mut x = a ^ b.wrapping_mul(0x9E37_79B9_7F4A_7C15);
    x ^= x >> 30;
    x = x.wrapping_mul(0xBF58_476D_1CE4_E5B9);
    x ^= x >> 27;
    x = x.wrapping_mul(0x94D0_49BB_1331_11EB);
    x ^= x >> 31;
    x
}

/// Refusal reasons for [`admit_proposal`].
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum ProposalRefusal {
    /// The recomputed proposal digest does not match the digest sealed at proposal time —
    /// the proposal was tampered with or corrupted in transit.
    ProposalDigestMismatch,
    /// The caller-supplied round identity does not match the round the proposal was made
    /// for.
    ///
    /// This is one of two owning realizations of `allocator::RefusalSet::ROUND_MISMATCH`
    /// (the other is `certification::CertificationRefusal::RoundIdentityMismatch`) —
    /// `allocate()` never constructs that bit itself; see
    /// `REFUSAL_REALIZATION_REPORT.md` for the full reconciliation.
    RoundIdentityMismatch,
    /// The caller-supplied current-mode digest does not match the mode the proposal was
    /// computed against — the world moved on since the proposal was formed.
    CurrentModeDigestMismatch,
    /// The proposed control delta falls outside the caller's supported bound.
    UnsupportedDelta,
    /// The telemetry standing captured in the proposal's flag set blocks admission (any
    /// flag other than `RECERTIFICATION_SUGGESTED` is set).
    TelemetryStandingBlocked,
}

/// A sealed proposal for a control-mode transition, produced only by the Observatory's
/// lawful evaluation path.
///
/// All fields are private. There is exactly one production constructor,
/// [`ModeProposal::propose`], which is `pub(crate)` — reachable only from within
/// `bcinr-cmca`, and in practice only called from `crate::observatory`. A `cfg(test)`
/// fixture constructor is provided for unit tests of downstream stages so they do not need
/// to reconstruct a full Observatory evaluation to exercise `admit_proposal`.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct ModeProposal {
    proposed_control_delta: SignedFixed,
    observation_digest: u64,
    current_mode_digest: u64,
    round_identity: u64,
    flags: ObservatoryFlagSet,
    proposal_digest: u64,
}

impl ModeProposal {
    /// The sole production constructor. `pub(crate)` — only callable from within this
    /// crate (the Observatory's evaluation path).
    #[inline(always)]
    pub(crate) fn propose(
        proposed_control_delta: SignedFixed,
        observation_digest: u64,
        current_mode_digest: u64,
        round_identity: u64,
        flags: ObservatoryFlagSet,
    ) -> Self {
        let proposal_digest = Self::seal(
            proposed_control_delta,
            observation_digest,
            current_mode_digest,
            round_identity,
            flags,
        );
        Self {
            proposed_control_delta,
            observation_digest,
            current_mode_digest,
            round_identity,
            flags,
            proposal_digest,
        }
    }

    /// Test-only fixture constructor for exercising downstream stages (`admit_proposal`,
    /// `shadow`, `jump`, `stability`, `certification`) without driving a full Observatory
    /// evaluation. Not reachable outside `#[cfg(test)]` builds.
    #[cfg(test)]
    pub fn test_fixture(
        proposed_control_delta: SignedFixed,
        observation_digest: u64,
        current_mode_digest: u64,
        round_identity: u64,
        flags: ObservatoryFlagSet,
    ) -> Self {
        Self::propose(
            proposed_control_delta,
            observation_digest,
            current_mode_digest,
            round_identity,
            flags,
        )
    }

    #[inline(always)]
    fn seal(
        proposed_control_delta: SignedFixed,
        observation_digest: u64,
        current_mode_digest: u64,
        round_identity: u64,
        flags: ObservatoryFlagSet,
    ) -> u64 {
        let mut d = mix64(
            proposed_control_delta.value_bits() as u64,
            observation_digest,
        );
        d = mix64(d, current_mode_digest);
        d = mix64(d, round_identity);
        d = mix64(d, flags.bits() as u64);
        d
    }

    #[inline(always)]
    pub fn proposed_control_delta(&self) -> SignedFixed {
        self.proposed_control_delta
    }

    #[inline(always)]
    pub fn observation_digest(&self) -> u64 {
        self.observation_digest
    }

    #[inline(always)]
    pub fn current_mode_digest(&self) -> u64 {
        self.current_mode_digest
    }

    #[inline(always)]
    pub fn round_identity(&self) -> u64 {
        self.round_identity
    }

    #[inline(always)]
    pub fn flags(&self) -> ObservatoryFlagSet {
        self.flags
    }

    #[inline(always)]
    pub fn proposal_digest(&self) -> u64 {
        self.proposal_digest
    }
}

/// A sealed proof that a [`ModeProposal`] was admitted: its digest, round identity,
/// current-mode digest, delta bound, and telemetry standing were all independently
/// re-verified against caller-supplied expectations.
///
/// Constructible only via [`admit_proposal`].
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct AdmittedProposal {
    pub(crate) proposal: ModeProposal,
}

impl AdmittedProposal {
    #[inline(always)]
    pub fn proposal(&self) -> &ModeProposal {
        &self.proposal
    }
}

/// Admits a [`ModeProposal`] by independently re-verifying every binding it claims to
/// carry: proposal digest integrity, round identity, current-mode digest, supported delta
/// bound, and telemetry standing.
///
/// Any single mismatch refuses; there is no partial admission.
pub fn admit_proposal(
    proposal: ModeProposal,
    expected_round_identity: u64,
    expected_current_mode_digest: u64,
    max_supported_delta: SignedFixed,
) -> Result<AdmittedProposal, ProposalRefusal> {
    let recomputed = ModeProposal::seal(
        proposal.proposed_control_delta,
        proposal.observation_digest,
        proposal.current_mode_digest,
        proposal.round_identity,
        proposal.flags,
    );
    if recomputed != proposal.proposal_digest {
        return Err(ProposalRefusal::ProposalDigestMismatch);
    }
    if proposal.round_identity != expected_round_identity {
        return Err(ProposalRefusal::RoundIdentityMismatch);
    }
    if proposal.current_mode_digest != expected_current_mode_digest {
        return Err(ProposalRefusal::CurrentModeDigestMismatch);
    }
    if proposal.proposed_control_delta.value_bits().unsigned_abs()
        > max_supported_delta.value_bits().unsigned_abs()
    {
        return Err(ProposalRefusal::UnsupportedDelta);
    }
    if !proposal.flags.telemetry_admissible() {
        return Err(ProposalRefusal::TelemetryStandingBlocked);
    }
    Ok(AdmittedProposal { proposal })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::observatory::ObservatoryFlag;

    fn clean_flags() -> ObservatoryFlagSet {
        ObservatoryFlagSet::EMPTY.insert(ObservatoryFlag::RecertificationCandidate)
    }

    fn base_proposal() -> ModeProposal {
        ModeProposal::test_fixture(SignedFixed::from_bits(10), 1, 2, 3, clean_flags())
    }

    #[test]
    fn admits_when_every_binding_matches() {
        let p = base_proposal();
        let admitted = admit_proposal(p, 3, 2, SignedFixed::from_bits(100));
        assert!(admitted.is_ok());
    }

    #[test]
    fn refuses_on_digest_tamper() {
        let mut p = base_proposal();
        p.proposal_digest ^= 1; // simulate corruption in transit
        assert_eq!(
            admit_proposal(p, 3, 2, SignedFixed::from_bits(100)),
            Err(ProposalRefusal::ProposalDigestMismatch)
        );
    }

    #[test]
    fn refuses_on_round_mismatch() {
        let p = base_proposal();
        assert_eq!(
            admit_proposal(p, 999, 2, SignedFixed::from_bits(100)),
            Err(ProposalRefusal::RoundIdentityMismatch)
        );
    }

    #[test]
    fn refuses_on_current_mode_digest_mismatch() {
        let p = base_proposal();
        assert_eq!(
            admit_proposal(p, 3, 999, SignedFixed::from_bits(100)),
            Err(ProposalRefusal::CurrentModeDigestMismatch)
        );
    }

    #[test]
    fn refuses_on_unsupported_delta() {
        let p = base_proposal();
        assert_eq!(
            admit_proposal(p, 3, 2, SignedFixed::from_bits(1)),
            Err(ProposalRefusal::UnsupportedDelta)
        );
    }

    #[test]
    fn refuses_on_blocked_telemetry_standing() {
        let bad_flags = ObservatoryFlagSet::EMPTY.insert(ObservatoryFlag::Drifting);
        let p = ModeProposal::test_fixture(SignedFixed::from_bits(10), 1, 2, 3, bad_flags);
        assert_eq!(
            admit_proposal(p, 3, 2, SignedFixed::from_bits(100)),
            Err(ProposalRefusal::TelemetryStandingBlocked)
        );
    }

    #[test]
    fn cannot_construct_admitted_proposal_except_via_admit_proposal() {
        // Compile-time property: AdmittedProposal has no public constructor other than
        // `admit_proposal`. This test documents the property by using only the public API.
        let p = base_proposal();
        let admitted = admit_proposal(p, 3, 2, SignedFixed::from_bits(100)).unwrap();
        assert_eq!(admitted.proposal().round_identity(), 3);
    }
}
