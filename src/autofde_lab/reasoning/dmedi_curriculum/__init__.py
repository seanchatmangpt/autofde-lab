"""DMEDI curriculum modules -- one real file per planner.

Real curriculum source: Design for Lean Six Sigma Black Belt (DMEDI:
Define, Measure, Explore, Develop, Implement). 51 real modules, one per
curriculum topic. Every module has MODULE_STANDING = "PLANNED" or
"IMPLEMENTED" -- never silently assumed. As of this generation:

3/51 IMPLEMENTED (real code + real passing tests, see
laboratory.py sections 14-15 and tests/reasoning/test_{triz,doe}_chicago.py).
48/51 PLANNED (real, named, explicit
NotImplementedError stubs -- never fabricated implementations).
"""

from __future__ import annotations

# phase -> [(topic, module_name, standing), ...], real and complete
DMEDI_CURRICULUM = {
    "DEFINE": [
        ("Introduction to Design for Lean Six Sigma", "intro_dfss", "PLANNED"),
        ("Overview of the Define Phase", "define_phase_overview", "PLANNED"),
        ("Charter", "charter", "PLANNED"),
        ("MGPP", "mgpp", "PLANNED"),
        ("Risk Management", "risk_management", "PLANNED"),
        ("Communication Plan", "communication_plan", "PLANNED"),
    ],
    "MEASURE": [
        ("Voice of the Customer", "voice_of_the_customer", "PLANNED"),
        ("Quality Function Deployment", "quality_function_deployment", "PLANNED"),
        ("Target Costing", "target_costing", "PLANNED"),
        ("Scorecards", "scorecards", "PLANNED"),
        ("Intro to Minitab", "intro_to_minitab", "PLANNED"),
        ("Basic Statistics", "basic_statistics", "PLANNED"),
        ("Understanding Variation and Control Charts", "control_charts", "PLANNED"),
        ("Measurement Systems Analysis", "measurement_systems_analysis", "PLANNED"),
        ("Process Capability", "process_capability", "PLANNED"),
    ],
    "EXPLORE": [
        ("Concept Generation", "concept_generation", "PLANNED"),
        ("TRIZ for New Product Design", "triz_new_product_design", "IMPLEMENTED"),
        ("Transactional TRIZ", "transactional_triz", "PLANNED"),
        ("Concept Selection - Pugh", "concept_selection_pugh", "PLANNED"),
        ("Concept Selection - AHP", "concept_selection_ahp", "PLANNED"),
        ("Statistical Tolerance Design", "statistical_tolerance_design", "PLANNED"),
        ("Monte Carlo Simulation", "monte_carlo_simulation", "PLANNED"),
        ("Hypothesis Testing", "hypothesis_testing", "PLANNED"),
        ("Confidence Intervals", "confidence_intervals", "PLANNED"),
        ("Testing Means", "testing_means", "PLANNED"),
        ("Testing Medians and Variances", "testing_medians_variances", "PLANNED"),
        ("Proportion Testing", "proportion_testing", "PLANNED"),
        ("Chi-Square", "chi_square", "PLANNED"),
        ("Simple Regression", "simple_regression", "PLANNED"),
        ("Multiple Regression", "multiple_regression", "PLANNED"),
        ("Multi-Vari Analysis", "multi_vari_analysis", "PLANNED"),
        ("Design FMEA", "design_fmea", "PLANNED"),
    ],
    "DEVELOP": [
        ("Detailed Design", "detailed_design", "PLANNED"),
        ("2-Way ANOVA", "two_way_anova", "PLANNED"),
        ("Intro to Design of Experiments", "intro_to_doe", "IMPLEMENTED"),
        ("Full-Factorial DOE", "full_factorial_doe", "IMPLEMENTED"),
        ("Fractional Factorial DOE", "fractional_factorial_doe", "PLANNED"),
        ("DOE Catapult Simulation", "doe_catapult_simulation", "PLANNED"),
        ("Lean Design", "lean_design", "PLANNED"),
        ("Design for Manufacture and Assembly", "design_for_manufacture_assembly", "PLANNED"),
        ("Intro to Reliability", "intro_to_reliability", "PLANNED"),
        ("Design of Experiments with Curvature", "doe_with_curvature", "PLANNED"),
        ("Conjoint Analysis", "conjoint_analysis", "PLANNED"),
        ("Mixture Designs", "mixture_designs", "PLANNED"),
        ("Robust Design", "robust_design", "PLANNED"),
        ("Helicopter RSM Simulation", "helicopter_rsm_simulation", "PLANNED"),
    ],
    "IMPLEMENT": [
        ("Overview of the Implement Phase", "implement_phase_overview", "PLANNED"),
        ("Prototype and Pilot", "prototype_and_pilot", "PLANNED"),
        ("Process Control", "process_control", "PLANNED"),
        ("Implementation Planning", "implementation_planning", "PLANNED"),
        ("DMEDI Capstone", "dmedi_capstone", "PLANNED"),
    ],
}

def module_count() -> int:
    """Real count, computed from the real dict above, never hardcoded twice."""
    return sum(len(v) for v in DMEDI_CURRICULUM.values())

def implemented_count() -> int:
    """Real count of IMPLEMENTED modules, computed, never hardcoded."""
    return sum(1 for topics in DMEDI_CURRICULUM.values() for _, _, s in topics if s == "IMPLEMENTED")
