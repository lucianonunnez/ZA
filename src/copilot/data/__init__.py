"""Bundled offline datasets + loader helpers."""

from __future__ import annotations

import json
from functools import cache
from importlib import resources


@cache
def _load(name: str) -> dict:
    with resources.files("copilot.data").joinpath(name).open() as fh:
        return json.load(fh)


def airports() -> dict:
    return _load("airports.json")


def airlines() -> dict:
    return {k: v for k, v in _load("airlines.json").items() if not k.startswith("_")}


@cache
def icao_to_iata() -> dict:
    """Reverse map of airport ICAO -> IATA, for resolving OpenSky arrival codes."""
    return {a["icao"]: iata for iata, a in airports().items() if a.get("icao")}


@cache
def airline_name_by_iata() -> dict:
    """IATA airline code -> display name (for sources that return IATA codes)."""
    return {v["iata"]: v["name"] for v in airlines().values()}


def airline_reliability() -> dict:
    return _load("airlines_reliability.json")


def sample_flights() -> dict:
    return _load("sample_flights.json")
