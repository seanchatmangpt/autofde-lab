// CMCA-114 regression: a downstream consumer that treats warnings as errors
// (exactly this crate's own `clippy -D warnings` policy, and a common CI
// posture) must get a real, unavoidable compile-time signal when it uses any
// authority-chain "admit_*" constructor. `#[doc(hidden)]` alone (CMCA-102,
// Branch B) produced no such signal -- this file would have compiled clean
// under that regime despite constructing a "certified" proof out of thin air.
#![deny(deprecated)]

use bcinr_cmca::allocator::CertifiedLearning;

fn main() {
    let _ = CertifiedLearning::admit_learning();
}
