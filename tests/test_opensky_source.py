"""OpenSky flight source: reconstruction from real-shaped ADS-B data (offline)."""

from copilot.pipeline.opensky_source import (
    OpenSkyFlightSource,
    _carrier_from_callsign,
    haversine_km,
)
from copilot.schemas import Cabin, TripBrief

# A trimmed real-shaped OpenSky /flights/departure response from KJFK.
# firstSeen/lastSeen are unix UTC; 1719390600 = 2024-06-26 09:50:00Z.
_DEPARTURES = [
    {"icao24": "400abc", "callsign": "BAW178  ", "firstSeen": 1719390600,
     "lastSeen": 1719417300, "estDepartureAirport": "KJFK", "estArrivalAirport": "EGLL"},
    {"icao24": "a1b2c3", "callsign": "VIR004  ", "firstSeen": 1719394200,
     "lastSeen": 1719421800, "estDepartureAirport": "KJFK", "estArrivalAirport": "EGLL"},
    {"icao24": "ddeeff", "callsign": "DAL215  ", "firstSeen": 1719380000,
     "lastSeen": 1719400000, "estDepartureAirport": "KJFK", "estArrivalAirport": "KLAX"},
]


def test_haversine_jfk_lhr_distance():
    # JFK->LHR is ~5540 km; allow a margin.
    km = haversine_km(40.6413, -73.7781, 51.4700, -0.4543)
    assert 5400 < km < 5700


def test_callsign_parsing():
    assert _carrier_from_callsign("BAW178") == ("British Airways", "BA", "BA178")
    assert _carrier_from_callsign("ZZZ999")[1] == "ZZ"  # unknown -> raw prefix


def test_reconstruct_filters_to_destination_and_estimates_price():
    src = OpenSkyFlightSource()
    brief = TripBrief(origin="JFK", destination="LHR", cabin=Cabin.business)
    from copilot.data import airports

    apt = airports()
    opts = src._reconstruct(_DEPARTURES, brief, "JFK", "LHR", apt["JFK"], apt["LHR"])
    # Only the two LHR-bound flights, not the LAX one.
    assert len(opts) == 2
    assert {o.flight_no for o in opts} == {"BA178", "VS004"}
    for o in opts:
        assert o.estimated is True
        assert o.source == "opensky"
        assert o.cash_price_usd > 0
        assert o.points_price is None  # no fabricated award pricing
