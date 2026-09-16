//! wasm32-wasip1 in-process transport for the canonical bcinr-cmca allocator.
//!
//! This crate is a thin ABI shim, not a reimplementation: the ranking logic
//! below is a line-for-line port of the vendored
//! `vendor/bcinr/crates/bcinr-cmca/src/bin/cmca_rank_cli.rs` (same request/
//! response JSON, same phantom padding, same factor pinning, same flat tree,
//! same `allocator::allocate` call), with the process boundary replaced by
//! three `extern "C"` exports so Python (via `wasmtime`) — and later any
//! WASM-capable host, including the BEAM via wasmex — can call the certified
//! Q16.16 kernel in-process instead of spawning a subprocess.
//!
//! It deliberately lives *outside* `vendor/bcinr`, whose crates are
//! byte-for-byte snapshots of upstream commit `2ae60cf0` (see
//! `vendor/bcinr/VENDORING.md`); adding a workspace member there would break
//! the verbatim provenance a Chicago test asserts.
//!
//! # ABI
//!
//! ```text
//! cmca_alloc(len: usize) -> *mut u8          // caller-owned buffer
//! cmca_free(ptr: *mut u8, len: usize)        // release a cmca_alloc buffer
//! cmca_rank_json(ptr: *const u8, len: usize) -> *mut u8
//!     // input:  UTF-8 request JSON (RankRequest below)
//!     // output: [u32 LE payload_len][payload bytes], freed with
//!     //         cmca_free(ptr, 4 + payload_len)
//! ```
//!
//! Refusals (too many candidates, malformed JSON, `allocate()` refusal) are
//! reported as an `{"error": ...}` JSON envelope in the output payload --
//! the same convention as the CLI's error envelope, so the Python bridge's
//! existing `"error" in payload` handling applies unchanged. A Rust panic
//! surfaces as a WASM trap in the host runtime instead.
//!
//! # Build
//!
//! ```bash
//! cargo build --release --target wasm32-wasip1 \
//!   --manifest-path wasm/bcinr-cmca-wasm/Cargo.toml
//! cp wasm/bcinr-cmca-wasm/target/wasm32-wasip1/release/bcinr_cmca_wasm.wasm \
//!   wasm/artifacts/
//! ```

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
/// (CMCA-108). Not a policy choice made by this shim.
const MAX_CANDIDATES: usize = N;

/// Number of caller-defined quality axes -- one per `case_studies` measure
/// slot. Fixed by the compiled fixture.
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

/// Same fixed-point idioms as `cmca_rank_cli.rs`: Q16.16 via `* / 65536.0`,
/// negative inputs clamped to 0 rather than wrapping through the unsigned
/// representation.
fn to_fixed(v: f64) -> NonNegativeFixed {
    let clamped = v.max(0.0);
    NonNegativeFixed::from_bits((clamped * 65536.0).round() as u32)
}

fn to_f64(f: NonNegativeFixed) -> f64 {
    (f.val as f64) / 65536.0
}

/// All-zero-measure padding candidate, identical to the CLI's: every measure
/// formula collapses to 0, so it absorbs a real but negligible share and is
/// excluded from the response by name.
fn phantom_state(id: usize) -> PackedSemanticState {
    PackedSemanticState {
        id: id as u32,
        factors: [NonNegativeFixed::ZERO; 10],
    }
}

/// Factors that collapse the four compiled measure formulas to exactly the
/// caller's `measures[0..4]` -- derivation in `cmca_rank_cli.rs`'s module
/// docs, which this port does not repeat or alter.
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

fn run(input: &str) -> Result<Value, String> {
    let request: RankRequest =
        serde_json::from_str(input).map_err(|e| format!("invalid request JSON: {e}"))?;

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
    // `cmca_rank_cli.rs` and `tests/case_studies.rs`'s flat fixtures.
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

/// Entry point: request JSON in, response-or-error-envelope JSON out.
fn rank_payload(input: &str) -> Value {
    match run(input) {
        Ok(value) => value,
        Err(message) => serde_json::json!({ "error": message }),
    }
}

#[no_mangle]
pub extern "C" fn cmca_alloc(len: usize) -> *mut u8 {
    let mut buf = Vec::<u8>::with_capacity(len);
    let ptr = buf.as_mut_ptr();
    core::mem::forget(buf);
    ptr
}

/// # Safety
/// `ptr` must originate from `cmca_alloc` with the same `len`, and each
/// buffer may be freed exactly once.
#[no_mangle]
pub unsafe extern "C" fn cmca_free(ptr: *mut u8, len: usize) {
    drop(Vec::from_raw_parts(ptr, 0, len));
}

/// # Safety
/// `ptr[..len]` must be a valid, initialized UTF-8 request. The returned
/// buffer is `[u32 LE payload_len][payload bytes]` and must be released with
/// `cmca_free(ret, 4 + payload_len)`.
#[no_mangle]
pub unsafe extern "C" fn cmca_rank_json(ptr: *const u8, len: usize) -> *mut u8 {
    let input = String::from_utf8_lossy(core::slice::from_raw_parts(ptr, len));
    let payload = rank_payload(&input).to_string();
    let mut out = Vec::with_capacity(4 + payload.len());
    out.extend_from_slice(&(payload.len() as u32).to_le_bytes());
    out.extend_from_slice(payload.as_bytes());
    let out_ptr = out.as_mut_ptr();
    core::mem::forget(out);
    out_ptr
}
