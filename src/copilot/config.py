"""Configuration: model registry, task tiers, and runtime settings.

The registry is the single source of truth for *which* models exist, what they
cost, and which OpenRouter slug to call. Routing (config.py -> router.py) picks a
model per task *tier*, so swapping GLM in for the cheap tier is a one-line change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


class Tier(str, Enum):
    """Task tiers. Each pipeline stage asks for a tier, not a specific model."""

    CHEAP = "cheap"      # extraction, classification, risk-explanation
    STRONG = "strong"    # final white-glove recommendation reasoning
    JUDGE = "judge"      # eval scoring (kept distinct to avoid self-grading)


@dataclass(frozen=True)
class ModelSpec:
    """One callable model and what it costs.

    Prices are USD per 1M tokens (input/output). Numbers reflect public
    OpenRouter pricing as of mid-2026; they only drive the cost *ledger* and the
    budget guard, so being approximately right is enough.
    """

    name: str                 # our internal handle, e.g. "glm-4.6"
    slug: str                 # provider/model id, e.g. "z-ai/glm-4.6"
    input_per_1m: float
    output_per_1m: float
    context: int = 128_000

    def cost(self, in_tokens: int, out_tokens: int) -> float:
        return (in_tokens / 1e6) * self.input_per_1m + (out_tokens / 1e6) * self.output_per_1m


# ── Model registry ──────────────────────────────────────────────────────────
# Intentionally diverse: a Chinese open model (GLM), an open MoE (DeepSeek), and
# the three frontier labs — so the eval scorecard compares real apples to apples.
MODELS: dict[str, ModelSpec] = {
    "glm-4.6":        ModelSpec("glm-4.6",        "z-ai/glm-4.6",                 0.40, 1.75, 200_000),
    "glm-4.5-air":    ModelSpec("glm-4.5-air",    "z-ai/glm-4.5-air",             0.14, 0.86, 128_000),
    "deepseek-v3":    ModelSpec("deepseek-v3",    "deepseek/deepseek-chat",       0.27, 1.10, 64_000),
    "claude-haiku":   ModelSpec("claude-haiku",   "anthropic/claude-haiku-4.5",   1.00, 5.00, 200_000),
    "claude-sonnet":  ModelSpec("claude-sonnet",  "anthropic/claude-sonnet-4.6",  3.00, 15.00, 200_000),
    "gpt-4o-mini":    ModelSpec("gpt-4o-mini",    "openai/gpt-4o-mini",           0.15, 0.60, 128_000),
    "gpt-4o":         ModelSpec("gpt-4o",         "openai/gpt-4o",                2.50, 10.00, 128_000),
    "gemini-flash":   ModelSpec("gemini-flash",   "google/gemini-2.5-flash",      0.30, 2.50, 1_000_000),
    # The offline deterministic stand-in. Free. Always available.
    "mock":           ModelSpec("mock",           "mock/mock",                    0.0,  0.0,  128_000),
}

# Default model per tier. Cheap defaults to GLM-Air (fast + dirt cheap), strong
# to GLM-4.6 (your "intercalate GLM" ask), judge to a different lab for fairness.
TIER_DEFAULTS: dict[Tier, str] = {
    Tier.CHEAP: "glm-4.5-air",
    Tier.STRONG: "glm-4.6",
    Tier.JUDGE: "claude-sonnet",
}

# Fallback chains: if the primary is rate-limited / errors, try these in order.
TIER_FALLBACKS: dict[Tier, list[str]] = {
    Tier.CHEAP: ["deepseek-v3", "gpt-4o-mini", "claude-haiku"],
    Tier.STRONG: ["claude-sonnet", "gpt-4o", "gemini-flash"],
    Tier.JUDGE: ["gpt-4o", "glm-4.6"],
}


@dataclass
class Settings:
    provider: str = field(default_factory=lambda: os.getenv("COPILOT_PROVIDER", "mock"))
    openrouter_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    anthropic_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    budget_usd: float = field(default_factory=lambda: float(os.getenv("COPILOT_BUDGET_USD", "5.0")))
    trace_dir: str = field(default_factory=lambda: os.getenv("COPILOT_TRACE_DIR", "traces"))
    # Amadeus Self-Service (real flight search). Free tier uses the test host.
    amadeus_client_id: str = field(default_factory=lambda: os.getenv("AMADEUS_CLIENT_ID", ""))
    amadeus_secret: str = field(default_factory=lambda: os.getenv("AMADEUS_CLIENT_SECRET", ""))
    amadeus_host: str = field(default_factory=lambda: os.getenv("AMADEUS_HOSTNAME", "test"))

    @property
    def amadeus_enabled(self) -> bool:
        return bool(self.amadeus_client_id and self.amadeus_secret)

    @property
    def amadeus_base_url(self) -> str:
        return ("https://api.amadeus.com" if self.amadeus_host == "production"
                else "https://test.api.amadeus.com")

    def resolve_provider(self) -> str:
        """Fall back to mock if the chosen provider has no key — so a demo never
        dies on a missing secret; it degrades to deterministic offline output."""
        if self.provider == "openrouter" and not self.openrouter_key:
            return "mock"
        if self.provider == "anthropic" and not self.anthropic_key:
            return "mock"
        return self.provider


settings = Settings()
