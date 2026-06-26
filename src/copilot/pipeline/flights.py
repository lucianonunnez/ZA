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


async def search_flights_async(brief: TripBrief) -> list[FlightOption]:
    """Real flight search for any route when configured, else bundled inventory.

    Order: Amadeus (if creds) → OpenSky (real flights, any route, free, no key —
    when COPILOT_FLIGHT_SOURCE=opensky) → Playwright scraper (if =scrape) →
    bundled offline inventory. Each step falls back on empty/failure, so the
    pipeline always returns *something* and never crashes.
    """
    from copilot.config import settings

    origin, dest = _to_iata(brief.origin), _to_iata(brief.destination)
    source = os.getenv("COPILOT_FLIGHT_SOURCE", "")

    if settings.amadeus_enabled:
        from copilot.pipeline.amadeus import AmadeusFlightSource

        real = await AmadeusFlightSource(settings).search(brief, origin, dest)
        if real:
            return _rank(real)

    if source == "opensky":
        from copilot.pipeline.opensky_source import OpenSkyFlightSource

        live = await OpenSkyFlightSource().search(brief, origin, dest)
        if live:
            return _rank(live)

    if source == "scrape":
        from copilot.pipeline.scraper import ScraperFlightSource

        scraped = await ScraperFlightSource().search(brief)
        if scraped:
            return _rank(scraped)

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
