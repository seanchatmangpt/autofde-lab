//! Small stdin/stdout JSON CLI wrapping the real `allocator::allocate()`
//! (see `src/allocator/mod.rs`) over the `case_studies` fixture, so
//! out-of-process callers (e.g. a Python differential-judging bridge) can
//! obtain a real, deterministic reference allocation -- and, optionally, a
//! deliberately-tampered "claimed" allocation next to it -- without
//! reimplementing the allocator.
//!
//! Mirrors `bcinr-powl/src/bin/soundness_cli.rs`'s pattern: typed request/
//! response structs, an error envelope on stderr + exit 1, no
//! reimplementation of the underlying deterministic logic.

use std::collections::BTreeMap;
use std::io::{self, Read, Write};

use bcinr_cmca::allocator::allocate;
use bcinr_cmca::fixed::NonNegativeFixed;
use bcinr_cmca::generated::consequence_mass::case_studies::{
    ETA, LAMBDA, LENS_REGISTRY, N, OBJECT_REGISTRY, Q,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Deserialize)]
struct Tamper {
    index: usize,
    delta_millionths: i64,
}

#[derive(Debug, Deserialize)]
struct AllocateRequest {
    case: String,
    #[serde(default)]
    tamper: Option<Tamper>,
}

#[derive(Debug, Serialize)]
struct AllocateResponse {
    case: String,
    tampered: bool,
    reference_allocation: BTreeMap<String, f64>,
    claimed_allocation: BTreeMap<String, f64>,
}

/// Builds an error response envelope for a request that names an unknown
/// case, a tamper index out of range, or malformed JSON. Not part of the
/// happy-path wire schema above -- deliberately named `error` so it can't be
/// confused with a real `AllocateResponse` by a caller pattern-matching on
/// field presence.
fn error_envelope(message: String) -> Value {
    serde_json::json!({ "error": message })
}

/// Same fixed-point-to-f64 conversion idiom already used by
/// `tests/differential.rs`'s `to_f64` helper: `NonNegativeFixed` is Q16.16,
/// so dividing the raw `val` by `65536.0` recovers the real value.
fn to_f64(f: NonNegativeFixed) -> f64 {
    (f.val as f64) / 65536.0
}

fn run() -> Result<Value, String> {
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .map_err(|e| format!("failed to read stdin: {e}"))?;

    let request: AllocateRequest =
        serde_json::from_str(&input).map_err(|e| format!("invalid request JSON: {e}"))?;

    if request.case != "case_studies" {
        return Err(format!(
            "unsupported case {:?}: only \"case_studies\" is supported",
            request.case
        ));
    }

    // Flat parent tree, zero weights/payoffs baseline -- same pattern as
    // `tests/case_studies.rs`'s `test_case_study_1_cache_choice`.
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    let result = allocate(
        &OBJECT_REGISTRY,
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
        bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST,
        None,
    )
    .map_err(|e| format!("allocate() refused: {e:?}"))?;

    let reference_allocation: BTreeMap<String, f64> = result
        .iter()
        .enumerate()
        .map(|(i, share)| (i.to_string(), to_f64(*share)))
        .collect();

    let mut claimed_allocation = reference_allocation.clone();
    let tampered = request.tamper.is_some();
    if let Some(tamper) = request.tamper {
        let key = tamper.index.to_string();
        let current = claimed_allocation
            .get(&key)
            .copied()
            .ok_or_else(|| format!("tamper index {} out of range (N={})", tamper.index, N))?;
        claimed_allocation.insert(
            key,
            current + (tamper.delta_millionths as f64) / 1_000_000.0,
        );
    }

    let response = AllocateResponse {
        case: request.case,
        tampered,
        reference_allocation,
        claimed_allocation,
    };

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
