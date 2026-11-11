"""Encode airport planning traces (turnaround RCPSP, stand dispatch) as GraphLaw actions."""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from autofde_lab.law_bridge.graphlaw_admitter import Action


def _t(s: str, p: str, o: str) -> str:
    return f"<urn:ap:{s}> <urn:ap:{p}> <urn:ap:{o}> ."


def turnaround_actions(
    order: Sequence[str], deboarding: str, services: Sequence[str], boarding: str, case: str = "turn"
) -> Tuple[str, List[Action]]:
    """Precedence law: services need deboarding done; boarding needs every service done.
    `order` is the executed activity order. Returns (initial state, actions)."""
    done = lambda a: _t(case, "done", a)
    acts: List[Action] = []
    for a in order:
        if a == deboarding:
            pre = ""
        elif a == boarding:
            pre = "\n".join(done(s) for s in services)
        else:
            pre = done(deboarding)
        acts.append(Action(name=a, pre=pre, add=done(a)))
    return _t(case, "phase", "ground"), acts


def stand_actions(events: Sequence[Tuple[str, str, str]]) -> Tuple[str, List[Action]]:
    """events: (kind 'occupy'|'release', stand, flight) in time order. A stand must be free to
    be occupied, and occupied by that flight to be released."""
    stands = sorted({s for _, s, _ in events})
    initial = "\n".join(_t(f"stand_{s}", "state", "free") for s in stands)
    acts: List[Action] = []
    for i, (kind, s, f) in enumerate(events):
        st = f"stand_{s}"
        if kind == "occupy":
            acts.append(Action(f"{i}:occupy:{f}", _t(st, "state", "free"), _t(st, "heldby", f),
                               _t(st, "state", "free")))
        else:
            acts.append(Action(f"{i}:release:{f}", _t(st, "heldby", f), _t(st, "state", "free"),
                               _t(st, "heldby", f)))
    return initial, acts
