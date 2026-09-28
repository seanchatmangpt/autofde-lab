# Phasing Target Defense

## Knowledge-Depreciating Cyber Defense Through Semantic Rematerialization

Status: public dissertation thesis and experimental contract
Version: v26.9.26
Construction boundary: opaque by design

## Abstract

Cybersecurity normally assumes that a defended system possesses a persistent implementation identity. Defensive mechanisms harden that implementation, alter portions of its attack surface, diversify selected components, or dynamically reconfigure exposed properties.

Phasing Target Defense (PTD) proposes a different operating model enabled by inexpensive automated construction.

PTD treats the deployed implementation not as the persistent system but as an ephemeral realization of a persistent semantic specification. An opaque construction mechanism repeatedly materializes that specification into executable systems whose observable implementation structures may differ substantially across epochs while preserving admitted semantics and required behavior.

Let O* be the admitted semantic specification, mu_t an opaque construction process at epoch t, and S_t = mu_t(O*). PTD does not require S_(t+1) = T(S_t). Instead, S_(t+1) = mu_(t+1)(O*). The implementation may be discarded and reconstructed.

The central security hypothesis is that sufficiently inexpensive semantic rematerialization can make attack-relevant knowledge depreciate faster than the defender pays to regenerate the target. The public contribution is PTD itself; the constructor is a black box.

## Thesis

When executable systems are repeatedly constructed from persistent semantic authority rather than maintained as persistent implementations, defenders can intentionally reduce the transferability of attacker knowledge across deployment epochs. If reconstruction cost grows more slowly than attacker realignment cost, semantic rematerialization creates a regime in which large implementation changes can be economically favorable rather than operationally prohibitive.

The claim is not that change itself creates security. The claimed regime is:

cheap CONSTRUCT + semantic invariance + implementation disposability -> knowledge-depreciating defense.

## Persistent implementation assumption

Conventional software evolution is usually S_(t+1) = S_t + delta_t. This makes reconnaissance economically useful because knowledge about an implementation can be amortized across future versions.

PTD separates semantic persistence from implementation persistence. For an explicitly bounded system B, every admitted phase must preserve the required semantic and behavioral contract while implementation identity is allowed to change. The experiment boundary is explicit; PTD never assumes that processors, cloud APIs, DNS, TLS, operating systems, or physical infrastructure automatically change merely because an application does.

## CONSTRUCT as the primitive

A selection-oriented adaptive defense chooses from an existing option space. PTD instead assumes CONSTRUCT(O*, C_t) -> S_t, where C_t contains epoch conditions, constraints, evidence, target environment, and available construction capabilities.

The reachable realization space may therefore change between epochs. This is the root distinction: MTD moves within or transforms a target space; PTD constructs another admitted realization.

The dissertation does not require publication of the internal construction machinery. Only observable properties are experimentally characterized.

## Cross-phase attack-knowledge transfer

For attack task q, define Perf_A(q, K_i, S_j) as attack performance against realization S_j using knowledge acquired from phase i.

Knowledge retention is:

K_ret^q(i,j) = Perf_A(q,K_i,S_j) / Perf_A(q,K_j,S_j).

The denominator uses fresh-phase knowledge against the same target, so target difficulty is held fixed. Attacker knowledge depreciation is K_dep = 1 - K_ret.

K_ret = 1 means prior-phase knowledge performs as well as fresh knowledge. K_ret = 0 means no measured transfer benefit. K_ret > 1 is preserved as a negative PTD result rather than clamped away.

Large textual or structural differences are not sufficient evidence. D_syntax does not imply D_security. The experimental question is which realization changes actually predict reduced cross-phase attack transfer.

## Reconstruction economics

Let C_D be defender cost to construct the next phase and C_A attacker cost to restore useful attack capability. Regeneration Advantage is RA = C_A / C_D. The desired region has RA > 1; a strong economic region has RA much greater than one.

Let T_P be phase duration and T_A attacker realignment time. A strong temporal regime exists when T_A > T_P.

The attacker does not need to understand an entire system. The formal economic test is therefore narrower: defender rematerialization cost should be lower than attacker cost to reestablish the declared attack-relevant capability.

## Generative leverage

Let D_S measure a declared security-relevant realization distance. Generative Leverage is L_G = D_S(S_t,S_(t+1)) / C_D. This is an explanatory variable, not the security objective. PTD can fail despite huge realization distance if attack knowledge transfers cleanly.

The core efficiency metric is PTD_efficiency = K_dep / C_D. An attacker/defender economic form is PTD_advantage = K_dep * (C_A / C_D).

## Phase prediction and amplitude

