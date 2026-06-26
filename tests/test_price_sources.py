"""Travelpayouts parsing + the source-switch cascade (offline)."""

from copilot.config import Settings
from copilot.pipeline.flights import _source_chain
from copilot.pipeline.travelpayouts import TravelpayoutsFlightSource
from copilot.schemas import Cabin, TripBrief

# A trimmed real-shaped Aviasales Data API /prices_for_dates row.
_TP_ROW = {
    "origin": "JFK", "destination": "LHR", "price": 3120.0,
    "airline": "BA", "flight_number": 178, "departure_at": "2026-07-09T18:30:00+00:00",
    "transfers": 0, "duration_to": 445,
}


def test_travelpayouts_parse_real_fare():
    brief = TripBrief(origin="JFK", destination="LHR", cabin=Cabin.business)
    opt = TravelpayoutsFlightSource(Settings())._parse(_TP_ROW, brief)
    assert opt is not None
    assert opt.carrier == "British Airways"
    assert opt.flight_no == "BA178"
    assert opt.depart == "18:30"
    assert opt.cash_price_usd == 3120.0
    assert opt.estimated is False          # a real fare, not an estimate
    assert opt.source == "travelpayouts"


def test_travelpayouts_disabled_returns_empty_without_token():
    s = Settings()
    s.travelpayouts_token = ""
    assert s.travelpayouts_enabled is False


def test_source_chain_switch():
    s = Settings()
    s.travelpayouts_token = "tok"
    # auto cascades through all available real sources, best data first.
    assert _source_chain("auto", s) == ["travelpayouts", "fastflights", "opensky"]
    # a specific value forces just that one.
    assert _source_chain("opensky", s) == ["opensky"]
    # unset -> no network sources (offline: inventory/synthetic only).
    assert _source_chain("", s) == []
