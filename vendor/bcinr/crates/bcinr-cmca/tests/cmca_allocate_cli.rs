//! Integration tests for `src/bin/cmca_allocate_cli.rs`: real process
//! invocation of the built binary via `std::process::Command`, real stdin
//! JSON in, real stdout JSON out. No mocking of `allocate()` -- these assert
//! on the actual deterministic allocation the real `allocator::allocate()`
//! produces for the `case_studies` fixture, untampered and tampered.

use std::io::Write;
use std::process::{Command, Stdio};

use serde_json::Value;

fn run_cli(request: &Value) -> Value {
    let mut child = Command::new(env!("CARGO_BIN_EXE_cmca_allocate_cli"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("failed to spawn cmca_allocate_cli binary");

    child
        .stdin
        .take()
        .expect("child stdin")
        .write_all(request.to_string().as_bytes())
        .expect("write request to stdin");

    let output = child.wait_with_output().expect("wait for child");
    assert!(
        output.status.success(),
        "cmca_allocate_cli exited non-zero; stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    serde_json::from_slice(&output.stdout).expect("stdout is valid JSON")
}

#[test]
fn untampered_case_reports_identical_reference_and_claimed_allocations() {
    let request = serde_json::json!({ "case": "case_studies", "tamper": null });
    let response = run_cli(&request);

    assert_eq!(response["case"], Value::from("case_studies"));
    assert_eq!(response["tampered"], Value::Bool(false));
    assert_eq!(
        response["reference_allocation"], response["claimed_allocation"],
        "untampered request must report identical reference and claimed allocations"
    );

    // Sanity check on the real allocator output for this fixture: cache
    // choice case study 1's known property (Artifact_A > Artifact_B), same
    // as `tests/case_studies.rs`'s `test_case_study_1_cache_choice`.
    let obj_0 = response["reference_allocation"]["0"].as_f64().unwrap();
    let obj_1 = response["reference_allocation"]["1"].as_f64().unwrap();
    assert!(obj_0.is_finite() && obj_0 >= 0.0);
    assert!(obj_1.is_finite() && obj_1 >= 0.0);
    assert!(
        obj_0 > obj_1,
        "Artifact_A (index 0) should have higher cache allocation than Artifact_B (index 1)"
    );
}

#[test]
fn tampered_case_diverges_only_at_the_tampered_index() {
    let request = serde_json::json!({
        "case": "case_studies",
        "tamper": { "index": 0, "delta_millionths": 300000 }
    });
    let response = run_cli(&request);

    assert_eq!(response["tampered"], Value::Bool(true));

    let reference = response["reference_allocation"].as_object().unwrap();
    let claimed = response["claimed_allocation"].as_object().unwrap();

    assert_ne!(
        reference, claimed,
        "tampered request must produce a claimed allocation that differs from the reference"
    );

    let ref_0 = reference["0"].as_f64().unwrap();
    let claimed_0 = claimed["0"].as_f64().unwrap();
    assert!(
        (claimed_0 - (ref_0 + 0.3)).abs() < 1e-9,
        "claimed[0] should equal reference[0] + 0.3, got claimed={claimed_0} reference={ref_0}"
    );

    for key in reference.keys() {
        if key == "0" {
            continue;
        }
        assert_eq!(
            reference[key], claimed[key],
            "only the tampered index should diverge between reference and claimed"
        );
    }
}

#[test]
fn unknown_case_is_refused_with_error_envelope() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_cmca_allocate_cli"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("failed to spawn cmca_allocate_cli binary");

    child
        .stdin
        .take()
        .expect("child stdin")
        .write_all(br#"{"case":"not_a_real_case","tamper":null}"#)
        .expect("write request to stdin");

    let output = child.wait_with_output().expect("wait for child");
    assert!(
        !output.status.success(),
        "unknown case should exit non-zero"
    );
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        stderr.contains("error"),
        "stderr should contain an error envelope, got: {stderr}"
    );
}
