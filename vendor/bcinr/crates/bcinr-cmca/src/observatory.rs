//! # Calibration Observatory and Telemetry Engine
//!
//! This module provides the telemetry and evaluation machinery to monitor
//! mathematical model stability and trigger recertification/admissions branchlessly.
//!
//! It implements the core inference phase of the MAPE-K loop, checking five key criteria:
//!
//! 1. **Numerical Uncertainty** ([`ObservatoryFlag::NumericallyUncertain`]): Triggers when the estimated condition
//!    number (`kappa_hat`) exceeds the stability limit (`epsilon_on`), but the lower bound
//!    (`kappa_under`) does not, meaning the actual condition number is boundary-uncertain.
//! 2. **Gram Degeneracy** ([`ObservatoryFlag::GramDegenerate`]): Triggers when the condition number lower bound
//!    (`kappa_under`) exceeds the stability threshold, but the minimum positive eigenvalue
//!    (`gamma_min_plus_under`) falls below the Gram threshold (`epsilon_gram`).
//! 3. **Non-stationary Drift** ([`ObservatoryFlag::Drifting`]): Triggers when the divergence metric (`d_js`)
//!    exceeds the drift boundary (`epsilon_drift`).
//! 4. **Scale Inertia** ([`ObservatoryFlag::ScaleInert`]): Triggers when measured scale (`s_meas`) matches the
//!    leaf scale (`s_leaf`) exactly, indicating a collapse of informative scaling variance.
//! 5. **Recertification Candidate** ([`ObservatoryFlag::RecertificationCandidate`]): The success flag returned when
//!    all active stability criteria are satisfied.
//!
//! All checks are combined into a branchless selection tree, guaranteeing $CC=1$.

use crate::allocator::{const_eq_u32, const_lt_u32, const_select_u32};
use crate::fixed::{NonNegativeFixed, SignedFixed};

/// Telemetry safety and calibration indicators for the runtime observatory.
///
/// These flags categorize the current stability status of the monitored substrate.
/// Except for [`ObservatoryFlag::RecertificationCandidate`], all flags represent a failure mode
/// that halts normal operation and demands quarantine or fallback execution.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum ObservatoryFlag {
    /// The estimated condition number exceeds the safety threshold, but its lower bound does not.
    /// Indicates that the substrate is operating in a region of high numerical uncertainty.
    NumericallyUncertain,

    /// The lower bound condition number indicates a active state, but the minimum positive Gram eigenvalue
    /// is below the degeneracy threshold. Indicates loss of numerical rank/independence.
    GramDegenerate,

    /// The measured distance/divergence exceeds the allowed drift threshold, indicating that the underlying
    /// data distribution is non-stationary.
    Drifting,

    /// The measured scale is identical to the target leaf scale, indicating zero scaling update information.
    ScaleInert,

    /// The proposal does not propose a delta, meaning it is unadmitted for recertification.
    ModeDeltaUnadmitted,

    /// The successful validation state. The substrate passes all safety filters and is a candidate
    /// for recertification or normal deployment.
    RecertificationCandidate,
}

impl ObservatoryFlag {
    /// Converts a raw `u32` value into its corresponding `ObservatoryFlag`.
    ///
    /// The conversion is performed branchlessly, mapping out-of-bounds inputs to `None`.
    ///
    /// # Examples
    ///
    /// ```rust
    /// use bcinr_cmca::observatory::ObservatoryFlag;
    ///
    /// assert_eq!(ObservatoryFlag::from_u32(0), Some(ObservatoryFlag::NumericallyUncertain));
    /// assert_eq!(ObservatoryFlag::from_u32(4), Some(ObservatoryFlag::ModeDeltaUnadmitted));
    /// assert_eq!(ObservatoryFlag::from_u32(5), Some(ObservatoryFlag::RecertificationCandidate));
    /// assert_eq!(ObservatoryFlag::from_u32(6), None);
    /// ```
    pub fn from_u32(val: u32) -> Option<Self> {
        let lookup = [
            Some(Self::NumericallyUncertain),
            Some(Self::GramDegenerate),
            Some(Self::Drifting),
            Some(Self::ScaleInert),
            Some(Self::ModeDeltaUnadmitted),
            Some(Self::RecertificationCandidate),
            None,
            None,
        ];

        let in_bounds = const_lt_u32(val, 6);
        let idx = const_select_u32(in_bounds, val, 6) as usize;
        let res = lookup[idx & 7];

        res.filter(|_| in_bounds != 0)
    }
}

