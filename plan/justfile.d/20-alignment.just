ALIGNMENT_ROOT := (if path_exists(justfile_directory() + "/justfile.d") == "true" { justfile_directory() } else { parent_directory(justfile_directory()) }) + "/alignment"

alignment-test:
    {{ALIGNMENT_ROOT}}/run_tests.sh
