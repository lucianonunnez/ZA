"""Weather signal for disruption risk.

Online: Open-Meteo (free, no key) for a precipitation/wind forecast at the
arrival airport. Offline or on any network error: a deterministic seasonal
heuristic from latitude, so risk scoring still works in a closed sandbox.
"""

from __future__ import annotations

import httpx

from copilot.data import airports

_FORECAST = "https://api.open-meteo.com/v1/forecast"


async def weather_risk(iata: str) -> tuple[float, list[str]]:
    """Return (risk_0_to_100, drivers). Never raises — degrades to heuristic."""
    apt = airports().get(iata)
    if not apt:
        return 25.0, ["unknown airport — assumed average weather risk"]
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                _FORECAST,
                params={
                    "latitude": apt["lat"],
                    "longitude": apt["lon"],
                    "hourly": "precipitation,wind_speed_10m,snowfall",
                    "forecast_days": 2,
                },
            )
            resp.raise_for_status()
            hourly = resp.json()["hourly"]
        precip = max(hourly.get("precipitation", [0]) or [0])
        wind = max(hourly.get("wind_speed_10m", [0]) or [0])
        snow = max(hourly.get("snowfall", [0]) or [0])
        risk = min(100.0, precip * 8 + max(0, wind - 25) * 2 + snow * 20)
        drivers = []
        if precip > 2:
            drivers.append(f"rain up to {precip:.1f}mm forecast")
        if wind > 30:
            drivers.append(f"strong winds ~{wind:.0f} km/h")
        if snow > 0:
            drivers.append(f"snowfall {snow:.1f}cm")
        if not drivers:
            drivers.append("calm forecast")
        return round(risk, 1), drivers
    except Exception:
        return _offline_heuristic(apt)


def _offline_heuristic(apt: dict) -> tuple[float, list[str]]:
    # Higher-latitude airports carry more weather-disruption risk on average.
    lat = abs(apt["lat"])
    risk = round(min(60.0, 10 + lat * 0.6), 1)
    return risk, [f"offline estimate from latitude {apt['lat']:.0f}° (no live weather)"]
