//! Small stdin/stdout JSON CLI wrapping the real `allocator::allocate()`
//! (see `src/allocator/mod.rs`) as a **general N-candidate multi-criteria
//! ranking entry point**, so out-of-process callers (e.g. autofde-lab's
//! `match_solvers(ranked=True)` gap) can rank arbitrary candidate data by
//! the compiled `case_studies` lens-weighting policy (`LENS_REGISTRY`,
//! `LAMBDA`, `ETA`) without reimplementing the allocator, and without being
//! stuck on `cmca_allocate_cli`'s single fixed fixture.
//!
//! Mirrors `cmca_allocate_cli.rs`'s and `bcinr-powl/src/bin/soundness_cli.rs`'s
//! pattern: typed request/response structs, an error envelope on stderr +
//! exit 1, no reimplementation of the underlying deterministic logic.
//!
//! # This is a semantic reinterpretation of a fixture built for a different domain
//!
//! `case_studies` is compiled for a fixed shape: `N = 8` objects, `K = 4`
//! measures (`MeasureCache`, `MeasureSearch`, `MeasureRetrieval`,
//! `MeasureScheduling`), `Q = 4` lenses (see CMCA-108:
//! `allocate`/`allocate_single_lens` are hard-locked to this crate's own
//! compile-time `N`/`K`/`Q`, not generic — a genuinely const-generic
//! rewrite was scoped and deferred as future work, not attempted here).
//! Rather than fork or regenerate the crate, this CLI **honestly
//! reinterprets** those 4 already-compiled measure slots as 4 independent,
//! caller-defined quality axes for whatever ranking problem the caller
//! actually has -- e.g. autofde-lab's solver-ranking heuristic might send
//! `[domain_match_confidence, inverse_cost, historical_success_rate,
//! robustness_score]`. The `MeasureCache`/`Search`/`Retrieval`/`Scheduling`
//! *names* are an artifact of the compiled fixture, not a claim that this
//! CLI's candidates are caches, searches, retrievals, or scheduling
//! decisions.
//!
//! ## How each `measures[i]` becomes that measure's `node_masses` entry
//!
//! Each measure's `node_masses[k][i]` is computed by
//! `allocator::allocate`'s private kernel from several `PackedSemanticState`
//! factors via fixed, nonlinear formulas (not accepted as a single scalar
//! directly) -- see `allocator/mod.rs`'s `m_cache`/`m_search`/
//! `m_retrieval`/`m_sched` formulas. This CLI picks factor values that
//! collapse each formula back down to exactly the caller's scalar:
//!
//! - `MeasureCache` = `(recomputationCost * 5 + verificationCost) *
//!   accessFrequency * standing`. Setting `accessFrequency = standing = 1`,
//!   `verificationCost = 0`, `recomputationCost = measures[0] / 5` yields
//!   `MeasureCache = measures[0]` exactly (modulo fixed-point rounding).
//! - `MeasureSearch` = `(businessValue + downstreamConsequence) *
//!   searchDemand * standing`. Setting `businessValue = standing = 1`,
//!   `downstreamConsequence = 0`, `searchDemand = measures[1]` yields
//!   `MeasureSearch = measures[1]`.
//! - `MeasureRetrieval` = `businessValue * retrievalDemand`. With
//!   `businessValue = 1` (already fixed above) and `retrievalDemand =
//!   measures[2]`, `MeasureRetrieval = measures[2]`.
//! - `MeasureScheduling` = `businessValue * schedulingDemand`. With
//!   `businessValue = 1` and `schedulingDemand = measures[3]`,
//!   `MeasureScheduling = measures[3]`.
//!
//! `businessValue` and `standing` are shared across more than one measure
//! formula, which is why they are pinned to `1` (the multiplicative
//! identity) rather than driven by any one `measures[i]` -- pinning them
//! is what makes all four measures independently controllable from the
//! caller's 4 scalars.
//!
//! Every other factor (`validity`, unused slots) is left at `0`, since
//! none of the four measure formulas above reference them.
//!
//! ## Expected input range
//!
//! `measures[i]` are assumed to already be normalized/scaled sensibly by
//! the caller (non-negative; roughly `0.0..1000.0` is the domain the
//! allocator's own reference oracle clamps `node_masses` into, see
//! `tests/reference.rs`). Negative inputs are clamped to `0.0` rather than
//! wrapping through fixed-point's unsigned representation.
//!
//! # Padding and the >8 candidate limit
//!
//! `allocate` is compiled for exactly `N = 8` objects (see CMCA-108). Fewer
//! than 8 real candidates are padded with explicit, documented **phantom
//! candidates** -- `PackedSemanticState`s with all factors `0`, which
//! collapse every measure formula to `0` and therefore receive a real but
//! negligible allocation share, excluded from the response. More than 8
//! real candidates is refused with a typed error rather than silently
//! truncated -- there is no correct way to drop a caller's candidate
//! without their knowledge.
//!
//! # Flat tree
//!
//! Candidates are siblings, not a hierarchy: `parent = [-1; N]`, the same
//! flat-tree pattern `tests/case_studies.rs`'s case-study-1/2 fixtures and
//! `cmca_allocate_cli.rs` already use for non-hierarchical inputs. This is
//! a real, correct application of `allocate()`'s existing flat-tree
//! support, not a workaround.

