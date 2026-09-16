use crate::allocator::clip;
use crate::fixed::{const_lt_u32, NonNegativeFixed};

#[derive(Copy, Clone, Debug, Default, PartialEq, Eq)]
pub struct LrcState {
    pub mean_error: NonNegativeFixed,
    pub var_error: NonNegativeFixed,
    pub prev_zeta: NonNegativeFixed,
    pub prev_eta: NonNegativeFixed,
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct LrcParams {
    pub alpha: NonNegativeFixed,    // Smoothing factor for EMA (e.g., 0.125)
    pub phi_max: NonNegativeFixed,  // Maximum stability margin (e.g., 1.0)
    pub phi_min: NonNegativeFixed,  // Minimum stability margin (e.g., 0.1)
    pub zeta_0: NonNegativeFixed,   // Baseline MWU step size (e.g., 0.005)
    pub zeta_min: NonNegativeFixed, // Minimum MWU step size (e.g., 0.0005)
    pub zeta_max: NonNegativeFixed, // Maximum MWU step size (e.g., 0.0125)
    pub eta_0: NonNegativeFixed,    // Baseline exploration rate (e.g., 0.01)
    pub eta_min: NonNegativeFixed,  // Minimum exploration rate (e.g., 0.005)
    pub eta_max: NonNegativeFixed,  // Maximum exploration rate (e.g., 0.1)
    pub k_kappa: NonNegativeFixed,  // Sensitivity to subtree divergence (e.g., 0.5)
    pub k_d: NonNegativeFixed,      // Sensitivity to drift (e.g., 0.5)
    pub gamma: NonNegativeFixed,    // Variance penalty scale for zeta (e.g., 1.0)
    pub theta: NonNegativeFixed,    // Variance boost scale for eta (e.g., 2.0)
}

impl LrcState {
    /// Update the learning rates branchlessly under Radon Law (CC=1).
    #[inline(always)]
    pub fn update(
        &mut self,
        current_error: NonNegativeFixed,
        kappa: NonNegativeFixed,
        d_js: NonNegativeFixed,
        params: &LrcParams,
    ) -> (NonNegativeFixed, NonNegativeFixed) {
        // 1. Mean Error Update: mean = (1 - alpha) * mean + alpha * error
        let alpha = params.alpha;
        let one_minus_alpha = NonNegativeFixed::ONE.saturating_sub(alpha);
        let mean_next = (one_minus_alpha * self.mean_error) + (alpha * current_error);

        // 2. Absolute Difference: diff = |current_error - mean_next|
        let is_lt = const_lt_u32(current_error.val, mean_next.val);
        let diff = NonNegativeFixed::from_bits(is_lt.select_u32(
            mean_next.val.wrapping_sub(current_error.val),
            current_error.val.wrapping_sub(mean_next.val),
        ));

        // 3. Variance Error Update: var = (1 - alpha) * var + alpha * diff^2
        let diff_sq = diff * diff;
        let var_next = (one_minus_alpha * self.var_error) + (alpha * diff_sq);

        // 4. Stability Margin Component: Phi = max(Phi_min, Phi_max - k_kappa * kappa - k_d * d_js)
        let penalty = (params.k_kappa * kappa) + (params.k_d * d_js);
        let phi = params.phi_max.saturating_sub(penalty);
        let phi_safe = clip(phi, params.phi_min, params.phi_max);

        // 5. MWU Step-Size: zeta = num / denom
        let num = params.zeta_0 * phi_safe;
        let denom = NonNegativeFixed::ONE + (params.gamma * var_next);
        let zeta_next = num.saturating_div(denom);
        let zeta_clipped = clip(zeta_next, params.zeta_min, params.zeta_max);

        // 6. Uniform Exploration: eta = eta_0 + theta * var
        let eta_next = params.eta_0 + (params.theta * var_next);
        let eta_clipped = clip(eta_next, params.eta_min, params.eta_max);

        // Commit state
        self.mean_error = mean_next;
        self.var_error = var_next;
        self.prev_zeta = zeta_clipped;
        self.prev_eta = eta_clipped;

        (zeta_clipped, eta_clipped)
    }
}
