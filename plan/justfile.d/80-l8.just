L8_ROOT := parent_directory(justfile_directory())

# L8 adversarial courts: PDDL mutants + MiniZinc veto mutants + self-check
l8-courts:
    python3 {{L8_ROOT}}/courts/court.py all

l8-pddl:
    python3 {{L8_ROOT}}/courts/court.py pddl

l8-mzn:
    python3 {{L8_ROOT}}/courts/court.py mzn
