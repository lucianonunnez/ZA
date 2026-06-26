"""MCP server smoke test (skipped if the optional `mcp` extra isn't installed)."""

import pytest

pytest.importorskip("mcp")


async def test_mcp_exposes_concierge_tools():
    from copilot.mcp_server import build_server

    server = build_server()
    names = {t.name for t in await server.list_tools()}
    assert {"quote_trip", "watch_flight", "monitor_flight", "member_profile"} <= names
