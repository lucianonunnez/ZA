"""End-to-end orchestration: one free-text message in, a full concierge answer out.

    message -> extract(brief) -> search(flights) -> assess_risk(each) -> recommend

Risk assessment fans out concurrently across options (async) because each is an
independent model + weather call. The ledger underneath records every model call
so the caller can show cost/latency/fallbacks — evidence over vibes, end to end.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from copilot.gateway import Gateway
from copilot.memory.base import MemberProfile, MemoryStore
from copilot.pipeline.extract import extract_brief
from copilot.pipeline.flights import search_flights_async
from copilot.pipeline.recommend import recommend
from copilot.pipeline.risk import assess_risk
from copilot.schemas import Recommendation, ScoredOption, TripBrief


@dataclass
class ConciergeResult:
    brief: TripBrief
    recommendation: Recommendation
    trace: dict  # ledger summary: calls, cost, latency, models used, fallbacks
    member: MemberProfile | None = None


async def run_concierge(
    message: str,
    gateway: Gateway | None = None,
    *,
    member_handle: str | None = None,
    store: MemoryStore | None = None,
) -> ConciergeResult:
    gw = gateway or Gateway()

    # Customer intelligence: load what we know about this member, if any.
    member: MemberProfile | None = None
    if member_handle:
        from copilot.memory import default_store

        member = (store or default_store()).get(member_handle)

    brief = await extract_brief(message, gw, member=member)
    flights = await search_flights_async(brief)

    risks = await asyncio.gather(*(assess_risk(f, gw) for f in flights))
    scored = [ScoredOption(flight=f, risk=r) for f, r in zip(flights, risks)]
    # Re-rank by risk-adjusted desirability happens inside recommend().
    rec = await recommend(brief, scored, gw)

    return ConciergeResult(
        brief=brief, recommendation=rec, trace=gw.ledger.summary(), member=member
    )
