"""Synthetic flight generator — the universal coverage fallback.

Real sources (Amadeus, OpenSky) don't cover every route or are rate-limited, so a
quote must never come back empty for a known city pair. This builds plausible,
*clearly estimated* options for any two airports we have coordinates for: real
carrier names, distance-based price and duration, departures spread across the
day so the time-of-day disruption risk varies meaningfully.

Honest by construction: every option is estimated=True and labeled "est." in the
UI; we never imply these are live fares. Real-time weather and reliability still
apply on top, so the risk read is genuine even when the fare is an estimate.
Deterministic (no randomness) so the same route always yields the same options.
"""

from __future__ import annotations

from copilot.data import airlines, airports
from copilot.pipeline.opensky_source import _estimate_price, haversine_km
from copilot.schemas import FlightOption, TripBrief

# Spread so risk varies: a calm morning, a midday, a higher-risk evening.
_DEPARTS = ["07:30", "13:15", "19:45"]


def _carriers_for_route(origin: str, dest: str, n: int) -> list[tuple[str, str]]:
    """Pick n (name, iata) carriers deterministically from the route string."""
    pool = [(v["name"], v["iata"]) for v in airlines().values()]
    seed = sum(ord(c) for c in f"{origin}{dest}")
    return [pool[(seed + i) % len(pool)] for i in range(n)]


def _add_minutes(hhmm: str, minutes: int) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    total = (h * 60 + m + minutes) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def synthesize(brief: TripBrief, origin: str, dest: str) -> list[FlightOption]:
    apt = airports()
    o, d = apt.get(origin), apt.get(dest)
    if not o or not d:
        return []  # unknown airport -> let the caller show a graceful message

    distance = haversine_km(o["lat"], o["lon"], d["lat"], d["lon"])
    duration = int(distance / 800 * 60 + 30)
    base_price = _estimate_price(distance, brief.cabin)

    options: list[FlightOption] = []
    for i, (name, code) in enumerate(_carriers_for_route(origin, dest, 3)):
        depart = _DEPARTS[i % len(_DEPARTS)]
        # Small price spread so options aren't identical.
        price = round(base_price * (0.95 + 0.06 * i), 0)
        options.append(
            FlightOption(
                carrier=name, carrier_code=code, flight_no=f"{code}{100 + i * 7}",
                origin=origin, destination=dest,
                depart=depart, arrive=_add_minutes(depart, duration),
                cabin=brief.cabin, duration_min=duration, stops=0,
                cash_price_usd=price, estimated=True, source="synthetic",
            )
        )
    return options
