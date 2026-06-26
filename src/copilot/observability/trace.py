"""Cost/latency ledger. Evidence over vibes: every model call is recorded."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field


@dataclass
class TraceEvent:
    ts: float
    stage: str
    tier: str
    model: str
    provider: str
    in_tokens: int
    out_tokens: int
    cost_usd: float
    latency_ms: float
    fell_back_from: str | None = None


@dataclass
class Ledger:
    """In-memory ledger that also appends JSONL to disk for later inspection."""

    trace_dir: str = "traces"
    events: list[TraceEvent] = field(default_factory=list)
    _path: str | None = None

    def _ensure_path(self) -> str:
        if self._path is None:
            os.makedirs(self.trace_dir, exist_ok=True)
            self._path = os.path.join(self.trace_dir, f"run-{int(time.time())}.jsonl")
        return self._path

    def record(self, event: TraceEvent) -> None:
        self.events.append(event)
        try:
            with open(self._ensure_path(), "a") as fh:
                fh.write(json.dumps(asdict(event)) + "\n")
        except OSError:
            pass  # tracing must never break the request path

    @property
    def total_cost(self) -> float:
        return round(sum(e.cost_usd for e in self.events), 6)

    @property
    def total_latency_ms(self) -> float:
        return round(sum(e.latency_ms for e in self.events), 1)

    def summary(self) -> dict:
        by_model: dict[str, dict] = {}
        for e in self.events:
            m = by_model.setdefault(e.model, {"calls": 0, "cost_usd": 0.0, "tokens": 0})
            m["calls"] += 1
            m["cost_usd"] = round(m["cost_usd"] + e.cost_usd, 6)
            m["tokens"] += e.in_tokens + e.out_tokens
        return {
            "calls": len(self.events),
            "total_cost_usd": self.total_cost,
            "total_latency_ms": self.total_latency_ms,
            "by_model": by_model,
            "fallbacks": sum(1 for e in self.events if e.fell_back_from),
        }