PTD does not require a fixed mutation envelope. Rather than assuming a probability distribution over a private constructor, the public experiment measures prediction error over observable next-phase properties.

An attacker may train any predictor S_hat_(t+1) = f(S_1,...,S_t), and the experiment measures E_phase = D_S(S_hat_(t+1), S_(t+1)). Historical phases are useful to the attacker only to the degree that they predict future attack-relevant structure.

Knowledge of the PTD method therefore does not imply knowledge of the next realization. This is an empirical claim, not a secrecy assumption.

## Cyber-resiliency relationship

PTD does not replace established cyber-resiliency engineering. NIST SP 800-160 Vol. 2 Rev. 1 includes diversity, dynamic positioning, non-persistence, unpredictability, adaptive response, realignment, segmentation, substantiated integrity, and related techniques.

PTD's architectural proposition is that implementation persistence itself is optional inside the experiment boundary. Non-persistence, diversity, positioning, and other techniques can therefore emerge from repeated construction rather than being separately maintained mechanisms.

Existing software-diversity and synthesis work shows that specifications can yield multiple functionally equivalent implementations. Moving Target Defense research already studies invalidating reconnaissance. Intent-defined and adaptive-software work already separates durable intent from concrete implementation. PTD's bounded contribution is repeated admitted realization construction with cross-phase attack-knowledge depreciation as the dependent variable.

## Disclosure frontier

For disclosed information x, let V_B(x) be marginal legitimate-buyer utility and V_A(x) marginal attacker utility. A disclosure frontier can maximize V_B(x) - lambda V_A(x), subject to auditability, operability, compliance, interoperability, and assurance requirements.

Experiments should progressively increase attacker information, including black-box access, current source, historical phases, the public semantic contract, and knowledge that PTD is in use. Security must not depend on the general method remaining secret. Non-disclosure may add attacker discovery cost, but it is an economic amplifier rather than the proof.

## Experimental program

A canonical admitted subject O* is repeatedly materialized into S_1, S_2, ..., S_n. Experiments vary only dimensions whose semantic invariance can be independently checked, including representation, naming, schema, serialization, generated source structure, service decomposition, deployment topology, policy boundaries, dependency topology, and planner representation.

Each experiment declares its bounded realization surface, attack objective, phase duration, success thresholds, realization-distance function, and attacker information condition. High-information experiments should give the attacker as much current and historical information as practical while withholding only future choices that do not yet exist.

The executable court in src/autofde_lab/ptd measures K_ret, K_dep, C_A, C_D, T_A, T_P, D_S, L_G, RA, PTD efficiency, and PTD advantage without access to constructor internals.

## Falsification

PTD fails when large reconstruction leaves K_ret near one: the variation is mostly irrelevant to the attack objective. It also fails economically when C_D >= C_A for the claimed regime, and temporally when T_A <= T_P for a claimed strong phase regime.

Semantic admission failure is a PTD failure. Common-mode persistence is a PTD failure when a vulnerability in the persistent specification or another persistent authority necessarily survives each realization. Compromise of the persistent authority or construction inputs is a separate failure class because it may influence future phases.

These failures are first-class output rows in the executable PTD court; they are not normalized away.

## Contributions

The public research contribution consists of the distinction between persistent semantic systems and disposable realizations; cross-phase attack-knowledge retention and depreciation metrics; Generative Leverage and Regeneration Advantage; observable phase-prediction error; the disclosure frontier; and a reproducible protocol for evaluating PTD without publishing constructor internals.

## Research boundary

PTD does not claim that software diversity, synthesis, MTD, non-persistence, unpredictability, dynamic positioning, or intent-defined software are new. The bounded novelty claim is:

persistent admitted semantic system -> repeated whole-boundary realization construction -> measurable cross-phase attack-knowledge depreciation.

The constructor is not the publication. It is an opaque experimental producer. PTD stands or falls on independently observable results.

## Conclusion

For most of software history, substantial change has been expensive. That encouraged implementation persistence, which made reconnaissance reusable. When reconstruction becomes sufficiently inexpensive, implementation persistence can become optional inside a declared boundary.

The resulting objective is not merely to stop an attacker from learning a target. It is to reduce the future value of what the attacker learns.

The central empirical question is: can constructing the next system become cheaper than reestablishing useful attack capability against it?

## Public prior-art anchors

NIST Moving Target Defense glossary: https://csrc.nist.gov/glossary/term/moving_target_defense

NIST SP 800-160 Vol. 2 Rev. 1: https://csrc.nist.gov/pubs/sp/800/160/v2/r1/final

DARPA Intent-Defined Adaptive Software: https://www.darpa.mil/research/programs/intent-defined-adaptive-software
