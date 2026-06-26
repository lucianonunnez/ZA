"""Live flight status + inbound-aircraft tracking.

This is the upgrade from a *risk index* (a proxy, used at quote time) to a *live
signal* (used once a specific flight is booked). The #1 disruption driver is the
late-arriving aircraft; ADS-B lets us watch that feeder leg directly and for free.

Two real backends sit behind this seam (wire them on a machine with network + keys):

  * Schedule/status: AeroDataBox (cheap) or AviationStack (free 500/mo) — resolves
    `flight_no + date` to status, scheduled/estimated times, and the AIRCRAFT
    REGISTRATION. That registration is what makes the next step possible.
  * Live position: OpenSky Network (free, 4k credits/day) — given the aircraft's
    icao24/callsign, returns whether it's airborne and where, so we can see if its
    inbound leg is already running late.

Offline (no key / closed network), `live_flight_status` returns a deterministic
mock so the demo and tests still run. The point is the *design*: when a real
inbound delay is observed, it dominates the static index.
"""

from __future__ import annotations

import os

import httpx

from copilot.schemas import FlightStatus, InboundStatus

_AERODATABOX = "https://aerodatabox.p.rapidapi.com"
_OPENSKY = "https://opensky-network.org/api"


async def live_flight_status(flight_no: str, date: str | None = None) -> FlightStatus:
    """Best-effort live status. Never raises — degrades to a mock when offline."""
    key = os.getenv("AERODATABOX_API_KEY", "")
    if not key:
        return _mock_status(flight_no)
    try:
        return await _aerodatabox_status(flight_no, date, key)
    except Exception:
        return _mock_status(flight_no, source="unavailable")


async def _aerodatabox_status(flight_no: str, date: str | None, key: str) -> FlightStatus:
    """Resolve status + aircraft reg, then ask OpenSky about the inbound leg."""
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": "aerodatabox.p.rapidapi.com"}
    url = f"{_AERODATABOX}/flights/number/{flight_no}"
    if date:
        url += f"/{date}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    leg = data[0] if isinstance(data, list) and data else data
    dep = leg.get("departure", {})
    reg = (leg.get("aircraft") or {}).get("reg")
    sched = (dep.get("scheduledTime") or {}).get("utc")
    est = (dep.get("revisedTime") or {}).get("utc")
    delay = int(dep.get("delayMinutes") or 0)

    inbound = await _opensky_inbound(reg) if reg else None
    return FlightStatus(
        flight_no=flight_no,
        status=leg.get("status", "unknown").lower(),
        scheduled_departure=sched,
        estimated_departure=est,
        departure_delay_min=delay,
        aircraft_reg=reg,
        inbound=inbound,
        source="aerodatabox",
    )


async def _opensky_inbound(reg: str) -> InboundStatus:
    """Look up the aircraft's recent flights via OpenSky to estimate inbound delay.

    Simplified: in production you'd map reg->icao24, pull /flights/aircraft for the
    last few hours, and compare the inbound arrival vs schedule. Here we just probe
    reachability and return a conservative 'airborne, on schedule' read.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{_OPENSKY}/states/all", params={"icao24": reg.lower()})
            resp.raise_for_status()
            states = resp.json().get("states") or []
        return InboundStatus(aircraft_reg=reg, airborne=bool(states), source="opensky")
    except Exception:
        return InboundStatus(aircraft_reg=reg, source="unavailable")


def _mock_status(flight_no: str, source: str = "mock") -> FlightStatus:
    """Deterministic offline status, varied by flight number so demos differ.

    One flight in the sample set ('AA100') is made to look like its feeder is late,
    to demonstrate the live override taking over from the static index.
    """
    late = flight_no.upper().endswith("100")
    inbound = InboundStatus(
        aircraft_reg="G-XWBA",
        inbound_flight_no=flight_no[:2] + "099",
        inbound_from="MAD",
        airborne=True,
        inbound_delay_min=55 if late else 0,
        source=source,
    )
    return FlightStatus(
        flight_no=flight_no,
        status="delayed" if late else "scheduled",
        scheduled_departure="18:30Z",
        estimated_departure="19:25Z" if late else "18:30Z",
        departure_delay_min=55 if late else 0,
        aircraft_reg="G-XWBA",
        inbound=inbound,
        source=source,
    )


def live_risk_override(status: FlightStatus) -> tuple[float, list[str]] | None:
    """If we have a real live signal, translate it into a risk score that should
    DOMINATE the static index. Returns (score_0_100, drivers) or None if no signal.
    """
    if status.source in ("unknown", "unavailable"):
        return None
    if status.status == "cancelled":
        return 100.0, ["flight is CANCELLED (live)"]
    delay = max(
        status.departure_delay_min,
        status.inbound.inbound_delay_min if status.inbound else 0,
    )
    if delay <= 0:
        return 8.0, ["live: on schedule, inbound aircraft tracking on time"]
    drivers = [f"live: departure delayed ~{status.departure_delay_min} min"]
    if status.inbound and status.inbound.inbound_delay_min > 0:
        drivers.append(
            f"inbound {status.inbound.inbound_flight_no} from {status.inbound.inbound_from} "
            f"running ~{status.inbound.inbound_delay_min} min late"
        )
    score = min(100.0, 30.0 + delay * 1.2)
    return round(score, 1), drivers