const FLAGS: [ObservatoryFlag; 8] = [
    ObservatoryFlag::NumericallyUncertain,
    ObservatoryFlag::GramDegenerate,
    ObservatoryFlag::Drifting,
    ObservatoryFlag::ScaleInert,
    ObservatoryFlag::ModeDeltaUnadmitted,
    ObservatoryFlag::RecertificationCandidate,
    ObservatoryFlag::RecertificationCandidate,
    ObservatoryFlag::RecertificationCandidate,
];

#[allow(deprecated)]
use crate::allocator::CertificateReceipt;

/// Wraps a raw observatory flag code into a `Result` type branchlessly.
///
/// A flag code of `5` (corresponding to `RecertificationCandidate`) represents success and
/// maps to `Ok(CertificateReceipt)`. Any other flag code represents a failure mode and maps to `Err(ObservatoryFlag)`.
///
/// # Branchless Contract
///
/// Under the hood, this function maps the integer code into the static flag mapping
/// array and uses a branchless array index selection based on the equality to `5`.
#[allow(deprecated)] // return type legitimately carries the CMCA-114 authority-chain proof token
pub fn wrap_observatory_result(
    flag_code: u32,
    digest: u64,
) -> Result<CertificateReceipt, ObservatoryFlag> {
    let flag = FLAGS[(flag_code as usize) & 7];
    let is_recert = const_eq_u32(flag_code, 5);
    let outcomes = [Err(flag), Ok(CertificateReceipt::new(digest))];
    outcomes[is_recert as usize]
}

