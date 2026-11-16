EXECUTOR_ROOT := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) }) + "/executor"

executor-run:
    python3 {{EXECUTOR_ROOT}}/run.py

executor-verify: executor-run
    python3 {{EXECUTOR_ROOT}}/replay.py verify {{EXECUTOR_ROOT}}/receipts.jsonl

executor-test:
    python3 -m unittest discover -v -s {{EXECUTOR_ROOT}}/tests
