"""Amadeus Self-Service adapter — real flight search for ANY route.

OAuth2 client-credentials → Flight Offers Search. Free tier uses the test host
(set AMADEUS_HOSTNAME=production for live data). Activated only when
AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET are set; otherwise the caller falls
back to the bundled inventory, so nothing breaks without keys.

Honest note: Amadeus returns cash fares, not award/points pricing, so the
points-arbitrage fields are left empty for real results — we don't fabricate them.
"""

from __future__ import annotations

import datetime as _dt
import re

import httpx

from copilot.config import Settings
from copilot.config import settings as global_settings
from copilot.schemas import Cabin, FlightOption, TripBrief

_CABIN_TO_AMADEUS = {
    Cabin.economy: "ECONOMY",
    Cabin.premium_economy: "PREMIUM_ECONOMY",
    Cabin.business: "BUSINESS",
    Cabin.first: "FIRST",
}

# Carrier code -> display name (extends the reliability table for unknowns).
_CARRIERS = {
    "BA": "British Airways", "AA": "American Airlines", "DL": "Delta Air Lines",
    "UA": "United Airlines", "VS": "Virgin Atlantic", "AF": "Air France",
    "KL": "KLM", "LH": "Lufthansa", "IB": "Iberia", "EK": "Emirates",
    "QR": "Qatar Airways", "SQ": "Singapore Airlines", "CX": "Cathay Pacific",
    "TK": "Turkish Airlines", "LA": "LATAM", "AR": "Aerolineas Argentinas",
}


def _iso_duration_to_min(iso: str) -> int:
    """'PT7H55M' -> 475 minutes."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso or "")
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return h * 60 + mins


def _default_date() -> str:
    """Amadeus requires a date; default to ~2 weeks out if the brief has none."""
    return (_dt.date.today() + _dt.timedelta(days=14)).isoformat()


class AmadeusFlightSource:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or global_settings
        self._token: str | None = None

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            f"{self.settings.amadeus_base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.amadeus_client_id,
                "client_secret": self.settings.amadeus_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    async def search(self, brief: TripBrief, origin: str, dest: str) -> list[FlightOption]:
        """Return real flight options, or [] on any failure (caller falls back)."""
        if not self.settings.amadeus_enabled:
            return []
        depart = brief.depart_date.isoformat() if brief.depart_date else _default_date()
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": dest,
            "departureDate": depart,
            "adults": str(max(1, brief.passengers)),
            "travelClass": _CABIN_TO_AMADEUS.get(brief.cabin, "ECONOMY"),
            "currencyCode": "USD",
            "max": "4",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                token = await self._access_token(client)
                resp = await client.get(
                    f"{self.settings.amadeus_base_url}/v2/shopping/flight-offers",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []
        return [o for o in (self._parse_offer(off, brief) for off in data.get("data", [])) if o]

    def _parse_offer(self, offer: dict, brief: TripBrief) -> FlightOption | None:
        try:
            itin = offer["itineraries"][0]
            segs = itin["segments"]
            first, last = segs[0], segs[-1]
            code = first["carrierCode"]
            return FlightOption(
                carrier=_CARRIERS.get(code, code),
                carrier_code=code,
                flight_no=f"{code}{first['number']}",
                origin=first["departure"]["iataCode"],
                destination=last["arrival"]["iataCode"],
                depart=first["departure"]["at"][11:16],
                arrive=last["arrival"]["at"][11:16],
                cabin=brief.cabin,
                duration_min=_iso_duration_to_min(itin.get("duration", "")),
                stops=len(segs) - 1,
                cash_price_usd=float(offer["price"]["grandTotal"]),
                # Amadeus = cash fares only; no award pricing, so points stay empty.
            )
        except (KeyError, IndexError, ValueError):
            return None
