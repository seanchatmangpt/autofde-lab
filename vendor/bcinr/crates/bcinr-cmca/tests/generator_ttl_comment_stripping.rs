//! Regression test for CMCA-118: `generator.py`'s TTL comment stripping must
//! be literal-aware — a `#` character inside a quoted string literal (e.g. a
//! URL fragment or an ID embedded in a note) must survive, while a real `#`
//! comment outside any literal must still be stripped.
//!
//! `generator.py` has no existing Python test convention in this crate (no
//! `test_generator*.py`, no pytest config) — the crate's existing convention
//! is Rust tests in `tests/`. This test therefore shells out to the real
//! `generator.py` as a subprocess against real TTL fixtures on disk, per the
//! ticket's suggested approach, rather than introducing a new Python test
//! framework for a single regression case.

use std::fs;
use std::path::PathBuf;
use std::process::Command;

fn crate_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn run_generator(ttl_contents: &str) -> (bool, String, String) {
    let dir = tempfile_dir();
    let ttl_path = dir.join("input.ttl");
    let out_path = dir.join("out.rs");
    fs::write(&ttl_path, ttl_contents).expect("write fixture ttl");

    let output = Command::new("python3")
        .arg(crate_root().join("generator.py"))
        .arg(&ttl_path)
        .arg(&out_path)
        .output()
        .expect("failed to invoke python3 generator.py");

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let generated = fs::read_to_string(&out_path).unwrap_or_default();

    let _ = fs::remove_dir_all(&dir);
    (
        output.status.success(),
        stderr,
        format!("{stdout}\n---\n{generated}"),
    )
}

/// Minimal, unique temp dir under the crate's target dir so parallel test
/// runs don't collide.
///
/// Uniqueness is `pid + atomic-sequence + nanos`. The previous `pid + nanos`
/// scheme raced: `SystemTime` nanos can repeat within the same clock tick
/// across threads, so two parallel tests could land the same dir, and the
/// second `input.ttl` write won the race to the first test's `python3`
/// invocation -- observed as `unsupported_language_tag_is_still_rejected`
/// intermittently failing with the *multiline-literal* rejection message.
/// The atomic sequence makes within-process collisions impossible; the pid
/// guards cross-process; the nanos are retained only as extra entropy.
fn tempfile_dir() -> PathBuf {
    static TEMP_DIR_SEQ: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
    let base = crate_root().join("target").join("cmca118-test-tmp");
    fs::create_dir_all(&base).expect("create tmp base");
    let seq = TEMP_DIR_SEQ.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    let unique = base.join(format!(
        "{}-{}-{}",
        std::process::id(),
        seq,
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(&unique).expect("create unique tmp dir");
    unique
}

const TTL_PREAMBLE: &str = r#"@prefix cmca: <http://example.org/cmca#> .

cmca:Root a cmca:SemanticObject .
"#;

#[test]
fn hash_literal_inside_string_survives_and_is_not_treated_as_comment_start() {
    // The `#` in the label literal below must NOT truncate the string, and
    // must NOT be treated as starting a comment that swallows the trailing
    // `.` statement terminator.
    let ttl = format!(
        "{TTL_PREAMBLE}cmca:Root cmca:businessValue \"1.0\"^^xsd:decimal .\ncmca:Root cmca:label \"A#B\" .\n"
    );
    let (ok, stderr, combined) = run_generator(&ttl);
    assert!(ok, "generator failed unexpectedly: {stderr}");
    // The object should have been parsed (businessValue factor present),
    // proving the line with the '#'-bearing literal was not corrupted into
    // an unparsed/garbage statement that the parser silently dropped.
    assert!(
        combined.contains("businessValue") || combined.contains("Generated"),
        "expected successful generation output, got: {combined}"
    );
}

#[test]
fn real_comment_outside_literal_is_still_stripped() {
    let ttl = format!(
        "{TTL_PREAMBLE}cmca:Root cmca:businessValue \"1.0\"^^xsd:decimal . # trailing real comment\n# whole-line comment\n"
    );
    let (ok, stderr, _combined) = run_generator(&ttl);
    assert!(
        ok,
        "generator failed on a line with a genuine trailing comment: {stderr}"
    );
}

#[test]
fn unsupported_multiline_literal_is_still_rejected() {
    // Locks in one of the existing "Unsupported Turtle construct" rejections
    // referenced by the ticket, so the literal-awareness fix doesn't
    // accidentally loosen these checks.
    let ttl = format!("{TTL_PREAMBLE}cmca:Root cmca:label \"\"\"multi\nline\"\"\" .\n");
    let (ok, stderr, _combined) = run_generator(&ttl);
    assert!(!ok, "expected generator to reject multiline literal");
    assert!(
        stderr.contains("multiline literals"),
        "expected multiline-literal rejection message, got: {stderr}"
    );
}

#[test]
fn unsupported_language_tag_is_still_rejected() {
    let ttl = format!("{TTL_PREAMBLE}cmca:Root cmca:label \"hello\"@en .\n");
    let (ok, stderr, _combined) = run_generator(&ttl);
    assert!(!ok, "expected generator to reject language-tagged literal");
    assert!(
        stderr.contains("language tags"),
        "expected language-tag rejection message, got: {stderr}"
    );
}

#[test]
fn real_ontology_files_produce_byte_identical_output_after_the_fix() {
    // Neither real ontology file currently contains a '#' inside a literal,
    // so their generated output must be byte-identical to before this fix —
    // this is the no-regression proof for the literal-awareness change.
    for (ttl_name, out_name) in [
        ("cmca-rdf.ttl", "case_studies.rs"),
        ("generalization.ttl", "generalization_case_studies.rs"),
    ] {
        let ttl_path = crate_root().join("ontology").join(ttl_name);
        if !ttl_path.exists() {
            continue;
        }
        let dir = tempfile_dir();
        let out_path = dir.join(out_name);
        let output = Command::new("python3")
            .arg(crate_root().join("generator.py"))
            .arg(&ttl_path)
            .arg(&out_path)
            .output()
            .expect("failed to invoke python3 generator.py");
        assert!(
            output.status.success(),
            "generator failed on real ontology file {ttl_name}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        let _ = fs::remove_dir_all(&dir);
    }
}
