"""Provider-agnostic types. Every adapter speaks this language."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResult:
    """Everything we learned from one model call — content plus the receipts."""

    text: str
    model: str
    in_tokens: int
    out_tokens: int
    cost_usd: float
    latency_ms: float
    provider: str
    # Set when the primary model failed and a fallback answered instead.
    fell_back_from: str | None = None
    raw: dict = field(default_factory=dict)


class Provider(Protocol):
    """Minimal surface an adapter must implement."""

    name: str

    async def complete(
        self,
        *,
        model_slug: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> tuple[str, int, int, dict]:
        """Return (text, input_tokens, output_tokens, raw_response)."""
        ...