use std::io::{self, Read, Write};

use bcinr_cmca::allocator::allocate;
use bcinr_cmca::fixed::NonNegativeFixed;
use bcinr_cmca::generated::consequence_mass::case_studies::{
    PackedSemanticState, ETA, FACTOR_ACCESS_FREQUENCY, FACTOR_BUSINESS_VALUE,
    FACTOR_DOWNSTREAM_CONSEQUENCE, FACTOR_RECOMPUTATION_COST, FACTOR_RETRIEVAL_DEMAND,
    FACTOR_SCHEDULING_DEMAND, FACTOR_SEARCH_DEMAND, FACTOR_STANDING, FACTOR_VERIFICATION_COST,
    LAMBDA, LENS_REGISTRY, N, Q,
};
use bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST;
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Real hard limit: `allocate()` is compiled for exactly `N = 8` objects
/// (CMCA-108, see module doc comment above). Not a policy choice made by
/// this CLI.
const MAX_CANDIDATES: usize = N;

/// Number of independent quality axes this CLI exposes -- one per
/// `case_studies` measure slot (`MeasureCache`/`Search`/`Retrieval`/
/// `Scheduling`). Fixed by the compiled fixture, see module doc comment.
const NUM_MEASURES: usize = 4;

#[derive(Debug, Deserialize)]
struct Candidate {
    name: String,
    measures: [f64; NUM_MEASURES],
}

#[derive(Debug, Deserialize)]
struct RankRequest {
    candidates: Vec<Candidate>,
}

#[derive(Debug, Serialize)]
struct RankedCandidate {
    name: String,
    share: f64,
}

#[derive(Debug, Serialize)]
struct RankResponse {
    ranking: Vec<RankedCandidate>,
}

/// Builds an error response envelope for a request with too many
/// candidates or malformed JSON. Deliberately named `error` so it can't be
/// confused with a real `RankResponse` by a caller pattern-matching on
/// field presence -- same convention as `cmca_allocate_cli.rs`.
fn error_envelope(message: String) -> Value {
    serde_json::json!({ "error": message })
}

/// Same fixed-point-to-f64 conversion idiom `cmca_allocate_cli.rs`'s
/// `to_f64` and `tests/differential.rs`'s `to_fixed`/`to_f64` helpers use:
/// `NonNegativeFixed` is Q16.16, so multiplying/dividing the raw value by
/// `65536.0` converts to/from `f64`.
fn to_fixed(v: f64) -> NonNegativeFixed {
    // Clamp negative inputs to 0 rather than wrapping through the
    // unsigned representation -- see module doc comment's "Expected input
    // range".
    let clamped = v.max(0.0);
    NonNegativeFixed::from_bits((clamped * 65536.0).round() as u32)
}

