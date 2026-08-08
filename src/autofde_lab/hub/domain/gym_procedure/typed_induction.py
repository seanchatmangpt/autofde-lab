# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Typed effect induction -- the repair for unsound add-list flattening.

The defect this exists to fix, found by a real trial run against the live
`cube_counter` provider: `induce_discovered_domain` unions observed deltas
across every successful call to an action. Probing `increment` at counter
0->1, 1->2, 2->3 therefore yields

    increment.positive_effects = {counter=1, counter=2, counter=3, solved=True}

which says a single `increment` establishes `solved=True`. That model is
unsound, it validated a 1-step plan for a 3-step goal, and *30 planners
agreed on it* -- so planner consensus provided no protection. Consensus
over a wrong model is confidently wrong, not right.

Root cause: a metric dimension's transition is **relative** (`counter += 1`),
but a propositional add-list can only express **absolute** facts. Flattening
one into the other loses the invariant and invents unconditional effects.

Repair: induce per-dimension, typed.

* metric dimensions (INTEGER/CONTINUOUS) -> a learned **delta** (`+1`), valid
  only if every observed transition of that action showed the SAME delta;
  otherwise the dimension is recorded as context-dependent and NOT claimed.
* non-metric dimensions (BOOLEAN/CATEGORICAL) -> an absolute value, and only
  when every observation agreed; a dimension that took different values in
  different contexts (e.g. `solved`, which depends on `counter == target`)
  is recorded as **derived/context-dependent** rather than asserted as an
  unconditional effect.

A derived dimension is not a gap to paper over -- it is the honest statement
that this action's effect on that dimension depends on state the add-list
cannot carry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from autofde_lab.hub.domain.gym_procedure.state_typing import (
    DimensionKind,
    StateDimension,
    classify_observation,
)


@dataclass(frozen=True)
class TypedEffect:
    """What one action does to one dimension, in that dimension's own terms."""

    dimension: str
    kind: DimensionKind
    delta: Optional[float] = None  # metric dims: the constant relative change
    absolute_value: Any = None  # non-metric dims: the constant value it lands on
    flip: bool = False  # boolean dims: the constant RELATIVE change (negation)
    context_dependent: bool = False  # observed inconsistently -> NOT claimed
    observations: int = 0

    def describe(self) -> str:
        if self.context_dependent:
            return f"{self.dimension}: CONTEXT_DEPENDENT (not claimed as an unconditional effect)"
        if self.delta is not None:
            return f"{self.dimension}: {self.delta:+g} (relative)"
        if self.flip:
            return f"{self.dimension}: NOT (relative)"
        return f"{self.dimension}: ={self.absolute_value} (absolute)"


@dataclass(frozen=True)
class TypedAction:
    id: str
    effects: dict[str, TypedEffect] = field(default_factory=dict)
    preconditions: dict[str, Any] = field(default_factory=dict)  # non-metric dims that always held
    metric_lower_bounds: dict[str, float] = field(default_factory=dict)
    n_successes: int = 0
    n_refusals: int = 0

    def applicable_in(self, state: dict[str, Any]) -> bool:
        for dim, required in self.preconditions.items():
            if state.get(dim) != required:
                return False
        for dim, bound in self.metric_lower_bounds.items():
            value = state.get(dim)
            if not isinstance(value, (int, float)) or value < bound:
                return False
        return True

    def context_dependent_dimensions(self) -> list[str]:
        return sorted(d for d, e in self.effects.items() if e.context_dependent)

    def apply(self, state: dict[str, Any]) -> dict[str, Any]:
        """Apply this action's learned typed effects to a real state dict."""
        new = dict(state)
        for dim, eff in self.effects.items():
            if eff.context_dependent:
                continue  # honestly unknown -- leave the dimension alone
            if eff.delta is not None:
                base = new.get(dim, 0)
                if isinstance(base, (int, float)):
                    result = base + eff.delta
                    new[dim] = int(result) if eff.kind is DimensionKind.INTEGER else result
            elif eff.flip:
                new[dim] = not bool(new.get(dim))
            else:
                new[dim] = eff.absolute_value
        return new


@dataclass(frozen=True)
class TypedDomain:
    dimensions: dict[str, StateDimension]
    actions: dict[str, TypedAction]

    def derived_dimensions(self) -> list[str]:
        """Dimensions no action claims unconditionally -- i.e. derived from
        others (e.g. `solved` == `counter == target`). Naming them is what
        stops a planner from believing one increment sets `solved`."""
        derived: set[str] = set()
        for act in self.actions.values():
            derived.update(act.context_dependent_dimensions())
        return sorted(derived)

    def simulate(self, initial: dict[str, Any], plan: tuple[str, ...]) -> Optional[dict[str, Any]]:
        state = dict(initial)
        for action_id in plan:
            act = self.actions.get(action_id)
            if act is None:
                return None
            if not act.applicable_in(state):
                return None
            state = act.apply(state)
        return state


