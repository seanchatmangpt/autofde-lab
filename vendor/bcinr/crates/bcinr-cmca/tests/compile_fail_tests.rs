// trybuild globs the `tests/ui/*.rs` directory via `std::fs::metadata`, which
// shells out to `statx` — unavailable under Miri's isolation sandbox.
#![cfg(not(miri))]

#[test]
fn compile_fail_tests() {
    let t = trybuild::TestCases::new();
    t.compile_fail("tests/ui/*.rs");
}
