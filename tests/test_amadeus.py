"""Amadeus adapter: parsing + safe fallback (no network needed)."""

from copilot.config import Settings
from copilot.pipeline.amadeus import AmadeusFlightSource, _iso_duration_to_min
from copilot.pipeline.flights import search_flights_async
from copilot.schemas import Cabin, TripBrief

# A trimmed real-shaped Amadeus Flight Offers response.
_SAMPLE_OFFER = {
    "itineraries": [
        {
            "duration": "PT7H25M",
            "segments": [
                {
                    "carrierCode": "BA", "number": "112",
                    "departure": {"iataCode": "JFK", "at": "2026-07-09T18:30:00"},
                    "arrival": {"iataCode": "LHR", "at": "2026-07-10T06:55:00"},
                }
            ],
        }
    ],
    "price": {"grandTotal": "3812.40", "currency": "USD"},
}


def test_iso_duration_parsing():
    assert _iso_duration_to_min("PT7H25M") == 445
    assert _iso_duration_to_min("PT45M") == 45
    assert _iso_duration_to_min("") == 0


def test_parse_offer_maps_fields():
    brief = TripBrief(origin="JFK", destination="LHR", cabin=Cabin.business)
    opt = AmadeusFlightSource(Settings())._parse_offer(_SAMPLE_OFFER, brief)
    assert opt is not None
    assert opt.carrier == "British Airways"
    assert opt.flight_no == "BA112"
    assert opt.origin == "JFK" and opt.destination == "LHR"
    assert opt.depart == "18:30" and opt.arrive == "06:55"
    assert opt.duration_min == 445
    assert opt.cash_price_usd == 3812.40
    assert opt.points_price is None  # Amadeus = cash only; we don't fabricate points


def test_parse_offer_bad_payload_returns_none():
    brief = TripBrief(origin="JFK", destination="LHR")
    assert AmadeusFlightSource(Settings())._parse_offer({"garbage": True}, brief) is None


async def test_search_falls_back_to_inventory_without_amadeus_creds():
    # No AMADEUS creds in the default Settings -> bundled inventory is used.
    options = await search_flights_async(TripBrief(origin="JFK", destination="LHR"))
    assert options
    assert options[0].origin == "JFK"
