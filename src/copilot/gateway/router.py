"""The router: pick a model by task tier, enforce a budget, fall back on failure.

This is the "manage multiple models" core. A stage says `gateway.chat(Tier.CHEAP,
...)` and the router decides *which* concrete model answers, charges the ledger,
and — if the primary errors or rate-limits — walks the fallback chain instead of
failing the whole request. That last part is the literal "hit usage limits on
Claude/Codex/Cursor" resilience the JD asks about.
"""

from __future__ import annotations

import time

from copilot.config import (
    MODELS,
    TIER_DEFAULTS,
    TIER_FALLBACKS,
    Settings,
    Tier,
    settings as global_settings,
)
from copilot.gateway.base import ChatMessage, LLMResult, Provider
from copilot.gateway.mock import MockProvider
from copilot.observability.trace import Ledger, TraceEvent


class BudgetExceeded(RuntimeError):
    """Raised when a call's projected cost would cross the configured ceiling."""


def _build_provider(settings: Settings) -> Provider:
    resolved = settings.resolve_provider()
    if resolved == "openrouter":
        from copilot.gateway.openrouter import OpenRouterProvider

        return OpenRouterProvider(settings.openrouter_key)
    if resolved == "anthropic":
        from copilot.gateway.anthropic import AnthropicProvider

        return AnthropicProvider(settings.anthropic_key)
    return MockProvider()


class Gateway:
    def __init__(self, settings: Settings | None = None, provider: Provider | None = None):
        self.settings = settings or global_settings
        self.provider = provider or _build_provider(self.settings)
        self.ledger = Ledger(trace_dir=self.settings.trace_dir)

    def _chain(self, tier: Tier, override: str | None) -> list[str]:
        primary = override or TIER_DEFAULTS[tier]
        return [primary, *TIER_FALLBACKS.get(tier, [])]

    async def chat(
        self,
        tier: Tier,
        messages: list[ChatMessage],
        *,
        stage: str = "",
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResult:
        # Budget guard up front: refuse if we're already over the ceiling.
        if self.ledger.total_cost >= self.settings.budget_usd:
            raise BudgetExceeded(
                f"Spend ${self.ledger.total_cost:.4f} reached cap ${self.settings.budget_usd:.2f}"
            )

        chain = self._chain(tier, model)
        last_err: Exception | None = None

        for i, model_name in enumerate(chain):
            spec = MODELS.get(model_name)
            if spec is None:
                continue
            slug = "mock/mock" if self.provider.name == "mock" else spec.slug
            t0 = time.perf_counter()
            try:
                text, in_tok, out_tok, raw = await self.provider.complete(
                    model_slug=slug,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
            except Exception as exc:  # noqa: BLE001 — any provider error → try fallback
                last_err = exc
                continue

            latency_ms = (time.perf_counter() - t0) * 1000
            cost = spec.cost(in_tok, out_tok)
            fell_back = chain[0] if i > 0 else None

            self.ledger.record(
                TraceEvent(
                    ts=time.time(),
                    stage=stage,
                    tier=tier.value,
                    model=model_name,
                    provider=self.provider.name,
                    in_tokens=in_tok,
                    out_tokens=out_tok,
                    cost_usd=cost,
                    latency_ms=round(latency_ms, 1),
                    fell_back_from=fell_back,
                )
            )
            return LLMResult(
                text=text,
                model=model_name,
                in_tokens=in_tok,
                out_tokens=out_tok,
                cost_usd=cost,
                latency_ms=round(latency_ms, 1),
                provider=self.provider.name,
                fell_back_from=fell_back,
                raw=raw,
            )

        raise RuntimeError(f"All models failed for tier {tier.value}: {last_err}")
