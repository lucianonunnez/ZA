"""Synthetic fallback: any known route returns labeled estimated options."""

from copilot.pipeline.flights import search_flights_async
from copilot.pipeline.synthetic_source import synthesize
from copilot.schemas import Cabin, TripBrief


def test_synthesize_returns_estimated_options_for_known_pair():
    brief = TripBrief(origin="EZE", destination="BCN", cabin=Cabin.business)
    opts = synthesize(brief, "EZE", "BCN")
    assert len(opts) == 3
    for o in opts:
        assert o.estimated is True
        assert o.source == "synthetic"
        assert o.cash_price_usd > 0
    # Departures spread across the day -> risk will vary.
    assert len({o.depart for o in opts}) == 3


def test_synthesize_unknown_airport_is_empty():
    brief = TripBrief(origin="UNKNOWN", destination="ZZZ")
    assert synthesize(brief, "UNKNOWN", "ZZZ") == []


async def test_async_search_never_empty_for_known_route():
    # EZE-BCN isn't in curated inventory, but the synthetic fallback covers it.
    options = await search_flights_async(TripBrief(origin="Buenos Aires", destination="Barcelona"))
    assert options
    assert options[0].origin == "EZE" and options[0].destination == "BCN"
    assert all(o.estimated for o in options)
