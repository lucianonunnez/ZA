"""Native Anthropic adapter (optional alternative to going through OpenRouter)."""

from __future__ import annotations

import httpx

from copilot.gateway.base import ChatMessage

_ENDPOINT = "https://api.anthropic.com/v1/messages"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, timeout: float = 60.0):
        self._key = api_key
        self._timeout = timeout

    async def complete(
        self,
        *,
        model_slug: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> tuple[str, int, int, dict]:
        # Anthropic wants system separate from the turn list.
        system = " ".join(m.content for m in messages if m.role == "system")
        turns = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        # Strip the "anthropic/" prefix if a slug came in OpenRouter form.
        model = model_slug.split("/", 1)[-1] if "/" in model_slug else model_slug

        payload = {
            "model": model,
            "system": system,
            "messages": turns,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "x-api-key": self._key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = "".join(block.get("text", "") for block in data.get("content", []))
        usage = data.get("usage", {})
        return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0), data
