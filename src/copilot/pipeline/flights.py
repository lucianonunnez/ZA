"""Stage 2 — turn a TripBrief into concrete FlightOptions with points arbitrage.

Offline: serves a curated inventory so the demo always has something to show.
Online: drop a real flight API (Amadeus/Kiwi) or a Playwright scraper behind
`search_flights` — the rest of the pipeline doesn't change. Scraping is your
literal bonus point in the JD, so the seam is deliberately clean.
"""

from __future__ import annotations

import os

from copilot.data import airports, sample_flights
from copilot.schemas import Cabin, FlightOption, TripBrief

# City -> primary IATA, so "London"/"Londres" resolves to a code we have data for.
_CITY_TO_IATA = {
    "new york": "JFK", "nyc": "JFK",
    "london": "LHR", "londres": "LHR",
    "buenos aires": "EZE",
    "miami": "MIA", "paris": "CDG", "dubai": "DXB", "singapore": "SIN",
    "san francisco": "SFO",
}


def _to_iata(value: str) -> str:
    v = value.strip()
    if v.upper() in airports():
        return v.upper()
    return _CITY_TO_IATA.get(v.lower(), v.upper())


async def search_flights_async(brief: TripBrief) -> list[FlightOption]:
    """Live source first (Playwright scraper, if enabled), else bundled inventory.

    Set COPILOT_FLIGHT_SOURCE=scrape to try the browser scraper; it falls back to
    inventory automatically when Playwright/network is unavailable.
    """
    if os.getenv("COPILOT_FLIGHT_SOURCE") == "scrape":
        from copilot.pipeline.scraper import ScraperFlightSource

        scraped = await ScraperFlightSource().search(brief)
        if scraped:
            scraped.sort(key=lambda o: (-(o.savings_pct or 0), o.cash_price_usd))
            return scraped
    return search_flights(brief)


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
