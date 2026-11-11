"""L9 stub closure: propulsion rating bounds + abstract-hook contracts (Chicago style)."""

import pytest

from autofde_lab.builders.domain.dynamics import Environment, Simulation
from autofde_lab.builders.domain.events import Events
from autofde_lab.builders.domain.initialization import Initializable, UncertainInitialized
from autofde_lab.builders.domain.observability import PartiallyObservable
from autofde_lab.hub.domain.flight_planning.aircraft_performance.bean.aircraft_state import (
    AircraftState,
)
from autofde_lab.hub.domain.flight_planning.aircraft_performance.performance.aero.service.aerodynamics_service_interface import (
    AerodynamicsServiceInterface,
)
from autofde_lab.hub.domain.flight_planning.aircraft_performance.performance.performance_model_enum import (
    PerformanceModelEnum,
)
from autofde_lab.hub.domain.flight_planning.aircraft_performance.performance.phase_enum import (
    PhaseEnum,
)
from autofde_lab.hub.domain.flight_planning.aircraft_performance.performance.propulsion.service.propulsion_service import (
    PropulsionService,
)
from autofde_lab.hub.domain.flight_planning.aircraft_performance.performance.propulsion.service.propulsion_service_interface import (
    PropulsionServiceInterface,
)
from autofde_lab.hub.domain.flight_planning.aircraft_performance.performance.rating_enum import (
    RatingEnum,
)
from autofde_lab.hub.domain.flight_planning.aircraft_performance.weather.service.atmosphere_service_interface import (
    AtmopshereServiceInterface,
)

MODELS = [PerformanceModelEnum.OPENAP, PerformanceModelEnum.POLL_SCHUMANN]


@pytest.mark.parametrize("model", MODELS)
def test_rating_bounds_are_ordered_floats(model):
    svc = PropulsionService()
    settings = svc.init_settings("A320", model)
    state = AircraftState(
        model_type="A320",
        performance_model_type=model,
        gw_kg=70_000,
        zp_ft=30_000,
        mach=0.78,
        phase=PhaseEnum.CRUISE,
        rating_level=RatingEnum.CR,
        cg=0.3,
        gamma_air_deg=0,
    )
    lo = svc.compute_min_rating(settings, state)
    hi = svc.compute_max_rating(settings, state)
    assert isinstance(lo, float) and isinstance(hi, float)
    assert 0.0 <= lo < hi <= 1.0


@pytest.mark.parametrize(
    "iface", [PropulsionServiceInterface, AerodynamicsServiceInterface, AtmopshereServiceInterface]
)
def test_interfaces_are_abstract(iface):
    with pytest.raises(TypeError):
        iface()


def test_dynamics_hooks_are_abstract_contracts():
    with pytest.raises(NotImplementedError):
        Environment._state_step(Environment(), None)
    with pytest.raises(NotImplementedError):
        Simulation._state_sample(Simulation(), None, None)


def test_initialization_hook_contract():
    for cls in (Initializable, UncertainInitialized):
        with pytest.raises(NotImplementedError):
            cls._get_initial_state_distribution_(cls()) if cls is UncertainInitialized else cls._state_reset(cls())


def test_events_and_observability_hook_contract():
    with pytest.raises(NotImplementedError):
        Events._get_action_space_(Events())
    with pytest.raises(NotImplementedError):
        PartiallyObservable._get_observation_space_(PartiallyObservable())


def test_hook_docstrings_state_override_contract():
    for fn in (
        Environment._state_step,
        Initializable._state_reset,
        Events._get_action_space_,
        PartiallyObservable._get_observation_space_,
    ):
        assert "must override" in fn.__doc__
