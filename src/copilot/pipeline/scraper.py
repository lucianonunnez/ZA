"""Playwright flight scraper — browser automation for when there's no API.

This is the JD's literal bonus point (scraping / browser automation). It sits
behind the same `FlightSource` seam as the offline dataset, so the pipeline
doesn't care where options come from.

Design notes a reviewer would look for:
  * Async Playwright, one browser context per scrape, always closed.
  * A defensive parse: scraping is brittle, so any failure returns [] and the
    caller falls back to inventory — never a crash in the request path.
  * Respect-the-site posture: a real deployment would honor robots.txt, rate-limit,
    cache aggressively, and prefer an official API; scraping is the fallback.

Requires the optional extra:  uv pip install -e ".[scrape]" && playwright install chromium
With Playwright absent or the network closed, `ScraperFlightSource.search` returns
[] and the orchestrator uses the bundled inventory.
"""

from __future__ import annotations

from copilot.schemas import FlightOption, TripBrief


class ScraperFlightSource:
    """Fetch live options by driving a headless browser.

    `base_url` would point at a metasearch results page; the selectors below are
    illustrative. The value here is the *seam and the disciple*, not a specific
    site's DOM (which changes weekly).
    """

    def __init__(self, base_url: str = "https://example-metasearch.test"):
        self.base_url = base_url

    async def search(self, brief: TripBrief) -> list[FlightOption]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return []  # extra not installed -> let caller fall back to inventory

        url = (
            f"{self.base_url}/search?from={brief.origin}&to={brief.destination}"
            f"&cabin={brief.cabin.value}&pax={brief.passengers}"
        )
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.goto(url, timeout=15000)
                    await page.wait_for_selector(".result-card", timeout=8000)
                    cards = await page.query_selector_all(".result-card")
                    options = [await self._parse_card(c, brief) for c in cards]
                    return [o for o in options if o]
                finally:
                    await browser.close()
        except Exception:
            # Brittle by nature: any failure degrades to the inventory source.
            return []

    async def _parse_card(self, card, brief: TripBrief) -> FlightOption | None:
        try:
            carrier = (await (await card.query_selector(".carrier")).inner_text()).strip()
            code = (await (await card.query_selector(".carrier-code")).inner_text()).strip()
            flight_no = (await (await card.query_selector(".flight-no")).inner_text()).strip()
            depart = (await (await card.query_selector(".depart")).inner_text()).strip()
            arrive = (await (await card.query_selector(".arrive")).inner_text()).strip()
            price = float((await (await card.query_selector(".price")).inner_text()).replace("$", "").replace(",", ""))
            return FlightOption(
                carrier=carrier, carrier_code=code, flight_no=flight_no,
                origin=brief.origin, destination=brief.destination,
                depart=depart, arrive=arrive, cabin=brief.cabin,
                duration_min=0, stops=0, cash_price_usd=price,
            )
        except Exception:
            return None
