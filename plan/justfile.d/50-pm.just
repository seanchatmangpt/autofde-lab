PM_ROOT := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) })
pm-test:
    cd {{PM_ROOT}}/pm && python3 -m unittest test_pm
pm-run:
    cd {{PM_ROOT}}/pm && python3 gen_problem.py --out out/instance && python3 sweep_scheduler.py out/instance.json out/schedule.json
pm-plan:
    cd {{PM_ROOT}}/pm && python3 gen_problem.py --assets 2 --cadences monthly --horizon 60 --out out/small && python3 planner_try.py pm_domain.pddl out/small.pddl
