import os
import tomllib
from pathlib import Path

import pytest

from enterprise_pipeline import dials


def _tmp_dials(tmp_path, monkeypatch, text):
    p = tmp_path / "d.toml"
    p.write_text(text)
    monkeypatch.setenv("PLAN_POLICY_DIALS", str(p))
    return p


def test_defaults_match_open_switches(monkeypatch):
    monkeypatch.delenv("PLAN_POLICY_DIALS", raising=False)
    sw = tomllib.loads(dials.SWITCHES_PATH.read_text())
    assert dials.clock_policy() == sw["clock_policy"]["default"]
    assert dials.defaults()["clock_policy"] == sw["clock_policy"]["default"]
    assert dials.gpm_safe_harbor_bps() == sw["clock_policy_auto"]["gpm_safe_harbor_bps"]


def test_editing_toml_flips_pure_function(tmp_path, monkeypatch):
    sw = tomllib.loads(dials.SWITCHES_PATH.read_text())
    n = sw["clock_policy_auto"]["desolate_market_provider_threshold"]
    _tmp_dials(tmp_path, monkeypatch, f"[clock_policy_auto]\ndesolate_market_provider_threshold = {n}\n")
    assert dials.desolate_market(n) is False
    _tmp_dials(tmp_path, monkeypatch, f"[clock_policy_auto]\ndesolate_market_provider_threshold = {n + 1}\n")
    assert dials.desolate_market(n) is True


def test_clock_policy_flips_by_option(tmp_path, monkeypatch):
    opts = tomllib.loads(dials.SWITCHES_PATH.read_text())["clock_policy"]["options"]
    seen = set()
    for o in opts:
        _tmp_dials(tmp_path, monkeypatch, f'[clock_policy]\nvalue = "{o}"\n')
        seen.add(dials.clock_policy())
    assert seen == set(opts)


def test_bad_dial_refused(tmp_path, monkeypatch):
    _tmp_dials(tmp_path, monkeypatch, '[clock_policy]\nvalue = "zzz"\n')
    with pytest.raises(ValueError, match=r"BAD_DIAL\[clock_policy=zzz\]"):
        dials.clock_policy()


def test_pm_cap_switch(tmp_path, monkeypatch):
    _tmp_dials(tmp_path, monkeypatch, '[pm_daily_minutes_cap]\nvalue = "capped"\npm_daily_minutes_cap = 7\n')
    assert dials.pm_daily_minutes_cap() == 7
    _tmp_dials(tmp_path, monkeypatch, '[pm_daily_minutes_cap]\nvalue = "uncapped"\n')
    assert dials.pm_daily_minutes_cap() is None
