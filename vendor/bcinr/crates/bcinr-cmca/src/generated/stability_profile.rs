// STABILITY PROFILE
// Expanded Stochastic Homeostasis Envelope
//
// CMCA-113: despite the filename and this file's original "GENERATED"
// header, `PROFILE` below is hand-written -- CMCA-105 confirmed this file
// has zero ontology/generator coverage (present hand-authored since the
// crate's first commit). Every field is documented below with its real
// provenance, following the same POLICY (owner: ...) / DERIVED / MEASURED
// convention `crates/bcinr-cmca/src/generated_profile.rs` already uses for
// its hand-authored constants. A constant marked `POLICY` here is an
// intentional, load-bearing choice by the named owner, not a derived
// mathematical fact -- consult that owner before changing it for
// production tuning. A constant marked `ARBITRARY` has no known rationale
// at all and should not be treated as validated; it is named explicitly so
// nobody mistakes silence for derivation.
//
// `gain_matrix` / `weight_vector` / `deterministic_margin` are not
// independent: `allocator::mod.rs`'s `allocate_in` enforces, for every row
// `i`, the diagonal-dominance / contraction inequality
//   sum_j gain_matrix[i][j] * weight_vector[j]
//     <= weight_vector[i] * (1 - deterministic_margin)
// (all terms in the 1e9-scaled fixed representation these constants use).
// `tests/stability_profile_invariants.rs` checks this inequality directly
// against the live `PROFILE` constants so an edit that breaks it fails CI
// instead of silently shipping a `StabilityRefusal::GainMatrixUnsafe` that
// nobody predicted.

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct NonNegativeFixed {
    pub raw: u64,
}

impl NonNegativeFixed {
    pub const fn from_raw(raw: u64) -> Self {
        Self { raw }
    }
}

pub type Digest = [u8; 32];

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct StabilityProfile {
    /// POLICY (owner: bcinr-cmca::allocator). Together with `weight_vector`
    /// and `deterministic_margin`, must satisfy the contraction inequality
    /// documented on this module's header comment for every row. Not
    /// independently arbitrary -- edit all three together and re-run
    /// `tests/stability_profile_invariants.rs` before shipping a change.
    pub gain_matrix: [[NonNegativeFixed; 5]; 5],
    /// POLICY (owner: bcinr-cmca::allocator). See `gain_matrix`.
    pub weight_vector: [NonNegativeFixed; 5],
    /// POLICY (owner: bcinr-cmca::allocator). The contraction margin
    /// (fraction, 1e9-scaled) in the inequality documented on `gain_matrix`.
    /// See `gain_matrix`.
    pub deterministic_margin: NonNegativeFixed,

    /// ARBITRARY. No stated formula or named-owner rationale found for
    /// these five per-measure bounds; flagged by CMCA-113 for replacement
    /// or a real derivation before production tuning depends on them.
    pub noise_second_moment_bounds: [NonNegativeFixed; 5],
    /// ARBITRARY. No stated formula or named-owner rationale found; flagged
    /// by CMCA-113 for replacement or a real derivation before production
    /// tuning depends on it.
    pub certified_noise_radius: NonNegativeFixed,

    /// ARBITRARY. No stated formula or named-owner rationale found; flagged
    /// by CMCA-113 for replacement or a real derivation before production
    /// tuning depends on it.
    pub mode_jump_bound: NonNegativeFixed,
    /// POLICY (owner: bcinr-cmca::allocator). Gates
    /// `StabilityRefusal::DwellTimeViolation` in `allocate_in` (mod.rs) --
    /// `tau_d < minimum_dwell_rounds` refuses a mode switch. The value 461
    /// itself has no derivation on record; it is an operator policy choice,
    /// not a mathematical consequence of the other constants in this file.
    /// CMCA-113 could not locate a formula or named owner for the specific
    /// number 461 -- treat any change as a fresh policy decision, not a
    /// tweak to an existing derivation.
    pub minimum_dwell_rounds: u32,
    /// ARBITRARY. No stated formula or named-owner rationale found; flagged
    /// by CMCA-113 for replacement or a real derivation before production
    /// tuning depends on it.
    pub certified_switching_radius: NonNegativeFixed,

    /// ARBITRARY. No stated formula or named-owner rationale found; flagged
    /// by CMCA-113 for replacement or a real derivation before production
    /// tuning depends on it.
    pub total_homeostatic_radius: NonNegativeFixed,

    /// ARBITRARY. No stated formula or named-owner rationale found; flagged
    /// by CMCA-113 for replacement or a real derivation before production
    /// tuning depends on it.
    pub temperature_ceiling: NonNegativeFixed,
    /// ARBITRARY. No stated formula or named-owner rationale found; flagged
    /// by CMCA-113 for replacement or a real derivation before production
    /// tuning depends on it. Aliased as `ETA_G_MIN` below.
    pub distinguishability_floor: NonNegativeFixed,
    /// ARBITRARY. No stated formula or named-owner rationale found; flagged
    /// by CMCA-113 for replacement or a real derivation before production
    /// tuning depends on it.
    pub floor_minimum: NonNegativeFixed,

    /// POLICY (owner: bcinr-cmca::allocator). NOT a cryptographic secret and
    /// NOT currently a real authorization boundary: `allocate_in` (mod.rs)
    /// compares the caller-supplied `digest` argument byte-for-byte against
    /// this same public constant, which any in-process or downstream caller
    /// can import directly from `bcinr_cmca::generated::stability_profile`
    /// (as this crate's own doctest and `allocation_receipt.rs`'s tests
    /// already do) -- so today this is a same-crate round-trip
    /// self-consistency check, not proof of anything about the caller.
    /// There is no rotation process and no derivation formula for these 32
    /// bytes; CMCA-113 could not confirm any provenance for the literal
    /// value. Building a real, caller-independent authorization mechanism
    /// (so a fabricated digest cannot simply be re-imported from this same
    /// constant) is out of this ticket's scope -- see CMCA-114, which
    /// tracks the sibling finding that the surrounding "certified" proof
    /// chain accepts unvalidated `Self { .. }` construction the same way.
    pub certificate_digest: Digest,
}