/// Evaluates calibration metrics and proposes an admission/stability flag branchlessly.
///
/// This is the primary telemetry evaluation routine. It takes estimates and lower bounds of
/// key covariance and distance metrics and compares them against predefined thresholds,
/// compiling all findings into a single outcome flag branchlessly.
///
/// # Arguments
///
/// * `artifact` - The `MeasurementArtifact` containing telemetry metrics and proposal.
/// * `epsilon_on` - The threshold limit for the condition number.
/// * `epsilon_gram` - The threshold limit for the Gram eigenvalue.
/// * `epsilon_drift` - The threshold limit for drift divergence.
/// * `s_meas` - The measured scale parameter of the current sample.
/// * `s_leaf` - The target scale parameter at the leaf node.
///
/// # Return Value
///
/// Returns `Ok(CertificateReceipt)` if the system passes all safety gates (mapping to `RecertificationCandidate`).
/// Otherwise, returns an `Err(ObservatoryFlag)` indicating the first detected failure mode in the
/// prioritization queue (highest priority to lowest priority):
/// 1. `Drifting` (highest priority check)
/// 2. `ScaleInert`
/// 3. `NumericallyUncertain`
/// 4. `GramDegenerate`
///
/// # Branchless Contract
///
/// Checks are performed concurrently using bitwise masks. Prioritization is enforced using
/// sequential branchless selections `const_select_u32`.
#[allow(deprecated)] // return type legitimately carries the CMCA-114 authority-chain proof token
pub fn evaluate_calibration(
    artifact: &MeasurementArtifact,
    epsilon_on: NonNegativeFixed,
    epsilon_gram: NonNegativeFixed,
    epsilon_drift: NonNegativeFixed,
    s_meas: NonNegativeFixed,
    s_leaf: NonNegativeFixed,
) -> Result<CertificateReceipt, ObservatoryFlag> {
    let kappa_hat = artifact.point_estimate;
    let kappa_under = artifact.lower_bound;
    let gamma_min_plus_under = artifact.gram_lower_bound;
    let d_js = artifact.drift;

    // Conditions
    #[cfg(not(feature = "mutant_9"))]
    let is_drift = const_lt_u32(epsilon_drift.val, d_js.val);
    #[cfg(feature = "mutant_9")]
    let is_drift = const_lt_u32(d_js.val, epsilon_drift.val); // Mutated: drift check inverted

    let is_scale_inert = const_eq_u32(s_meas.val, s_leaf.val);

    let kappa_hat_on =
        const_lt_u32(epsilon_on.val, kappa_hat.val) | const_eq_u32(epsilon_on.val, kappa_hat.val);
    #[cfg(not(feature = "mutant_10"))]
    let kappa_under_off = const_lt_u32(kappa_under.val, epsilon_on.val);
    #[cfg(feature = "mutant_10")]
    let kappa_under_off = const_lt_u32(epsilon_on.val, kappa_under.val); // Mutated: inverted
    let is_numerically_uncertain = kappa_hat_on & kappa_under_off;

    let kappa_under_on = const_lt_u32(epsilon_on.val, kappa_under.val)
        | const_eq_u32(epsilon_on.val, kappa_under.val);

    #[cfg(not(feature = "mutant_11"))]
    let gamma_under_off = const_lt_u32(gamma_min_plus_under.val, epsilon_gram.val);
    #[cfg(feature = "mutant_11")]
    let gamma_under_off = const_lt_u32(epsilon_gram.val, gamma_min_plus_under.val); // Mutated: inverted

    let is_gram_degenerate = kappa_under_on & gamma_under_off;

    let is_unadmitted = const_eq_u32(artifact.proposal as u32, ModeDelta::Retain as u32);

    let is_recert = kappa_under_on & (!gamma_under_off) & (!is_unadmitted);

    let mut flag = 5u32; // Default to Ok
    flag = const_select_u32(is_recert, 5, flag);
    flag = const_select_u32(is_unadmitted, 4, flag);
    flag = const_select_u32(is_gram_degenerate, 1, flag);
    flag = const_select_u32(is_numerically_uncertain, 0, flag);
    flag = const_select_u32(is_scale_inert, 3, flag);
    flag = const_select_u32(is_drift, 2, flag);

    wrap_observatory_result(flag, artifact.control_mode_digest)
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct SupportStanding {
    pub is_supported: bool,
    pub smoothing_applied: bool,
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum ModeDelta {
    Retain,
    ProposeDelta,
}

#[derive(Copy, Clone, Debug)]
pub struct MeasurementArtifact {
    pub point_estimate: NonNegativeFixed,
    pub lower_bound: NonNegativeFixed,
    pub upper_bound: NonNegativeFixed,
    pub support_standing: SupportStanding,
    pub effective_sample_size: NonNegativeFixed,
    pub dependence_standing: u32,
    pub numeric_error: NonNegativeFixed,
    pub drift: NonNegativeFixed,
    pub gram_lower_bound: NonNegativeFixed,
    pub graph_digest: u64,
    pub control_mode_digest: u64,
    pub proposal: ModeDelta,
}

use crate::allocator::const_max_i32;
use crate::generated::consequence_mass::case_studies::{K, N};
use crate::{unroll_4_static, unroll_8_static};

/// Measures the divergence metric $\kappa_v$ and produces a MeasurementArtifact branchlessly.
#[inline(never)]
#[allow(clippy::too_many_arguments)] // deliberate wide parameter list for a hot, branchless measurement kernel
pub fn measure_kappa(
    v: usize,
    _q_idx: usize,
    k: usize,
    parent: &[i32; N],
    _is_leaf: &[bool; N],
    is_subtree_leaf_v: &[bool; N],
    is_subtree_leaf: &[[bool; N]; N],
    node_masses: &[[NonNegativeFixed; N]; K],
    q_val: SignedFixed,
) -> MeasurementArtifact {
    let k_masked = k & 3;

    let mut x = [0i32; N];
    unroll_8_static!(I, {
        let mut log_m = 0u32;
        unroll_4_static!(K_IDX, {
            let matches = const_eq_u32(k_masked as u32, K_IDX as u32);
            log_m = const_select_u32(
                matches,
                node_masses[K_IDX & 3][I & 7].log2().val as u32,
                log_m,
            );
        });
        let q_signed = q_val.val;
        x[I & 7] = (((q_signed as i64).wrapping_mul(log_m as i32 as i64)) >> 16) as i32;
    });

    let mut x_max_meas = i32::MIN;
    unroll_8_static!(J, {
        let is_child = const_eq_u32(parent[J & 7] as u32, v as u32);
        let x_safe = const_select_u32(is_child, x[J & 7] as u32, i32::MIN as u32) as i32;
        x_max_meas = const_max_i32(x_max_meas, x_safe);
    });

    let mut sum_exp_meas = NonNegativeFixed::ZERO;
    unroll_8_static!(J, {
        let is_child = const_eq_u32(parent[J & 7] as u32, v as u32);
        let a_prime = x[J & 7].wrapping_sub(x_max_meas);
        let exp_val = SignedFixed::from_bits(a_prime).exp2();
        sum_exp_meas += NonNegativeFixed::from_bits(const_select_u32(is_child, exp_val.val, 0));
    });
    let l_meas = x_max_meas.wrapping_add(sum_exp_meas.log2().val);

    let mut x_max_leaf = i32::MIN;
    unroll_8_static!(X_IDX, {
        let is_sub = is_subtree_leaf_v[X_IDX & 7];
        let x_safe = const_select_u32(is_sub as u32, x[X_IDX & 7] as u32, i32::MIN as u32) as i32;
        x_max_leaf = const_max_i32(x_max_leaf, x_safe);
    });

    let mut sum_exp_leaf = NonNegativeFixed::ZERO;
    unroll_8_static!(X_IDX, {
        let is_sub = is_subtree_leaf_v[X_IDX & 7];
        let a_prime = x[X_IDX & 7].wrapping_sub(x_max_leaf);
        let exp_val = SignedFixed::from_bits(a_prime).exp2();
        sum_exp_leaf +=
            NonNegativeFixed::from_bits(const_select_u32(is_sub as u32, exp_val.val, 0));
    });
    let l_leaf = x_max_leaf.wrapping_add(sum_exp_leaf.log2().val);

    let mut kappa_i64 = 0i64;
    unroll_8_static!(C, {
        let is_child = const_eq_u32(parent[C & 7] as u32, v as u32);

        let mut x_max_c = i32::MIN;
        unroll_8_static!(X_IDX, {
            let is_sub_c = is_subtree_leaf[C & 7][X_IDX & 7];
            let x_safe =
                const_select_u32(is_sub_c as u32, x[X_IDX & 7] as u32, i32::MIN as u32) as i32;
            x_max_c = const_max_i32(x_max_c, x_safe);
        });

        let mut sum_exp_c = NonNegativeFixed::ZERO;
        unroll_8_static!(X_IDX, {
            let is_sub_c = is_subtree_leaf[C & 7][X_IDX & 7];
            let a_prime = x[X_IDX & 7].wrapping_sub(x_max_c);
            let exp_val = SignedFixed::from_bits(a_prime).exp2();
            sum_exp_c +=
                NonNegativeFixed::from_bits(const_select_u32(is_sub_c as u32, exp_val.val, 0));
        });
        let l_c = x_max_c.wrapping_add(sum_exp_c.log2().val);

        let log_ratio = l_c.wrapping_sub(l_meas);
        let s_leaf_c = NonNegativeFixed::from_bits(
            SignedFixed::from_bits(l_c.wrapping_sub(l_leaf)).exp2().val,
        );

        let term = (s_leaf_c.val as i64).wrapping_mul(log_ratio as i64);
        let term_selected = const_select_u32(is_child, (term >> 16) as u32, 0) as i32 as i64;
        kappa_i64 = kappa_i64.wrapping_add(term_selected);
    });

    let kappa_clipped = const_select_u32((kappa_i64 < 0) as u32, 0, kappa_i64 as u32);
    let kappa = NonNegativeFixed::from_bits(kappa_clipped);

    MeasurementArtifact {
        point_estimate: kappa,
        lower_bound: kappa,
        upper_bound: kappa,
        support_standing: SupportStanding {
            is_supported: true,
            smoothing_applied: false,
        },
        effective_sample_size: NonNegativeFixed::ONE,
        dependence_standing: 0,
        numeric_error: NonNegativeFixed::ZERO,
        drift: NonNegativeFixed::ZERO,
        gram_lower_bound: NonNegativeFixed::ZERO,
        graph_digest: 0,
        control_mode_digest: 0,
        proposal: ModeDelta::Retain,
    }
}
