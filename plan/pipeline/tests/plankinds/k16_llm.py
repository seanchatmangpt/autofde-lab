"""K16 LLM candidate plans: a real chat-completion call, only when a usable key+endpoint exists."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

from . import Case, Outcome, Skip

KIND = "K16"
TITLE = "LLM candidate plan (blocks-3, parsed to action lines)"
BLOCKS = Path(__file__).resolve().parents[4] / ("tests/domains/python/pddl_domains/blocks")
_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY")


def _endpoint():
    e = os.environ
    if e.get("ANTHROPIC_API_KEY"):
        return ("anthropic", "https://api.anthropic.com/v1/messages",
                {"x-api-key": e["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
                e.get("ANTHROPIC_MODEL", "claude-haiku-4-5"))
    if e.get("OPENAI_API_KEY"):
        return ("openai", "https://api.openai.com/v1/chat/completions",
                {"Authorization": f"Bearer {e['OPENAI_API_KEY']}"}, e.get("OPENAI_MODEL", "gpt-4o-mini"))
    if e.get("AZURE_OPENAI_API_KEY") and e.get("AZURE_OPENAI_ENDPOINT") and e.get("AZURE_OPENAI_DEPLOYMENT"):
        url = (f"{e['AZURE_OPENAI_ENDPOINT'].rstrip('/')}/openai/deployments/{e['AZURE_OPENAI_DEPLOYMENT']}"
               "/chat/completions?api-version=2024-06-01")
        return ("azure", url, {"api-key": e["AZURE_OPENAI_API_KEY"]}, "")
    return None


def probe() -> Skip | None:
    if not any(os.environ.get(k) for k in _KEYS):
        return Skip("no API key", "export ANTHROPIC_API_KEY=... (or OPENAI_API_KEY)")
    if _endpoint() is None:
        return Skip("no API key usable: AZURE_OPENAI_API_KEY set but AZURE_OPENAI_ENDPOINT/"
                    "AZURE_OPENAI_DEPLOYMENT absent", "export AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT")
    return None


def cases() -> list[Case]:
    return [Case("llm-blocks-3-candidate", "PLAN", {})]


def run(case: Case) -> Outcome:
    prov, url, hdr, model = _endpoint()
    prompt = ("Solve this PDDL problem. Reply with ONLY the plan, one action per line like (unstack a b).\n"
              f"{(BLOCKS / 'domain.pddl').read_text()}\n{(BLOCKS / 'probBLOCKS-3-0.pddl').read_text()}")
    if prov == "anthropic":
        body = {"model": model, "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]}
    else:
        body = {"messages": [{"role": "user", "content": prompt}], **({"model": model} if model else {})}
    req = urllib.request.Request(url, json.dumps(body).encode(), {"content-type": "application/json", **hdr})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.load(r)
    except Exception as exc:
        return Outcome("REFUSED", f"{prov} call failed: {exc}")
    text = j["content"][0]["text"] if prov == "anthropic" else j["choices"][0]["message"]["content"]
    steps = re.findall(r"^\s*\(([a-z-]+(?: [a-z0-9]+)*)\)\s*$", text, re.M)
    return Outcome("PLAN" if steps else "NO_PLAN", f"{prov} steps={len(steps)}", "\n".join(steps))
