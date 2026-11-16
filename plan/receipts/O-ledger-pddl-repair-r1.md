# O-ledger-pddl-repair-r1
Standing: PARTIAL
Owned files (ledger/*, spec/servengine_ideal_domain.pddl): no defect found; `pytest ledger/tests` -> 18 passed (rc 0).
Disclosed minimal unblock in non-owned pipeline/enterprise_pipeline/staged.py:
1. intake goal is `(reactive-hire-handed-off wo)` when the reactive-hire flag is set (dispatch goal was unreachable -> aries TIMEOUT).
2. qa-review compile adds `MISSING[model_tag_photo]` when part replacement lacks the tag photo.
Result: test_howto_reactive_hire_real_plan and test_tutorial_twin_model_tag_omitted_is_missing pass.
Remaining (not owned): NO_PARENT from tests/helpers_world.py (parentless secondary_client vs locked L09) -> test_staged x5;
test_howto_executive_override (dispatch_override eligibility, align.py); ui smoke needs --with playwright/streamlit.
Run: diataxis+test_staged (PLAN_SEARCH_TIMEOUT_S=5): 6 failed, 12 passed, 3 skipped before-receipt.
