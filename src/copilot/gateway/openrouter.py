"""OpenRouter adapter — one key, many labs (GLM, DeepSeek, Claude, GPT, Gemini).

This is the recommended path: it keeps a single secret and lets the router treat
every model uniformly. Only used when OPENROUTER_API_KEY is set; otherwise the
gateway transparently falls back to the mock provider.
"""

from __future__ import annotations

import httpx

from copilot.gateway.base import ChatMessage

_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider:
    name = "openrouter"

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
        payload: dict = {
            "model": model_slug,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._key}",
            "HTTP-Referer": "https://github.com/lucianonunnez/ZA",
            "X-Title": "Concierge Copilot",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Some models return content=null on short/empty completions — coerce to "".
        text = data["choices"][0]["message"].get("content") or ""
        usage = data.get("usage", {})
        in_tokens = usage.get("prompt_tokens", 0)
        out_tokens = usage.get("completion_tokens", 0)
        return text, in_tokens, out_tokens, data
