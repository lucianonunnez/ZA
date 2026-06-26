"""Travelpayouts (Aviasales) Data API — real cached fares for any route, free.

Amadeus' free portal is being decommissioned; Travelpayouts is an active, free
alternative: sign up at travelpayouts.com, copy the API token, and the Aviasales
Data API returns real cached prices for any city pair. Activated when
TRAVELPAYOUTS_TOKEN is set; returns [] otherwise so the caller cascades on.

Honest note: prices are cached from recent searches (2-7 days old), so they're
real but may be slightly stale — labeled as real fares (estimated=False), not
fabricated. Docs:
https://support.travelpayouts.com/hc/en-us/articles/203956163-Aviasales-Data-API
"""

from __future__ import annotations

import datetime as _dt

import httpx

from copilot.config import Settings
from copilot.config import settings as global_settings
from copilot.data import airline_name_by_iata
from copilot.schemas import FlightOption, TripBrief

_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


class TravelpayoutsFlightSource:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or global_settings

    async def search(self, brief: TripBrief, origin: str, dest: str) -> list[FlightOption]:
        if not self.settings.travelpayouts_enabled:
            return []
        depart = (brief.depart_date or (_dt.date.today() + _dt.timedelta(days=14))).strftime("%Y-%m")
        params = {
            "origin": origin, "destination": dest, "departure_at": depart,
            "currency": "usd", "one_way": "true", "sorting": "price",
            "limit": "5", "token": self.settings.travelpayouts_token,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except Exception:
            return []
        if not payload.get("success"):
            return []
        return [o for o in (self._parse(r, brief) for r in payload.get("data", [])) if o]

    def _parse(self, row: dict, brief: TripBrief) -> FlightOption | None:
        try:
            code = row["airline"]
            depart_at = row.get("departure_at", "")
            return FlightOption(
                carrier=airline_name_by_iata().get(code, code),
                carrier_code=code,
                flight_no=f"{code}{row.get('flight_number', '')}",
                origin=row["origin"], destination=row["destination"],
                depart=depart_at[11:16] if len(depart_at) >= 16 else "",
                arrive="",
                cabin=brief.cabin,
                duration_min=int(row.get("duration_to") or row.get("duration") or 0),
                stops=int(row.get("transfers", 0)),
                cash_price_usd=float(row["price"]),
                estimated=False, source="travelpayouts",
            )
        except (KeyError, ValueError, TypeError):
            return None
