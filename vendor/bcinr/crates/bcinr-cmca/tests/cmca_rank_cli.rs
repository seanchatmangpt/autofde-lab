//! Integration tests for `src/bin/cmca_rank_cli.rs`: real process
//! invocation of the built binary via `std::process::Command`, real stdin
//! JSON in, real stdout JSON out. No mocking of `allocate()` -- these
//! assert on the actual deterministic ranking the real
//! `allocator::allocate()` produces, mirroring
//! `tests/cmca_allocate_cli.rs`'s pattern.

use std::io::Write;
use std::process::{Command, Stdio};

use serde_json::Value;

fn run_cli(request: &Value) -> std::process::Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_cmca_rank_cli"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("failed to spawn cmca_rank_cli binary");

    child
        .stdin
        .take()
        .expect("child stdin")
        .write_all(request.to_string().as_bytes())
        .expect("write request to stdin");

    child.wait_with_output().expect("wait for child")
}

fn run_cli_ok(request: &Value) -> Value {
    let output = run_cli(request);
    assert!(
        output.status.success(),
        "cmca_rank_cli exited non-zero; stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).expect("stdout is valid JSON")
}

#[test]
fn a_dominant_candidate_ranks_first() {
    // "dominant" beats both other candidates on all 4 measure axes --
    // it must rank strictly first, and every candidate must appear
    // (padding/phantom candidates never do, since none were needed here).
    let request = serde_json::json!({
        "candidates": [
            { "name": "dominant", "measures": [100.0, 100.0, 100.0, 100.0] },
            { "name": "weak_a", "measures": [1.0, 1.0, 1.0, 1.0] },
            { "name": "weak_b", "measures": [2.0, 2.0, 2.0, 2.0] },
        ]
    });
    let response = run_cli_ok(&request);

    let ranking = response["ranking"].as_array().expect("ranking is array");
    assert_eq!(
        ranking.len(),
        3,
        "all 3 real candidates must appear, no phantoms"
    );

    let names: Vec<&str> = ranking
        .iter()
        .map(|c| c["name"].as_str().unwrap())
        .collect();
    assert_eq!(
        names[0], "dominant",
        "the all-axis-dominant candidate must rank first, got order {names:?}"
    );

    // Shares must be a valid, non-negative, descending-sorted probability-
    // like distribution.
    let shares: Vec<f64> = ranking
        .iter()
        .map(|c| c["share"].as_f64().unwrap())
        .collect();
    for w in shares.windows(2) {
        assert!(
            w[0] >= w[1],
            "ranking must be sorted by share descending, got {shares:?}"
        );
    }
    for s in &shares {
        assert!(
            s.is_finite() && *s >= 0.0,
            "share must be finite and non-negative, got {s}"
        );
    }
    assert!(
        shares[0] > shares[1] && shares[0] > shares[2],
        "dominant candidate's share must strictly exceed both weaker candidates"
    );
}

#[test]
fn fewer_than_eight_candidates_are_padded_and_phantoms_are_excluded() {
    // Only 3 real candidates sent; the CLI must internally pad to N=8 with
    // phantom (all-zero) candidates to satisfy allocate()'s fixed shape,
    // but the response must contain exactly the 3 real names -- no
    // phantom entries leak through.
    let request = serde_json::json!({
        "candidates": [
            { "name": "alpha", "measures": [5.0, 5.0, 5.0, 5.0] },
            { "name": "beta", "measures": [3.0, 3.0, 3.0, 3.0] },
            { "name": "gamma", "measures": [1.0, 1.0, 1.0, 1.0] },
        ]
    });
    let response = run_cli_ok(&request);

    let ranking = response["ranking"].as_array().expect("ranking is array");
    assert_eq!(
        ranking.len(),
        3,
        "exactly the 3 real candidates, no phantoms"
    );

    let mut names: Vec<&str> = ranking
        .iter()
        .map(|c| c["name"].as_str().unwrap())
        .collect();
    names.sort_unstable();
    assert_eq!(names, vec!["alpha", "beta", "gamma"]);
}

#[test]
fn eight_real_candidates_all_appear() {
    let candidates: Vec<Value> = (0..8)
        .map(|i| {
            serde_json::json!({
                "name": format!("c{i}"),
                "measures": [1.0 + i as f64, 1.0, 1.0, 1.0]
            })
        })
        .collect();
    let request = serde_json::json!({ "candidates": candidates });
    let response = run_cli_ok(&request);

    let ranking = response["ranking"].as_array().expect("ranking is array");
    assert_eq!(
        ranking.len(),
        8,
        "all 8 real candidates must appear (N=8 exactly, no padding)"
    );

    let names: Vec<&str> = ranking
        .iter()
        .map(|c| c["name"].as_str().unwrap())
        .collect();
    assert_eq!(
        names[0], "c7",
        "c7 has the highest cache measure (1.0 + 7 = 8.0) and must rank first, got {names:?}"
    );
}

#[test]
fn more_than_eight_candidates_is_refused_with_typed_error_not_a_panic() {
    let candidates: Vec<Value> = (0..9)
        .map(|i| {
            serde_json::json!({
                "name": format!("c{i}"),
                "measures": [1.0, 1.0, 1.0, 1.0]
            })
        })
        .collect();
    let request = serde_json::json!({ "candidates": candidates });
    let output = run_cli(&request);

    assert!(
        !output.status.success(),
        "9 candidates must be refused, not silently truncated or accepted"
    );
    assert_ne!(
        output.status.code(),
        None,
        "process must exit cleanly with a code, not crash/signal (no panic)"
    );

    let stderr: Value = serde_json::from_str(String::from_utf8_lossy(&output.stderr).trim())
        .expect("stderr is a valid JSON error envelope");
    let message = stderr["error"].as_str().expect("error field is a string");
    assert!(
        message.contains('9') && message.contains('8'),
        "error message should name both the offered count and the N=8 limit, got: {message}"
    );
}

#[test]
fn malformed_request_is_refused_with_error_envelope() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_cmca_rank_cli"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("failed to spawn cmca_rank_cli binary");

    child
        .stdin
        .take()
        .expect("child stdin")
        .write_all(b"not json")
        .expect("write malformed request to stdin");

    let output = child.wait_with_output().expect("wait for child");
    assert!(!output.status.success());

    let stderr: Value = serde_json::from_str(String::from_utf8_lossy(&output.stderr).trim())
        .expect("stderr is a valid JSON error envelope");
    assert!(stderr["error"].as_str().is_some());
}
