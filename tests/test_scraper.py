"""Scraper seam: must degrade to inventory, never crash, when Playwright/net absent."""

from copilot.pipeline.flights import search_flights_async
from copilot.pipeline.scraper import ScraperFlightSource
from copilot.schemas import TripBrief


async def test_scraper_returns_empty_without_playwright_or_network():
    # In CI/offline this returns [] (no Playwright browser / no network) — not an error.
    out = await ScraperFlightSource().search(TripBrief(origin="JFK", destination="LHR"))
    assert out == []


async def test_async_search_falls_back_to_inventory(monkeypatch):
    monkeypatch.setenv("COPILOT_FLIGHT_SOURCE", "scrape")
    # Scraper yields nothing offline -> we still get bundled inventory.
    options = await search_flights_async(TripBrief(origin="JFK", destination="LHR"))
    assert options
    assert options[0].origin == "JFK"
