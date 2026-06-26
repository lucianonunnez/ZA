"""Offline JSON-backed member store — the zero-dependency default.

Good enough for the demo and tests; in production the Django/Postgres store
(same interface) takes over. Trip history is kept alongside the profile so
preference-learning is reproducible.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

from copilot.memory.base import MemberProfile, TripOutcome
from copilot.memory.learn import apply_outcome


class JsonMemoryStore:
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("COPILOT_MEMORY_PATH", "member_memory.json")

    def _read(self) -> dict:
        try:
            with open(self.path) as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        with open(self.path, "w") as fh:
            json.dump(data, fh, indent=2, default=str)

    def get(self, handle: str) -> MemberProfile | None:
        rec = self._read().get(handle)
        return MemberProfile.model_validate(rec["profile"]) if rec else None

    def upsert(self, profile: MemberProfile) -> MemberProfile:
        data = self._read()
        rec = data.setdefault(profile.handle, {"profile": {}, "history": []})
        rec["profile"] = profile.model_dump(mode="json")
        self._write(data)
        return profile

    def record_trip(self, handle: str, outcome: TripOutcome) -> MemberProfile:
        data = self._read()
        rec = data.setdefault(handle, {"profile": {"handle": handle}, "history": []})
        history = [TripOutcome.model_validate(h) for h in rec["history"]]
        profile = MemberProfile.model_validate(rec["profile"])

        updated = apply_outcome(profile, outcome, history)
        rec["profile"] = updated.model_dump(mode="json")
        rec["history"].append(outcome.model_dump(mode="json"))
        data[handle] = rec
        self._write(data)
        return updated


@lru_cache(maxsize=1)
def default_store() -> JsonMemoryStore:
    return JsonMemoryStore()
