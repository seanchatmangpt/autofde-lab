#![allow(clippy::needless_range_loop)]

use bcinr_cmca::generated::consequence_mass::case_studies::{
    LensSpec, PackedSemanticState, K, N, Q,
};

pub fn compute_measures_f64(state: &PackedSemanticState) -> [f64; K] {
    let factors: Vec<f64> = state
        .factors
        .iter()
        .map(|f| f.to_bits() as f64 / 65536.0)
        .collect();

    let recomp = factors[0];
    let verify = factors[1];
    let standing = factors[2];
    let access = factors[4];
    let search = factors[5];
    let retrieval = factors[6];
    let sched = factors[7];
    let bval = factors[8];
    let conseq = factors[9];

    let m0 = (recomp * 5.0 + verify) * access * standing;
    let m1 = (bval + conseq) * search * standing;
    let m2 = bval * retrieval;
    let m3 = bval * sched;

    [m0, m1, m2, m3]
}

#[allow(clippy::too_many_arguments)] // deliberate wide parameter list mirroring the fixed-point reference API
pub fn allocate_f64(
    states: &[PackedSemanticState; N],
    lenses: &[LensSpec; Q],
    lambda: &[[f64; Q]; K],
    eta: f64,
    parent: &[i32; N],
    weights: &mut [[f64; 2 * Q]; N],
    payoffs: &[[f64; 2 * Q]; N],
    zeta: f64,
    epsilon_kappa: f64,
    mu: &[f64; N],
    costs: &[f64; N],
    t: u32,
    last_switch_t: &mut u32,
    prev_mode: &mut u32,
    tau_d: u32,
) -> [f64; N] {
    // 1. Identify leaves
    let mut is_leaf = [true; N];
    for (i, leaf) in is_leaf.iter_mut().enumerate() {
        for &p in parent.iter() {
            if p == i as i32 {
                *leaf = false;
            }
        }
    }

    // 2. Identify subtree leaf relationships
    let mut is_descendant = [[false; N]; N];
    #[allow(clippy::needless_range_loop)] // diagonal self-index into a 2-D array
    for i in 0..N {
        is_descendant[i][i] = true;
    }
    for _ in 0..N {
        for j in 0..N {
            let p = parent[j];
            if p != -1 {
                #[allow(clippy::needless_range_loop)]
                // is_descendant[j][k] and is_descendant[p][k] share index k but are distinct rows
                for k in 0..N {
                    if is_descendant[j][k] {
                        is_descendant[p as usize][k] = true;
                    }
                }
            }
        }
    }

    let mut is_subtree_leaf = [[false; N]; N];
    for i in 0..N {
        for k in 0..N {
            is_subtree_leaf[i][k] = is_leaf[k] && is_descendant[i][k];
        }
    }

    // 3. Compute raw masses
    let mut raw_masses = [[0.0; N]; K];
    for i in 0..N {
        let m = compute_measures_f64(&states[i]);
        for k in 0..K {
            raw_masses[k][i] = m[k];
        }
    }

    // 4. Overwrite parent masses with q-norm aggregation if mutant 6 active is simulated, but here reference is normal.
    let mut node_masses = raw_masses;

    // Clamp masses
    #[allow(clippy::needless_range_loop)] // node_masses[k][i] indexed across two dimensions
    for k in 0..K {
        for i in 0..N {
            node_masses[k][i] = node_masses[k][i].clamp(0.0001, 1000.0);
        }
    }

    // 5. Update weights (MWU)
    // Dynamic rate limiter
    let beta = if zeta > 0.1 { 0.1 } else { zeta };

    // Dwell Time Lock
    let mut root_idx = 0usize;
    for (i, &p) in parent.iter().enumerate() {
        if p == -1 {
            root_idx = i;
        }
    }

    let mut max_w = -1.0;
    let mut dom_mode = 0u32;
    for (e, &w) in weights[root_idx].iter().enumerate() {
        if w > max_w {
            max_w = w;
            dom_mode = e as u32;
        }
    }

    let switch_wanted = dom_mode != *prev_mode;
    let can_switch = t.wrapping_sub(*last_switch_t) >= tau_d;
    let switch_rejected = switch_wanted && !can_switch;
    let update_allowed = !switch_rejected;

    for v in 0..N {
        if !is_leaf[v] {
            for q_idx in 0..Q {
                let q_val = lenses[q_idx].q.to_bits() as f64 / 65536.0;

                // Compute kappa
                let mut sum_meas_den = 0.0;
                let mut sum_leaf_den = 0.0;
                for i in 0..N {
                    if parent[i] == v as i32 {
                        sum_meas_den += node_masses[0][i].powf(q_val);
                    }
                    if is_subtree_leaf[v][i] {
                        sum_leaf_den += node_masses[0][i].powf(q_val);
                    }
                }

                let mut kappa = 0.0;
                for c in 0..N {
                    if parent[c] == v as i32 {
                        let s_meas = node_masses[0][c].powf(q_val) / sum_meas_den;
                        let mut l_q_c = 0.0;
                        for x in 0..N {
                            if is_subtree_leaf[c][x] {
                                l_q_c += node_masses[0][x].powf(q_val);
                            }
                        }
                        let s_leaf = l_q_c / sum_leaf_den;
                        if s_leaf > 0.0 {
                            kappa += s_leaf * (s_leaf / s_meas).log2();
                        }
                    }
                }

                let update_active = kappa > epsilon_kappa;

                if update_active && update_allowed {
                    let w_flat = weights[v][2 * q_idx];
                    let p_flat = payoffs[v][2 * q_idx];
                    weights[v][2 * q_idx] = w_flat * (beta * p_flat).exp();

                    let w_desc = weights[v][2 * q_idx + 1];
                    let p_desc = payoffs[v][2 * q_idx + 1];
                    weights[v][2 * q_idx + 1] = w_desc * (beta * p_desc).exp();
                }
            }

            // Normalize weights
            for q_idx in 0..Q {
                let w_flat = weights[v][2 * q_idx];
                let w_desc = weights[v][2 * q_idx + 1];
                let sum = w_flat + w_desc;
                if sum > 0.0 {
                    weights[v][2 * q_idx] /= sum;
                    weights[v][2 * q_idx + 1] /= sum;
                }
            }
        }
    }

    // Dwell Time Lock Post-Update
    let mut new_dom_mode = 0u32;
    let mut new_max_w = -1.0;
    for (e, &w) in weights[root_idx].iter().enumerate() {
        if w > new_max_w {
            new_max_w = w;
            new_dom_mode = e as u32;
        }
    }
    if new_dom_mode != *prev_mode && can_switch {
        *last_switch_t = t;
        *prev_mode = new_dom_mode;
    }

    // 6. Compute allocations Pi_{k, q}(x)
    let mut pi_kq = [[[0.0; N]; Q]; K];

    for k in 0..K {
        for q_idx in 0..Q {
            let q_val = lenses[q_idx].q.to_bits() as f64 / 65536.0;

            let mut root_sum = 0.0;
            for i in 0..N {
                if parent[i] == -1 {
                    root_sum += node_masses[k][i].powf(q_val);
                }
            }

            let mut alloc_flow = [0.0; N];
            for i in 0..N {
                if parent[i] == -1 {
                    alloc_flow[i] = node_masses[k][i].powf(q_val) / root_sum;
                }
            }

            let mut flat_alloc = [0.0; N];

            for _ in 0..N {
                for v in 0..N {
                    if !is_leaf[v] {
                        let w_flat = weights[v][2 * q_idx];
                        let w_desc = weights[v][2 * q_idx + 1];
                        let sum = w_flat + w_desc;
                        let rho = if sum > 0.0 { w_desc / sum } else { 0.5 };

                        let flat_coeff = 1.0 - rho;
                        let desc_coeff = rho;

                        let flat_part = flat_coeff * alloc_flow[v];
                        let desc_part = desc_coeff * alloc_flow[v];

                        let mut child_sum = 0.0;
                        let mut leaf_sum = 0.0;
                        for c in 0..N {
                            if parent[c] == v as i32 {
                                child_sum += node_masses[k][c].powf(q_val);
                            }
                        }
                        for x in 0..N {
                            if is_subtree_leaf[v][x] {
                                leaf_sum += node_masses[k][x].powf(q_val);
                            }
                        }

                        for x in 0..N {
                            if is_subtree_leaf[v][x] {
                                flat_alloc[x] +=
                                    flat_part * (node_masses[k][x].powf(q_val) / leaf_sum);
                            }
                        }

                        for c in 0..N {
                            if parent[c] == v as i32 {
                                alloc_flow[c] +=
                                    desc_part * (node_masses[k][c].powf(q_val) / child_sum);
                            }
                        }

                        alloc_flow[v] = 0.0;
                    }
                }
            }

            for x in 0..N {
                pi_kq[k][q_idx][x] = flat_alloc[x] + alloc_flow[x];
            }
        }
    }

    // 7. Combine allocations
    let mut pi_combined = [0.0; N];
    for k in 0..K {
        for q_idx in 0..Q {
            let lam = lambda[k][q_idx];
            for x in 0..N {
                pi_combined[x] += lam * pi_kq[k][q_idx][x];
            }
        }
    }

    // 8. Apply resource prices post-escort
    let mut priced_val = [0.0; N];
    for x in 0..N {
        let mu_clamped = mu[x].clamp(0.0, 100.0);
        let dot_prod = mu_clamped * costs[x];
        priced_val[x] = pi_combined[x] * (-dot_prod).exp();
    }

    let mut priced_sum = 0.0;
    for i in 0..N {
        if is_leaf[i] {
            priced_sum += priced_val[i];
        }
    }

    let mut pi_mu = [0.0; N];
    for x in 0..N {
        if priced_sum > 0.0 {
            pi_mu[x] = priced_val[x] / priced_sum;
        }
    }

    // 9. Apply unpriced global floor
    let mut num_leaves = 0;
    for &leaf in is_leaf.iter() {
        if leaf {
            num_leaves += 1;
        }
    }
    let u_sharp = 1.0 / num_leaves as f64;

    let mut pi_res = [0.0; N];
    for i in 0..N {
        if is_leaf[i] {
            pi_res[i] = eta * u_sharp + (1.0 - eta) * pi_mu[i];
        }
    }

    pi_res
}
