# O-console-repair-r1 receipt
Standing: PARTIAL_ALIVE

Edited: none (console.py unchanged; no console-attributable failure found).
Evidence:
- diataxis ui smoke (uv run --with playwright,streamlit,plotly,pandas pytest -x
  pipeline/tests/diataxis/test_ui_diataxis_smoke.py): 2 passed (view navigation, label
  existence: sidebar labels found), 1 failed: journey, "event client not recorded".
- Cause: seed=3442958383 -> ui_driver.gen_world client_kind=secondary_client, driver sets
  no parent, store.py raises Refused NO_PARENT[...] (lawful), console shows st.error.
  Owner: ui_driver.py/test owner (choose primary_client or fill parent), not console.
- AppTest over views A-G with PLAN_STORE=/tmp/oc_r1b.jsonl: zero exceptions each view.
Not attributable to console: test_staged, NO_PARENT in helpers_world, justfile.d/45-ui.just
recipes, ledger-pddl, anti-vacuity items.
