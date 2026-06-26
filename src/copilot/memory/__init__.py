"""Member memory / customer intelligence.

The compounding-value layer: the system learns each member's revealed
preferences over time so the *next* quote is better and faster than the first.
This is the JD's "customer intelligence" leverage point.

Persistence is behind a `MemoryStore` protocol (dependency inversion), so the
offline JSON store and the production Django/Postgres store are interchangeable.
"""

from copilot.memory.base import MemberProfile, MemoryStore, TripOutcome
from copilot.memory.json_store import JsonMemoryStore, default_store

__all__ = ["MemberProfile", "TripOutcome", "MemoryStore", "JsonMemoryStore", "default_store"]
