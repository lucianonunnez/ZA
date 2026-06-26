"""MCP server — exposes the concierge tools so an agent can call them.

This is the AI-native interface the JD asks for ("MCP: plug internal tooling into
an agent"). The concierge team's agent (Claude, etc.) can call `quote_trip`,
`watch_flight`, `monitor_booking` and `member_profile` as tools — the same
pipeline the CLI and FastAPI use, no logic duplicated.

Run:  python -m copilot.mcp_server      (stdio transport)
Requires the optional `mcp` extra:  uv pip install -e ".[mcp]"
"""

from __future__ import annotations

import json

from copilot.pipeline import run_concierge
from copilot.pipeline.live import live_flight_status
from copilot.pipeline.monitor import monitor_booking


def build_server():
    """Construct the FastMCP server. Imported lazily so the package works without mcp."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("ascend-concierge")

    @mcp.tool()
    async def quote_trip(request: str, member_handle: str | None = None) -> str:
        """Quote a trip from a free-text traveler request. Optionally personalize
        with a member handle (customer intelligence). Returns JSON."""
        result = await run_concierge(request, member_handle=member_handle)
        rec = result.recommendation
        return json.dumps(
            {
                "brief": result.brief.model_dump(mode="json"),
                "recommended": rec.recommended_index,
                "whatsapp_message": rec.whatsapp_message,
                "options": [
                    {
                        "carrier": o.flight.carrier, "flight_no": o.flight.flight_no,
                        "cash_usd": o.flight.cash_price_usd, "points_savings_pct": o.flight.savings_pct,
                        "risk": o.risk.score, "risk_band": o.risk.band,
                    }
                    for o in rec.options
                ],
                "trace": result.trace,
            },
            default=str,
        )

    @mcp.tool()
    async def watch_flight(flight_no: str, date: str | None = None) -> str:
        """Live status of a booked flight, including inbound-aircraft delay. JSON."""
        status = await live_flight_status(flight_no, date)
        return status.model_dump_json()

    @mcp.tool()
    async def monitor_flight(flight_no: str, destination: str, date: str | None = None) -> str:
        """Post-purchase proactive check: should we alert the member? JSON alert."""
        alert = await monitor_booking(flight_no, destination, date)
        return alert.model_dump_json()

    @mcp.tool()
    def member_profile(handle: str) -> str:
        """Look up a member's learned profile (customer intelligence). JSON or null."""
        from copilot.memory import default_store

        profile = default_store().get(handle)
        return profile.model_dump_json() if profile else "null"

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