def induce_typed_domain(probe_records: list[dict]) -> TypedDomain:
    """Induce a typed, delta-aware action model from real probe records.

    Each record must carry `observed_pre` and `observed_post` dicts of REAL
    typed values (not `"name=value"` strings) plus `action` and `applicable`.
    """
    observations = [r["observed_pre"] for r in probe_records if "observed_pre" in r]
    observations += [r["observed_post"] for r in probe_records if "observed_post" in r]
    dims = classify_observation(observations)

    by_action: dict[str, list[dict]] = {}
    for rec in probe_records:
        by_action.setdefault(rec["action"], []).append(rec)

    actions: dict[str, TypedAction] = {}
    for action_id, records in by_action.items():
        successes = [r for r in records if r.get("applicable") and "observed_pre" in r and "observed_post" in r]
        refusals = [r for r in records if not r.get("applicable")]

        effects: dict[str, TypedEffect] = {}
        touched = {k for r in successes for k in r["observed_post"] if r["observed_post"].get(k) != r["observed_pre"].get(k)}

        for dim_name in sorted(touched):
            dim = dims.get(dim_name)
            kind = dim.kind if dim else DimensionKind.UNKNOWN
            if kind in (DimensionKind.INTEGER, DimensionKind.CONTINUOUS):
                deltas = {
                    r["observed_post"][dim_name] - r["observed_pre"][dim_name]
                    for r in successes
                    if dim_name in r["observed_post"] and dim_name in r["observed_pre"]
                }
                if len(deltas) == 1:
                    effects[dim_name] = TypedEffect(dim_name, kind, delta=float(next(iter(deltas))), observations=len(successes))
                else:
                    # Different deltas in different contexts -- a real
                    # context dependency (e.g. a rate that varies), not a
                    # constant effect. Do not claim it.
                    effects[dim_name] = TypedEffect(dim_name, kind, context_dependent=True, observations=len(successes))
            else:
                values = {r["observed_post"][dim_name] for r in successes if dim_name in r["observed_post"]}
                paired = [
                    r for r in successes
                    if dim_name in r["observed_post"] and dim_name in r["observed_pre"]
                ]
                if len(values) == 1:
                    effects[dim_name] = TypedEffect(dim_name, kind, absolute_value=next(iter(values)), observations=len(successes))
                elif paired and all(
                    isinstance(r["observed_pre"][dim_name], bool)
                    and isinstance(r["observed_post"][dim_name], bool)
                    and r["observed_post"][dim_name] is (not r["observed_pre"][dim_name])
                    for r in paired
                ):
                    # A boolean TOGGLE is a *relative* effect, exactly as
                    # `counter += 1` is. Forcing it into an absolute value is
                    # the same category error that made add-list flattening
                    # unsound -- here it fails the other way: observing
                    # `switch_0` go False->True and True->False yields two
                    # values, so the dimension was written off as
                    # CONTEXT_DEPENDENT and the action modelled as a no-op.
                    # Measured: that made every `switchboard` goal
                    # unreachable (NO_TYPED_VALID_PLAN) the moment probing
                    # observed a toggle in both directions.
                    effects[dim_name] = TypedEffect(dim_name, kind, flip=True, observations=len(successes))
                else:
                    # THE cube_counter case: `solved` was False after some
                    # increments and True after the last one. It is derived
                    # from counter==target, not set by increment. Refusing to
                    # claim it here is what prevents the unsound "one
                    # increment establishes solved=True" model.
                    effects[dim_name] = TypedEffect(dim_name, kind, context_dependent=True, observations=len(successes))

        # Preconditions: only non-metric dimensions whose value was constant
        # across every success (a metric dimension varying across successes
        # is evidence it is NOT a precondition, not evidence it is one).
        preconds: dict[str, Any] = {}
        if successes and refusals:
            candidate_dims = {k for k in successes[0]["observed_pre"]}
            for dim_name in candidate_dims:
                dim = dims.get(dim_name)
                if dim and dim.is_metric():
                    continue
                vals = {r["observed_pre"].get(dim_name) for r in successes}
                if len(vals) != 1:
                    continue
                value = next(iter(vals))
                # REFUSAL EVIDENCE REQUIRED. "Constant across the successes we
                # happened to observe" is not evidence of a precondition -- with
                # a handful of probes nearly every boolean dimension looks
                # constant. Claiming them all is the same unsound inference as
                # the add-list union this module was written to repair, and it
                # fails the opposite way: measured, every `switchboard` action
                # acquired `switch_3=False, switch_4=False, master=False`, so
                # toggling one switch made the others inapplicable and the goal
                # unreachable (NO_TYPED_VALID_PLAN) even though the effects had
                # been learned correctly.
                #
                # A precondition is claimed only when the action was really
                # REFUSED somewhere this dimension differed -- the same
                # evidence standard the metric lower bounds below use.
                if any(
                    isinstance(r.get("observed_pre"), dict)
                    and dim_name in r["observed_pre"]
                    and r["observed_pre"][dim_name] != value
                    for r in refusals
                ):
                    preconds[dim_name] = value

        # Metric preconditions, inferred ONLY from real refusal evidence.
        #
        # Metric dimensions are deliberately excluded from the equality
        # preconditions above (a value varying across successes is evidence
        # it is NOT a constant precondition). That left a hole: `assemble`
        # really requires `refined >= 1`, so a model with no metric
        # precondition believed it was always applicable and planned it from
        # an empty pool -- measured, the real step came back REFUSED.
        #
        # A bound is claimed only when refusals were actually observed BELOW
        # every success. This can only ever make the model MORE restrictive,
        # so its failure mode is an honest NO_TYPED_VALID_PLAN, never a plan
        # that is wrongly believed to run.
        lower_bounds: dict[str, float] = {}
        if successes and refusals:
            for dim_name, dim in dims.items():
                if not dim.is_metric():
                    continue
                success_values = [
                    r["observed_pre"][dim_name] for r in successes if dim_name in r["observed_pre"]
                ]
                refusal_values = [
                    r["observed_pre"][dim_name]
                    for r in refusals
                    if isinstance(r.get("observed_pre"), dict) and dim_name in r["observed_pre"]
                ]
                if not success_values or not refusal_values:
                    continue
                threshold = min(success_values)
                if all(v < threshold for v in refusal_values) and any(
                    v < threshold for v in refusal_values
                ):
                    lower_bounds[dim_name] = float(threshold)

        actions[action_id] = TypedAction(
            id=action_id,
            effects=effects,
            preconditions=preconds,
            metric_lower_bounds=lower_bounds,
            n_successes=len(successes),
            n_refusals=len(refusals),
        )

    return TypedDomain(dimensions=dims, actions=actions)


