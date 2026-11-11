"""Chicago tests for lane R1 stub sites: real classes, no doubles."""

import math

import pytest

from autofde_lab.builders.domain import constraints, goals, memory, renderability
from autofde_lab.builders.domain.scheduling import (
    precedence,
    resource_renewability,
    task_progress,
    time_lag,
    time_windows,
)
from autofde_lab.core import HookNotImplementedError
from autofde_lab.hub.domain.flight_planning.weather_interpolator.weather_tools.interpolator.WeatherInterpolator import (
    WeatherForecastInterpolator,
)
from autofde_lab.hub.domain.mastermind.mastermind import MasterMind, State, Score

HOOKS = [
    (constraints.Constrained, "_get_constraints_"),
    (goals.Goals, "_get_goals_"),
    (memory.FiniteHistory, "_get_memory_maxlen_"),
    (precedence.WithPrecedence, "_get_successors"),
    (resource_renewability.MixedRenewable, "_get_resource_renewability"),
    (task_progress.CustomTaskProgress, "_get_task_progress"),
    (time_lag.WithTimeLag, "_get_time_lags"),
    (time_windows.WithTimeWindow, "_get_time_window"),
]


@pytest.mark.parametrize("cls,name", HOOKS)
def test_hook_raises_typed_not_implemented(cls, name):
    obj = object.__new__(cls)
    fn = getattr(obj, name)
    import inspect

    n = len(inspect.signature(fn).parameters)
    with pytest.raises(HookNotImplementedError) as ei:
        fn(*([None] * n))
    assert isinstance(ei.value, NotImplementedError)


def test_renderable_hook_typed():
    obj = object.__new__(renderability.Renderable)
    with pytest.raises(HookNotImplementedError):
        obj._render_from(None)


def test_mastermind_none_action_keeps_state():
    mm = MasterMind()
    st = State((0, 1), Score(0, 0))
    assert mm._get_next_state(st, None) is st


def test_weather_render_returns_axis_unchanged():
    w = object.__new__(WeatherForecastInterpolator)
    ax = object()
    assert w.render(ax) is ax


def test_schumann_thrust_quasi_steady_has_no_acceleration_term():
    from autofde_lab.hub.domain.flight_planning.aircraft_performance.bean.aircraft_state import (
        AircraftState,
    )

    assert not any("accel" in f or f == "dv_dt" for f in dir(AircraftState))
