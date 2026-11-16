"""Policy dials: read policy_dials.toml (tomllib); validate against open_switches.toml."""
from __future__ import annotations

import hashlib
import os
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
SWITCHES_PATH = _ROOT / "docs" / "jira" / "v26.11.11" / "open_switches.toml"
DEFAULT_PATH = _ROOT / "pipeline" / "policy_dials.toml"
_cache: dict[tuple[str, str], dict] = {}


def _read(p: Path) -> dict:
    raw = p.read_bytes() if p.exists() else b""
    key = (str(p), hashlib.sha256(raw).hexdigest())
    if key not in _cache:
        _cache[key] = tomllib.loads(raw.decode())
    return _cache[key]


def switches() -> dict:
    return _read(SWITCHES_PATH)


def load(path=None) -> dict:
    p = Path(path or os.environ.get("PLAN_POLICY_DIALS") or DEFAULT_PATH)
    return _read(p)


def defaults() -> dict[str, str]:
    return {k: v["default"] for k, v in switches().items() if "default" in v}


def get(switch: str) -> str:
    sw = switches()
    if switch not in sw or "options" not in sw[switch]:
        raise ValueError(f"BAD_DIAL[{switch}=unknown_switch]")
    v = load().get(switch, {}).get("value", sw[switch]["default"])
    if v not in sw[switch]["options"]:
        raise ValueError(f"BAD_DIAL[{switch}={v}]")
    return v


def param(switch: str, key: str):
    own = load().get(switch, {})
    if key in own:
        return own[key]
    base = switches().get(switch, {})
    if key in base:
        return base[key]
    raise KeyError(f"{switch}.{key}")


def clock_policy() -> str:
    return get("clock_policy")


def entity_dba_model() -> str:
    return get("entity_dba_model")


def secondary_out_of_coverage() -> str:
    return get("secondary_out_of_coverage")


def handoff_semantics() -> str:
    return get("handoff_semantics")


def document_expiry_enforcement() -> str:
    return get("document_expiry_enforcement")


def provider_filter_validation() -> str:
    return get("provider_filter_validation")


def media_prompt_mode() -> str:
    return get("media_prompt_mode")


def change_order_parent_wait() -> str:
    return get("change_order_parent_wait")


def change_order_nte_cap() -> str:
    return get("change_order_nte_cap")


def pm_daily_minutes_cap():
    if get("pm_daily_minutes_cap") == "uncapped":
        return None
    return int(param("pm_daily_minutes_cap", "pm_daily_minutes_cap"))


def gpm_safe_harbor_bps() -> int:
    return int(param("clock_policy_auto", "gpm_safe_harbor_bps"))


def low_rate_safe_harbor_cents() -> int:
    return int(param("clock_policy_auto", "low_rate_safe_harbor_cents"))


def desolate_market_min_providers() -> int:
    return int(param("clock_policy_auto", "desolate_market_provider_threshold"))


def default_nte_cost_share_bps():
    """Optional dial; None when neither file defines it."""
    try:
        return int(param("default_nte_cost_share", "default_nte_cost_share_bps"))
    except KeyError:
        return None


def desolate_market(provider_count: int) -> bool:
    return provider_count < desolate_market_min_providers()


def gpm_safe_harbor_met(gpm_bps: int) -> bool:
    return gpm_bps >= gpm_safe_harbor_bps()