def validate_plan_typed(
    domain: TypedDomain, initial: dict[str, Any], plan: tuple[str, ...], goal_predicate
) -> tuple[bool, Optional[dict[str, Any]], str]:
    """Independently validate a plan against the TYPED model.

    `goal_predicate` is a callable over a state dict, so a goal that depends
    on a derived dimension (`counter == target`) is evaluated on real
    simulated values instead of on an add-list atom the model was never
    entitled to assert.
    """
    final = domain.simulate(initial, plan)
    if final is None:
        return False, None, "PLAN_INAPPLICABLE_UNDER_TYPED_MODEL"
    if not goal_predicate(final):
        return False, final, "GOAL_NOT_REACHED_UNDER_TYPED_MODEL"
    return True, final, "VALID"


def search_plan_typed(
    domain: TypedDomain, initial: dict[str, Any], goal_predicate, max_len: int = 12
) -> Optional[tuple[str, ...]]:
    """Breadth-first search over the typed model. Deliberately simple and
    model-faithful: its only job is to produce a candidate the typed
    validator will accept, so that a projection-level unsoundness cannot
    smuggle a bad plan past validation."""
    from collections import deque

    def key(s: dict[str, Any]) -> tuple:
        return tuple(sorted((k, v) for k, v in s.items()))

    start = dict(initial)
    if goal_predicate(start):
        return ()
    seen = {key(start)}
    queue = deque([(start, ())])
    action_ids = sorted(domain.actions)
    while queue:
        state, path = queue.popleft()
        if len(path) >= max_len:
            continue
        for action_id in action_ids:
            act = domain.actions[action_id]
            if not act.applicable_in(state):
                continue
            nxt = act.apply(state)
            k = key(nxt)
            if k in seen:
                continue
            new_path = path + (action_id,)
            if goal_predicate(nxt):
                return new_path
            seen.add(k)
            queue.append((nxt, new_path))
    return None
