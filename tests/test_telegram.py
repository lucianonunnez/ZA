"""Telegram reply formatting (pure, offline — no bot token / network needed)."""

from copilot.pipeline import run_concierge
from copilot.telegram_bot import format_reply, is_risk_question


async def test_format_reply_renders_options_and_message():
    result = await run_concierge("NYC to London thursday business morning arrival")
    text = format_reply(result)
    assert "JFK → LHR" in text
    assert "<b>" in text                     # HTML formatting for Telegram
    assert "risk" in text
    assert "⭐" in text                       # the recommended pick is starred
    assert "models" in text                  # trace footer present
    assert "why" in text.lower()             # invites the risk explanation


def test_risk_question_detection():
    assert is_risk_question("why")
    assert is_risk_question("why?")
    assert is_risk_question("how do you score the risk?")
    assert is_risk_question("explain the risk")
    assert not is_risk_question("NYC to London business")


async def test_format_reply_handles_empty_route():
    result = await run_concierge("hi there")  # no inventory -> graceful message
    text = format_reply(result)
    assert isinstance(text, str) and len(text) > 0
