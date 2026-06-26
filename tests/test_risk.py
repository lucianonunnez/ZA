"""Tests that encode the evidence: the risk model must reflect what the data says."""


from copilot.gateway import Gateway
from copilot.pipeline.risk import _time_of_day_risk, assess_risk
from copilot.schemas import Cabin, FlightOption


def _flight(depart: str, carrier="BA", code="BA", stops=0) -> FlightOption:
    return FlightOption(
        carrier=carrier, carrier_code=code, flight_no="BA178",
        origin="JFK", destination="LHR", depart=depart, arrive="09:10+1",
        cabin=Cabin.business, duration_min=405, stops=stops, cash_price_usd=4820,
    )


def test_morning_is_lower_risk_than_late_night():
    """Validated: >80% on-time before 8am vs 53% after 10pm (US DOT)."""
    early, _ = _time_of_day_risk("06:30")
    late, _ = _time_of_day_risk("23:15")
    assert early < late


def test_time_of_day_monotonic_through_day():
    hours = ["06:00", "10:00", "13:00", "16:00", "20:00", "23:00"]
    risks = [_time_of_day_risk(h)[0] for h in hours]
    assert risks == sorted(risks), "risk should not decrease as the day progresses"


async def test_connections_raise_score():
    gw = Gateway()
    nonstop = await assess_risk(_flight("10:00", stops=0), gw, explain=False)
    onestop = await assess_risk(_flight("10:00", stops=1), gw, explain=False)
    assert onestop.score > nonstop.score


async def test_score_in_bounds_and_has_components():
    gw = Gateway()
    r = await assess_risk(_flight("10:00"), gw, explain=False)
    assert 0 <= r.score <= 100
    assert set(r.components) == {"time_of_day", "airline", "weather", "connections", "congestion"}
