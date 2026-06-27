import pytest

from copilot.pipeline import run_concierge
from copilot.pipeline.flights import _to_iata, search_flights
from copilot.schemas import TripBrief


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Roma", "FCO"),       # other-language city name
        ("roma", "FCO"),       # casing
        ("FCO", "FCO"),        # explicit IATA
        ("fco", "FCO"),        # lower-case IATA
        ("Rome", "FCO"),       # English name, derived from the data
        ("Dubái", "DXB"),      # accents
        ("Tokio", "NRT"),      # Spanish name
        ("romaa", "FCO"),      # typo -> fuzzy match
        ("lndon", "LHR"),      # typo
        ("nyc", "JFK"),        # nickname
        ("KJFK", "JFK"),       # ICAO code
        ("fly me to rome", "FCO"),  # a place named inside a phrase
    ],
)
def test_city_resolution_discovers_iata(text, expected):
    assert _to_iata(text) == expected


def test_unknown_place_flows_through_unchanged():
    assert _to_iata("ZZZ") == "ZZZ"


def test_flights_sorted_by_points_savings():
    brief = TripBrief(origin="JFK", destination="LHR")
    options = search_flights(brief)
    assert options
    savings = [o.savings_pct or 0 for o in options]
    assert savings == sorted(savings, reverse=True)


async def test_end_to_end_runs_offline():
    res = await run_concierge("NYC to London business class thursday, morning arrival")
    assert res.brief.origin == "JFK"
    assert res.brief.destination == "LHR"
    assert res.recommendation.recommended_index >= 0
    assert res.trace["calls"] > 0
    assert res.trace["total_cost_usd"] >= 0


async def test_unparseable_route_degrades_gracefully():
    res = await run_concierge("hi there")
    # No matching inventory -> safe fallback, never a crash.
    assert res.recommendation is not None
