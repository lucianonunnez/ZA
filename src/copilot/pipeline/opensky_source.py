"""OpenSky flight source — real flights for ANY route, free, no signup.

Amadeus' free self-service portal is being decommissioned (mid-2026), so the
resilient choice is a source with no vendor gate. OpenSky exposes real ADS-B
flight data for free: which aircraft actually departed an airport and where they
went. We query recent departures from the origin, keep the ones that landed at
the destination, and reconstruct flight options from real callsigns and times.

Honest about limits:
  * OpenSky has no fares, so price is a distance-based ESTIMATE (estimated=True,
    labeled "est." everywhere). We don't fabricate award/points pricing.
  * Departures are from the last couple of days (ADS-B is observational), so this
    reconstructs the routing/schedule that actually operates — not a future quote.
Everything else in the pipeline (reliability, weather, disruption risk) stays real.
Network/rate-limit failures return [] so the caller falls back to inventory.
"""

from __future__ import annotations

import math
import time

import httpx

from copilot.data import airlines, airports
from copilot.schemas import Cabin, FlightOption, TripBrief

_DEPARTURE_URL = "https://opensky-network.org/api/flights/departure"

# Rough cash price per km by cabin (USD), plus a fixed base — for the estimate only.
_RATE_PER_KM = {
    Cabin.economy: 0.11, Cabin.premium_economy: 0.22,
    Cabin.business: 0.42, Cabin.first: 0.75,
}
_BASE_FARE = {Cabin.economy: 60, Cabin.premium_economy: 120, Cabin.business: 300, Cabin.first: 600}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _estimate_price(distance_km: float, cabin: Cabin) -> float:
    return round(_BASE_FARE[cabin] + distance_km * _RATE_PER_KM[cabin], 0)


def _carrier_from_callsign(callsign: str) -> tuple[str, str, str]:
    """'BAW178 ' -> ('British Airways', 'BA', 'BA178'). Falls back to the raw prefix."""
    cs = (callsign or "").strip()
    prefix, number = cs[:3], cs[3:]
    info = airlines().get(prefix)
    if info:
        return info["name"], info["iata"], f"{info['iata']}{number}"
    return prefix or "Unknown", prefix[:2] or "??", cs or "?"


class OpenSkyFlightSource:
    def __init__(self, lookback_days: int = 2, now: int | None = None):
        self.lookback_days = lookback_days
        # `now` is injectable so tests/replays are deterministic.
        self._now = now

    async def search(self, brief: TripBrief, origin: str, dest: str) -> list[FlightOption]:
        apt = airports()
        o, d = apt.get(origin), apt.get(dest)
        if not o or not d or not o.get("icao") or not d.get("icao"):
            return []  # need ICAO + coords; let caller fall back

        end = self._now if self._now is not None else int(time.time())
        begin = end - self.lookback_days * 86400
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    _DEPARTURE_URL,
                    params={"airport": o["icao"], "begin": begin, "end": end},
                )
                resp.raise_for_status()
                rows = resp.json()
        except Exception:
            return []
        return self._reconstruct(rows, brief, origin, dest, o, d)

    def _reconstruct(self, rows, brief, origin, dest, o, d) -> list[FlightOption]:
        dest_icao = d["icao"]
        distance = haversine_km(o["lat"], o["lon"], d["lat"], d["lon"])
        cabin = brief.cabin
        price = _estimate_price(distance, cabin)
        duration = int(distance / 800 * 60 + 30)  # ~800 km/h cruise + taxi

        seen: set[str] = set()
        options: list[FlightOption] = []
        for r in rows:
            if r.get("estArrivalAirport") != dest_icao:
                continue
            callsign = (r.get("callsign") or "").strip()
            if not callsign or callsign in seen:
                continue
            seen.add(callsign)
            name, code, flight_no = _carrier_from_callsign(callsign)
            depart = time.strftime("%H:%M", time.gmtime(r["firstSeen"]))
            arrive = time.strftime("%H:%M", time.gmtime(r["lastSeen"]))
            options.append(
                FlightOption(
                    carrier=name, carrier_code=code, flight_no=flight_no,
                    origin=origin, destination=dest, depart=depart, arrive=arrive,
                    cabin=cabin, duration_min=duration, stops=0,
                    cash_price_usd=price, estimated=True, source="opensky",
                )
            )
            if len(options) >= 6:
                break
        options.sort(key=lambda x: x.depart)
        return options
