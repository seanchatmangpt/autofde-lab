"""Chicago-style (state-based, zero-mock) browser test for console.py; mechanics live in ui_driver."""
import os
import tempfile
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from ui_driver import CFG, UI, VIEWS, drive_ui_journey, goto_view, live_server, new_context


@pytest.fixture()
def live(tmp_path):
    with live_server(tmp_path) as srv:
        yield srv


def test_blank_store_view(live, request):
    headed = os.environ.get("HEADED") == "1"
    with sync_playwright() as pw:
        browser, ctx = new_context(pw, live["tmp"], headed)
        page = ctx.new_page()
        page.goto(live["url"])
        goto_view(page, VIEWS["event_log"])
        expect(page.get_by_text(UI["blank_text"])).to_be_visible()
        assert not live["store"].exists()
        goto_view(page, VIEWS["compile"])
        assert not live["store"].exists()
        ctx.tracing.stop(path=str(live["tmp"] / "blank_trace.zip"))
        browser.close()


def test_chicago_visual_blank_slate_to_settlement(live, request):
    w = drive_ui_journey(live["url"], CFG, live["store"], include_model_tag=True,
                         tmp=live["tmp"], headed=os.environ.get("HEADED") == "1")
    request.node.user_properties.append(("seed", w["seed"]))
