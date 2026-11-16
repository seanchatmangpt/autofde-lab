DIATAXIS_ROOT := justfile_directory()

diataxis-check:
    cd {{DIATAXIS_ROOT}} && python3 scripts/verify_diataxis.py

diataxis-selfcheck:
    cd {{DIATAXIS_ROOT}} && python3 scripts/verify_diataxis.py --self-check