fn to_f64(f: NonNegativeFixed) -> f64 {
    (f.val as f64) / 65536.0
}

/// A candidate with all-zero measures, used to pad requests with fewer
/// than `N` real candidates up to the compiled `N = 8` shape `allocate()`
/// requires. Every measure formula (see module doc comment) collapses to
/// `0` when its driving factors are `0`, so a phantom candidate receives a
/// real but negligible share and is excluded from the response by name
/// (phantom names are never returned).
fn phantom_state(id: usize) -> PackedSemanticState {
    PackedSemanticState {
        id: id as u32,
        factors: [NonNegativeFixed::ZERO; 10],
    }
}

/// Builds the `PackedSemanticState` that makes `case_studies`'s 4 measure
/// formulas collapse to exactly `measures[0..4]` -- see the module doc
/// comment's "How each `measures[i]` becomes that measure's `node_masses`
/// entry" section for the derivation.
fn state_from_measures(id: usize, measures: &[f64; NUM_MEASURES]) -> PackedSemanticState {
    let mut factors = [NonNegativeFixed::ZERO; 10];
    factors[FACTOR_ACCESS_FREQUENCY] = NonNegativeFixed::ONE;
    factors[FACTOR_STANDING] = NonNegativeFixed::ONE;
    factors[FACTOR_VERIFICATION_COST] = NonNegativeFixed::ZERO;
    factors[FACTOR_RECOMPUTATION_COST] = to_fixed(measures[0]) / NonNegativeFixed::from_num(5);
    factors[FACTOR_BUSINESS_VALUE] = NonNegativeFixed::ONE;
    factors[FACTOR_DOWNSTREAM_CONSEQUENCE] = NonNegativeFixed::ZERO;
    factors[FACTOR_SEARCH_DEMAND] = to_fixed(measures[1]);
    factors[FACTOR_RETRIEVAL_DEMAND] = to_fixed(measures[2]);
    factors[FACTOR_SCHEDULING_DEMAND] = to_fixed(measures[3]);

    PackedSemanticState {
        id: id as u32,
        factors,
    }
}

fn run() -> Result<Value, String> {
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .map_err(|e| format!("failed to read stdin: {e}"))?;

    let request: RankRequest =
        serde_json::from_str(&input).map_err(|e| format!("invalid request JSON: {e}"))?;

    if request.candidates.len() > MAX_CANDIDATES {
        return Err(format!(
            "too many candidates: got {}, allocate() is compiled for at most N={} (CMCA-108)",
            request.candidates.len(),
            MAX_CANDIDATES
        ));
    }
    if request.candidates.is_empty() {
        return Err("no candidates provided".to_string());
    }

    let mut states: [PackedSemanticState; N] = core::array::from_fn(phantom_state);
    let mut real_names: Vec<String> = Vec::with_capacity(request.candidates.len());
    for (i, candidate) in request.candidates.iter().enumerate() {
        states[i] = state_from_measures(i, &candidate.measures);
        real_names.push(candidate.name.clone());
    }

    // Flat parent tree, zero weights/payoffs baseline -- same pattern as
    // `cmca_allocate_cli.rs` and `tests/case_studies.rs`'s flat fixtures.
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    let result = allocate(
        &states,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        None,
    )
    .map_err(|e| format!("allocate() refused: {e:?}"))?;

    let mut ranking: Vec<RankedCandidate> = real_names
        .iter()
        .enumerate()
        .map(|(i, name)| RankedCandidate {
            name: name.clone(),
            share: to_f64(result[i]),
        })
        .collect();
    ranking.sort_by(|a, b| b.share.total_cmp(&a.share));

    let response = RankResponse { ranking };

    serde_json::to_value(response).map_err(|e| format!("failed to serialize response: {e}"))
}

fn main() {
    match run() {
        Ok(value) => {
            println!("{value}");
        }
        Err(message) => {
            let stderr = io::stderr();
            let mut handle = stderr.lock();
            let _ = writeln!(handle, "{}", error_envelope(message));
            std::process::exit(1);
        }
    }
}
