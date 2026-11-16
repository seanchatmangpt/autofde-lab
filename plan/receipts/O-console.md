# O-console receipt
Standing: PARTIAL_ALIVE

Edited: console.py, docs/jira/v26.11.11/CONTRACT-LAWS.md (UI deltas section).
Gate: streamlit AppTest over views A, C, D, E, G with PLAN_STORE=/tmp/o_console_store.jsonl;
`py_compile console.py` ok; no exceptions rendered (exit 0).
Not run: Playwright ui_driver suite (UI-test owner); dials.py, store.can/missing_media,
staged.observe_flags not yet on disk, console guards them and renders NOT EXECUTED.
