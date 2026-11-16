"""Diataxis UI smoke: real headless Chromium against a real `streamlit run console.py`.

Tutorial/how-to claims about the UI are checked against the live UI: every view label and button
label (from ui_envelopes.toml) is navigated/visible, and any of those labels quoted in
docs/diataxis/{tutorials,how-to}/*.md must exist in the running console. Journey mechanics
(random worlds, refusal then plan then ledger) come from ui_driver."""
import os
import sys
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui_driver import CFG, ORACLE, ROOT, UI, VIEWS, drive_ui_journey, goto_view, live_server, new_context  # noqa: E402

DOCS = ROOT / "docs" / "diataxis"
QUADRANTS = ("tutorials", "how-to")


@pytest.fixture()
def live(tmp_path):
    with live_server(tmp_path) as srv:
        yield srv


def _doc_text():
    out = ""
    for q in QUADRANTS:
        for p in sorted((DOCS / q).glob("*.md")):
            out += p.read_text()
    return out


def test_every_documented_view_is_navigable(live):
    """Each view label (tutorial/how-to vocabulary) opens a page with that heading."""
    with sync_playwright() as pw:
        browser, ctx = new_context(pw, live["tmp"], os.environ.get("HEADED") == "1")
        page = ctx.new_page()
        page.goto(live["url"])
        for label in VIEWS.values():
            goto_view(page, label)
            expect(page.get_by_role("heading", name=label)).to_be_visible()
        browser.close()
    assert not live["store"].exists(), "navigation alone must not write events"


def test_documented_ui_labels_exist_in_live_console(live):
    """Anti-vacuity twin: labels quoted by docs must be on screen; a bogus label must not be."""
    docs = _doc_text()
    quoted_views = [v for v in VIEWS.values() if v in docs]
    with sync_playwright() as pw:
        browser, ctx = new_context(pw, live["tmp"], os.environ.get("HEADED") == "1")
        page = ctx.new_page()
        page.goto(live["url"])
        for v in quoted_views:
            goto_view(page, v)
        goto_view(page, VIEWS["compile"])
        expect(page.get_by_text("NOT EXECUTED").first).to_be_visible()
        goto_view(page, VIEWS["event_log"])
        expect(page.get_by_text(UI["blank_text"])).to_be_visible()
        bogus = VIEWS["compile"] + "⁣"  # invisible separator: cannot match any real label
        assert page.get_by_test_id("stSidebar").get_by_text(bogus, exact=True).count() == 0
        browser.close()


def test_tutorial_journey_refusal_then_plan_then_ledger(live):
    """Tutorial path end to end: NO PLAN before model tag, plan with invoice/payout after, ledger."""
    headed = os.environ.get("HEADED") == "1"
    with sync_playwright() as pw:  # warm the script runner so the first form is not a cold race
        browser, ctx = new_context(pw, live["tmp"], headed)
        page = ctx.new_page()
        page.goto(live["url"])
        for label in VIEWS.values():
            goto_view(page, label)
        browser.close()
    w = drive_ui_journey(live["url"], CFG, live["store"], include_model_tag=True,
                         tmp=live["tmp"], headed=headed)
    assert w["wo"] and live["store"].exists()
    assert ORACLE["stage2_required_actions"]