pub const PROFILE: StabilityProfile = StabilityProfile {
    gain_matrix: [
        [
            NonNegativeFixed::from_raw(800_000_000),
            NonNegativeFixed::from_raw(10_000_000),
            NonNegativeFixed::from_raw(5_000_000),
            NonNegativeFixed::from_raw(2_000_000),
            NonNegativeFixed::from_raw(1_000_000),
        ],
        [
            NonNegativeFixed::from_raw(10_000_000),
            NonNegativeFixed::from_raw(850_000_000),
            NonNegativeFixed::from_raw(8_000_000),
            NonNegativeFixed::from_raw(3_000_000),
            NonNegativeFixed::from_raw(2_000_000),
        ],
        [
            NonNegativeFixed::from_raw(5_000_000),
            NonNegativeFixed::from_raw(8_000_000),
            NonNegativeFixed::from_raw(900_000_000),
            NonNegativeFixed::from_raw(4_000_000),
            NonNegativeFixed::from_raw(1_000_000),
        ],
        [
            NonNegativeFixed::from_raw(1_000_000),
            NonNegativeFixed::from_raw(2_000_000),
            NonNegativeFixed::from_raw(3_000_000),
            NonNegativeFixed::from_raw(950_000_000),
            NonNegativeFixed::from_raw(1_000_000),
        ],
        [
            NonNegativeFixed::from_raw(1_000_000),
            NonNegativeFixed::from_raw(1_000_000),
            NonNegativeFixed::from_raw(1_000_000),
            NonNegativeFixed::from_raw(1_000_000),
            NonNegativeFixed::from_raw(980_000_000),
        ],
    ],
    weight_vector: [
        NonNegativeFixed::from_raw(1_000_000_000),
        NonNegativeFixed::from_raw(1_200_000_000),
        NonNegativeFixed::from_raw(1_500_000_000),
        NonNegativeFixed::from_raw(800_000_000),
        NonNegativeFixed::from_raw(500_000_000),
    ],
    deterministic_margin: NonNegativeFixed::from_raw(10_000_000),

    noise_second_moment_bounds: [
        NonNegativeFixed::from_raw(1_000_000),
        NonNegativeFixed::from_raw(1_200_000),
        NonNegativeFixed::from_raw(800_000),
        NonNegativeFixed::from_raw(2_500_000),
        NonNegativeFixed::from_raw(3_000_000),
    ],
    certified_noise_radius: NonNegativeFixed::from_raw(45_000_000),

    mode_jump_bound: NonNegativeFixed::from_raw(200_000_000),
    minimum_dwell_rounds: 461,
    certified_switching_radius: NonNegativeFixed::from_raw(75_000_000),

    total_homeostatic_radius: NonNegativeFixed::from_raw(120_000_000),

    temperature_ceiling: NonNegativeFixed::from_raw(5_000_000_000),
    distinguishability_floor: NonNegativeFixed::from_raw(1_000_000),
    floor_minimum: NonNegativeFixed::from_raw(5_000_000),

    certificate_digest: [
        0x2c, 0xf2, 0x4d, 0xba, 0x5f, 0xb0, 0xa3, 0x0e, 0x26, 0xe8, 0x3b, 0x2a, 0xc5, 0xb9, 0xe2,
        0x9e, 0x1b, 0x16, 0x1e, 0x5c, 0x1f, 0xa7, 0x42, 0x5e, 0x73, 0x04, 0x33, 0x62, 0x93, 0x8b,
        0x98, 0x24,
    ],
};

// Aliases for compatibility with the allocator implementation:
pub const GAIN_MATRIX: [[NonNegativeFixed; 5]; 5] = PROFILE.gain_matrix;
pub const WEIGHT_VECTOR: [NonNegativeFixed; 5] = PROFILE.weight_vector;
pub const CONTRACTION_MARGIN: NonNegativeFixed = PROFILE.deterministic_margin;
pub const CERTIFICATE_DIGEST: Digest = PROFILE.certificate_digest;
pub const MODE_DWELL_ROUNDS_MIN: u32 = PROFILE.minimum_dwell_rounds;

pub const BETA_M_MAX: NonNegativeFixed = PROFILE.certified_noise_radius; // 45_000_000
pub const ZETA_W_MAX: NonNegativeFixed = NonNegativeFixed::from_raw(12_500_000); // 0.0125
pub const ETA_G_MIN: NonNegativeFixed = PROFILE.distinguishability_floor; // 1_000_000
