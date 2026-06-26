"""Stage 2 — turn a TripBrief into concrete FlightOptions with points arbitrage.

Offline: serves a curated inventory so the demo always has something to show.
Online: drop a real flight API (Amadeus/Kiwi) or a Playwright scraper behind
`search_flights` — the rest of the pipeline doesn't change. Scraping is your
literal bonus point in the JD, so the seam is deliberately clean.
"""

from __future__ import annotations

import os
from functools import cache

from copilot.data import airports, sample_flights
from copilot.schemas import Cabin, FlightOption, TripBrief

# A few aliases the airport data's city field doesn't cover verbatim.
_CITY_ALIASES = {
    "nyc": "JFK", "new york city": "JFK", "londres": "LHR",
    "sao paulo": "GRU", "são paulo": "GRU", "saint petersburg": "LED",
}


@cache
def _city_to_iata() -> dict[str, str]:
    """Build city -> primary IATA from the airport dataset (first airport wins)."""
    mapping = dict(_CITY_ALIASES)
    for iata, a in airports().items():
        city = a.get("city", "").lower()
        if city and city not in mapping:
            mapping[city] = iata
    return mapping


def _to_iata(value: str) -> str:
    v = value.strip()
    if v.upper() in airports():
        return v.upper()
    return _city_to_iata().get(v.lower(), v.upper())


def _rank(options: list[FlightOption]) -> list[FlightOption]:
    # Best points-arbitrage first, then cheapest cash (points may be absent).
    options.sort(key=lambda o: (-(o.savings_pct or 0), o.cash_price_usd))
    return options


def _source_chain(mode: str, settings) -> list[str]:
    """Which real sources to try, in order, given the COPILOT_FLIGHT_SOURCE switch.

    "auto" cascades through every available real source (best data first);
    a specific value forces just that one; "" stays offline (inventory/synthetic).
    Amadeus always leads when its creds are set.
    """
    chain: list[str] = []
    if settings.amadeus_enabled:
        chain.append("amadeus")
    if mode in ("auto", "travelpayouts") and settings.travelpayouts_enabled:
        chain.append("travelpayouts")
    if mode in ("auto", "fastflights"):
        chain.append("fastflights")
    if mode in ("auto", "opensky"):
        chain.append("opensky")
    if mode == "scrape":
        chain.append("scrape")
    return chain


async def _run_source(key: str, brief: TripBrief, origin: str, dest: str, settings) -> list:
    if key == "amadeus":
        from copilot.pipeline.amadeus import AmadeusFlightSource
        return await AmadeusFlightSource(settings).search(brief, origin, dest)
    if key == "travelpayouts":
        from copilot.pipeline.travelpayouts import TravelpayoutsFlightSource
        return await TravelpayoutsFlightSource(settings).search(brief, origin, dest)
    if key == "fastflights":
        from copilot.pipeline.fastflights_source import FastFlightsSource
        return await FastFlightsSource().search(brief, origin, dest)
    if key == "opensky":
        from copilot.pipeline.opensky_source import OpenSkyFlightSource
        return await OpenSkyFlightSource().search(brief, origin, dest)
    if key == "scrape":
        from copilot.pipeline.scraper import ScraperFlightSource
        return await ScraperFlightSource().search(brief)
    return []


async def search_flights_async(brief: TripBrief) -> list[FlightOption]:
    """Cascade real flight sources (a switch), then inventory, then synthetic.

    COPILOT_FLIGHT_SOURCE: "auto" tries every available real source in priority
    order (Amadeus → Travelpayouts → fast-flights → OpenSky); a specific value
    forces one; unset stays offline. Whatever a source can't cover falls through,
    so a known city pair never comes back empty — and nothing ever crashes.
    """
    from copilot.config import settings

    origin, dest = _to_iata(brief.origin), _to_iata(brief.destination)
    mode = os.getenv("COPILOT_FLIGHT_SOURCE", "").lower()

    for key in _source_chain(mode, settings):
        try:
            real = await _run_source(key, brief, origin, dest, settings)
        except Exception:
            real = []
        if real:
            return _rank(real)

    # Curated inventory (hand-tuned points arbitrage) for the routes we have it on.
    inventory = search_flights(brief)
    if inventory:
        return inventory

    # Universal fallback: never come back empty for a known city pair.
    from copilot.pipeline.synthetic_source import synthesize

    return _rank(synthesize(brief, origin, dest))


def search_flights(brief: TripBrief) -> list[FlightOption]:
    origin, dest = _to_iata(brief.origin), _to_iata(brief.destination)
    raw = sample_flights().get(f"{origin}-{dest}", [])
    options: list[FlightOption] = []
    for r in raw:
        options.append(
            FlightOption(
                carrier=r["carrier"],
                carrier_code=r["carrier_code"],
                flight_no=r["flight_no"],
                origin=origin,
                destination=dest,
                depart=r["depart"],
                arrive=r["arrive"],
                cabin=Cabin(r["cabin"]),
                duration_min=r["duration_min"],
                stops=r["stops"],
                cash_price_usd=r["cash_price_usd"],
                points_price=r.get("points_price"),
                points_program=r.get("points_program"),
                points_cash_value_usd=r.get("points_cash_value_usd"),
            )
        )
    # Best arbitrage first (largest points-vs-cash saving), then cheapest cash.
    options.sort(key=lambda o: (-(o.savings_pct or 0), o.cash_price_usd))
    return options
