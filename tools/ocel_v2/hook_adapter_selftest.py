#!/usr/bin/env python3
"""
hook_adapter_selftest.py — real-interface self-test for
~/.claude/scripts/hook-to-ocel.py.

hook-to-ocel.py's actual interface (confirmed by reading the file, not
guessed):

  - It is a stdin -> file-sink script whose `main()` reads a JSON hook
    payload from stdin and appends one OCEL event line to
    ~/.claude/ocel/claude-hooks.ocel.jsonl. It never returns/prints the
    built event as its primary contract (stdout is reserved for hook
    protocol data and must stay silent).
  - However it also defines a plain, side-effect-free, importable function:

        build_ocel_event(payload: dict) -> dict

    which takes a hook payload dict and returns the OCEL event dict
    (id/type/time/attributes/relationships) *without* touching disk. That
    is the real mapping logic this self-test exercises, imported directly
    (not shelled out, since importing the real function is more direct and
    avoids re-parsing subprocess stdout that the module intentionally
    keeps silent).

This script:
  1. Imports build_ocel_event from hook-to-ocel.py (via importlib, since the
     filename has hyphens and isn't a valid module identifier).
  2. Synthesizes one realistic PostToolUse hook payload (Bash tool call),
     matching the field names documented at the top of hook-to-ocel.py.
  3. Feeds it through the real build_ocel_event() to get a real OCEL event.
  4. Derives a ClaudeSession object record and pulls the ClaudeToolInvocation
     relationship out of that real event's `relationships` list (both are
     already produced by the real adapter logic; this step just packages
     them for the output file, it does not re-implement the mapping).
  5. Writes the result to hook_selftest_output.json in this directory.
"""

import importlib.util
import json
import os
import sys

HOOK_TO_OCEL_PATH = os.path.expanduser("~/.claude/scripts/hook-to-ocel.py")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook_selftest_output.json")


def load_hook_to_ocel():
    if not os.path.isfile(HOOK_TO_OCEL_PATH):
        raise FileNotFoundError(f"hook-to-ocel.py not found at {HOOK_TO_OCEL_PATH}")
    spec = importlib.util.spec_from_file_location("hook_to_ocel", HOOK_TO_OCEL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthesize_posttooluse_payload() -> dict:
    """One realistic Claude Code PostToolUse hook payload (Bash tool call)."""
    session_id = "sess_selftest_8f3a1c2e"
    return {
        "session_id": session_id,
        "transcript_path": f"/Users/sac/.claude/projects/-Users-sac-crown-2-integration-autofde-lab/{session_id}.jsonl",
        "cwd": "/Users/sac/crown-2-integration/autofde-lab/tools/ocel_v2",
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {
            "command": "pytest -q tests/test_ocel_adapter.py",
            "description": "Run OCEL adapter self-test suite",
        },
        "tool_response": {
            "stdout": "1 passed in 0.42s\n",
            "stderr": "",
            "is_error": False,
        },
        "permission_mode": "default",
    }


def main() -> int:
    module = load_hook_to_ocel()

    payload = synthesize_posttooluse_payload()

    # Real mapping logic — the actual function defined in hook-to-ocel.py.
    ocel_event = module.build_ocel_event(payload)

    # ClaudeSession object, derived straight from the real event's own
    # relationships list (the adapter always emits this relationship;
    # here we just surface it as a standalone "object" record for the
    # self-test output, per the task's requested shape).
    session_rel = next(
        r for r in ocel_event["relationships"] if r["objectType"] == "ClaudeSession"
    )
    claude_session_object = {
        "id": session_rel["objectId"],
        "type": "ClaudeSession",
        "attributes": [
            {"name": "session_id", "value": payload["session_id"]},
            {"name": "cwd", "value": payload["cwd"]},
        ],
    }

    tool_invocation_rel = next(
        (r for r in ocel_event["relationships"] if r["objectType"] == "ClaudeToolInvocation"),
        None,
    )

    result = {
        "input_payload": payload,
        "claude_session_object": claude_session_object,
        "claude_tool_invocation_relationship": tool_invocation_rel,
        "ocel_event": ocel_event,
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
