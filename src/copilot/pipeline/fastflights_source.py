"""fast-flights source — real Google Flights prices, no API key.

Uses the `fast-flights` library (https://github.com/AWeirdDev/flights), which
reads Google Flights' internal endpoint — real prices, no signup. Best-effort:
it's a scraper, so it can be blocked (e.g. from datacenter IPs) or change shape;
any failure returns [] and the caller cascades on. Optional extra:

    pip install -e ".[flights]"

Honest note: real fares (estimated=False), but scraped — treat as best-effort.
"""

from __future__ import annotations

import datetime as _dt
import re

from copilot.data import airline_name_by_iata
from copilot.schemas import FlightOption, TripBrief

_SEAT = {"economy": "economy", "premium_economy": "premium-economy",
         "business": "business", "first": "first"}


def _price_to_float(text: str) -> float | None:
    m = re.search(r"[\d,]+", text or "")
    return float(m.group().replace(",", "")) if m else None


class FastFlightsSource:
    async def search(self, brief: TripBrief, origin: str, dest: str) -> list[FlightOption]:
        try:
            from fast_flights import FlightData, Passengers, get_flights
        except ImportError:
            return []  # extra not installed -> cascade on

        date = (brief.depart_date or (_dt.date.today() + _dt.timedelta(days=14))).isoformat()
        try:
            result = get_flights(
                flight_data=[FlightData(date=date, from_airport=origin, to_airport=dest)],
                trip="one-way",
                seat=_SEAT.get(brief.cabin.value, "economy"),
                passengers=Passengers(adults=max(1, brief.passengers)),
                fetch_mode="fallback",
            )
            flights = getattr(result, "flights", []) or []
        except Exception:
            return []

        options: list[FlightOption] = []
        for f in flights[:5]:
            price = _price_to_float(getattr(f, "price", "") or "")
            name = getattr(f, "name", "") or "Airline"
            if not price:
                continue
            code = _code_for(name)
            options.append(
                FlightOption(
                    carrier=name, carrier_code=code, flight_no=code,
                    origin=origin, destination=dest,
                    depart=_time_of(getattr(f, "departure", "")),
                    arrive=_time_of(getattr(f, "arrival", "")),
                    cabin=brief.cabin,
                    duration_min=0, stops=int(getattr(f, "stops", 0) or 0),
                    cash_price_usd=price, estimated=False, source="fastflights",
                )
            )
        return options


def _code_for(name: str) -> str:
    for iata, n in airline_name_by_iata().items():
        if n.lower() in name.lower():
            return iata
    return name[:2].upper()


def _time_of(text: str) -> str:
    m = re.search(r"(\d{1,2}:\d{2})", text or "")
    return m.group(1) if m else ""
