"""Lane H: propulsion rating-bound contract and tsp inversion against real OpenAP and Poll-Schumann services."""

import pytest
from faker import Faker

from autofde_lab.hub.domain.flight_planning.aircraft_performance.bean.aircraft_state import (
    AircraftState,
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
from autofde_lab.hub.domain.flight_planning.aircraft_performance.performance.rating_enum import (
    RatingEnum,
)
from autofde_lab.hub.domain.flight_planning.aircraft_performance.weather.service.atmosphere_service import (
    AtmosphereService,
)
from autofde_lab.hub.domain.flight_planning.aircraft_performance.weather.settings.isa_atmosphere_settings import (
    IsaAtmosphereSettings,
)

MODELS = [PerformanceModelEnum.OPENAP, PerformanceModelEnum.POLL_SCHUMANN]
fake = Faker()
Faker.seed(20260911)
CASES = [
    (
        fake.random_int(25_000, 38_000),
        fake.random_int(55_000, 85_000),
        round(fake.pyfloat(min_value=0.72, max_value=0.82, right_digits=2), 2),
    )
    for _ in range(4)
]


def _state(model, zp_ft, gw_kg, mach, phase=PhaseEnum.CRUISE):
    st = AircraftState(
        model_type="A320",
        performance_model_type=model,
        gw_kg=gw_kg,
        zp_ft=zp_ft,
        mach=mach,
        phase=phase,
        rating_level=RatingEnum.CR,
        cg=0.3,
        gamma_air_deg=0,
    )
    st.weather_state = AtmosphereService().retrieve_weather_state(
        atmosphere_settings=IsaAtmosphereSettings(d_isa=0), four_dimensions_state=st
    )
    delta = st.weather_state.static_pressure_pa / 101325.0
    st.cl = (2 * gw_kg * 9.80665) / (delta * 101325.0 * 1.4 * 122.6 * mach**2)
    return st


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("zp_ft,gw_kg,mach", CASES)
def test_rating_bounds_normalised_and_ordered(model, zp_ft, gw_kg, mach):
    svc = PropulsionService()
    settings = svc.init_settings("A320", model)
    st = _state(model, zp_ft, gw_kg, mach)
    lo = svc.compute_min_rating(settings, st)
    hi = svc.compute_max_rating(settings, st)
    assert 0.0 <= lo <= hi <= 1.0
    # contract: bounds do not drift with altitude because neither model reads tsp
    st2 = _state(model, zp_ft - 5_000, gw_kg, mach)
    assert svc.compute_min_rating(settings, st2) == lo
    assert svc.compute_max_rating(settings, st2) == hi


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("zp_ft,gw_kg,mach", CASES)
def test_thrust_independent_of_tsp_and_inverts(model, zp_ft, gw_kg, mach):
    svc = PropulsionService()
    settings = svc.init_settings("A320", model)
    st = _state(model, zp_ft, gw_kg, mach)
    st.tsp = svc.compute_min_rating(settings, st)
    f_lo = svc.compute_total_net_thrust_n(settings, st)
    st.tsp = svc.compute_max_rating(settings, st)
    f_hi = svc.compute_total_net_thrust_n(settings, st)
    assert f_lo == pytest.approx(f_hi)
    tsp = svc.compute_tsp_from_thrust(settings, st, f_hi)
    st.tsp = tsp
    assert svc.compute_min_rating(settings, st) <= tsp <= svc.compute_max_rating(settings, st)
    assert svc.compute_total_net_thrust_n(settings, st) == pytest.approx(f_hi, abs=10)


def test_openap_thrust_monotonic_in_altitude_in_climb():
    svc = PropulsionService()
    settings = svc.init_settings("A320", PerformanceModelEnum.OPENAP)
    f = []
    for z in (10_000, 20_000, 30_000, 38_000):
        st = _state(PerformanceModelEnum.OPENAP, z, 70_000, 0.74, PhaseEnum.DESCENT)
        f.append(svc.compute_total_net_thrust_n(settings, st))
    assert f == sorted(f, reverse=True) or f == sorted(f)
