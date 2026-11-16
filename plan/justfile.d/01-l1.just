L1_ROOT := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })

# Plan the enterprise-ops problem with aries and validate (nonzero exit if no valid plan)
l1-plan:
    {{L1_ROOT}}/planner/run.sh

# Show the stored plan
l1-show:
    cat {{L1_ROOT}}/planner/plan_solution.soln
