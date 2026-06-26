"""Bundled offline datasets + loader helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    with resources.files("copilot.data").joinpath(name).open() as fh:
        return json.load(fh)


def airports() -> dict:
    return _load("airports.json")


def airline_reliability() -> dict:
    return _load("airlines_reliability.json")


def sample_flights() -> dict:
    return _load("sample_flights.json")
