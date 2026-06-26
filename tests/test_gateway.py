import pytest

from copilot.config import MODELS, Settings, Tier
from copilot.gateway import BudgetExceeded, ChatMessage, Gateway


async def test_routes_and_records_ledger():
    gw = Gateway()
    res = await gw.chat(Tier.CHEAP, [ChatMessage("system", "extract a TripBrief"),
                                     ChatMessage("user", "NYC to London")], stage="extract")
    assert res.model in MODELS
    assert gw.ledger.summary()["calls"] == 1


async def test_budget_cap_blocks_calls():
    gw = Gateway(settings=Settings(provider="mock", budget_usd=0.0))
    with pytest.raises(BudgetExceeded):
        await gw.chat(Tier.CHEAP, [ChatMessage("system", "x"), ChatMessage("user", "y")])


async def test_fallback_when_primary_provider_errors():
    """If the provider raises for every model, the router exhausts the chain."""
    class BoomProvider:
        name = "boom"
        async def complete(self, **kw):
            raise RuntimeError("rate limited")

    gw = Gateway(provider=BoomProvider())
    with pytest.raises(RuntimeError):
        await gw.chat(Tier.CHEAP, [ChatMessage("system", "x"), ChatMessage("user", "y")])


async def test_none_content_is_coerced_to_empty_string():
    """A real model once returned content=None; the gateway must not pass that on
    to callers that do .strip()/json.loads()."""
    class NoneTextProvider:
        name = "nonetext"
        async def complete(self, **kw):
            return None, 1, 1, {}

    gw = Gateway(provider=NoneTextProvider())
    res = await gw.chat(Tier.CHEAP, [ChatMessage("system", "x"), ChatMessage("user", "y")])
    assert res.text == ""


async def test_cost_accumulates():
    gw = Gateway()
    for _ in range(3):
        await gw.chat(Tier.CHEAP, [ChatMessage("system", "extract a TripBrief"),
                                   ChatMessage("user", "z")])
    assert gw.ledger.total_cost > 0
    assert gw.ledger.summary()["calls"] == 3
