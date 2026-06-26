"""Offline deterministic provider.

Lets the entire app — and the test suite and a live demo — run with zero keys
and zero network. It pattern-matches the task from the system prompt and returns
plausible structured output. Deterministic so evals are reproducible.
"""

from __future__ import annotations

import hashlib
import json

from copilot.gateway.base import ChatMessage


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


class MockProvider:
    name = "mock"

    async def complete(
        self,
        *,
        model_slug: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> tuple[str, int, int, dict]:
        system = next((m.content for m in messages if m.role == "system"), "")
        user = next((m.content for m in messages if m.role == "user"), "")

        s = system.lower()
        # Match on a UNIQUE anchor phrase per stage (each stage's real system
        # prompt contains exactly one of these), so overlapping vocabulary like
        # "risk"/"recommend" across prompts can't misroute the mock.
        if "evaluator" in s:               # judge.py _JUDGE_SYSTEM
            text = self._mock_judge(user)
        elif "tripbrief" in s:             # extract.py _SYSTEM
            text = self._mock_extract(user)
        elif "assess travel disruption" in s:  # risk.py system
            text = self._mock_risk(user)
        elif "proactive premium travel concierge" in s:  # monitor.py system
            text = self._mock_monitor(user)
        elif "vip member" in s:            # recommend.py _SYSTEM
            text = self._mock_recommend(user)
        else:
            text = "OK."

        in_tokens = max(1, len(system + user) // 4)
        out_tokens = max(1, len(text) // 4)
        return text, in_tokens, out_tokens, {"mock": True, "model": model_slug}

    # ── canned generators ────────────────────────────────────────────────────
    def _mock_extract(self, user: str) -> str:
        u = user.lower()
        origin = "JFK" if any(c in u for c in ("nyc", "new york", "jfk")) else "EZE"
        dest = "LHR" if any(c in u for c in ("london", "lhr", "londres")) else "MIA"
        cabin = "business" if "business" in u else ("first" if "first" in u else "economy")
        return json.dumps(
            {
                "origin": origin,
                "destination": dest,
                "depart_date": None,
                "return_date": None,
                "cabin": cabin,
                "passengers": 1,
                "preferences": ["morning arrival"] if "morning" in u or "mañana" in u else [],
                "budget_flexible": "flexible" in u,
                "notes": "",
                "missing_or_assumed": ["exact dates not specified — confirm with member"],
            }
        )

    def _mock_risk(self, user: str) -> str:
        return (
            "Conditions look largely favorable. Light crosswinds are forecast at the "
            "arrival airport and this carrier has a strong on-time record on the route, "
            "so disruption risk is low. I'd still hold a flexible fare given the season."
        )

    def _mock_recommend(self, user: str) -> str:
        return json.dumps(
            {
                "headline": "British Airways Club World — best balance of value and reliability",
                "rationale": (
                    "It pairs the strongest points value (~37% under cash via Avios) with a "
                    "civilized morning arrival, and BA's on-time record on this route is solid. "
                    "The risk is only elevated because it's an evening departure."
                ),
                "whatsapp_message": (
                    "Hi! For Thursday I'd go with British Airways BA178 in Club World — a "
                    "comfortable overnight that lands you in London mid-morning. Booking through "
                    "Avios brings the effective cost down meaningfully versus cash. Only flag: it's "
                    "an evening departure, so I'd hold a flexible fare. Want me to lock it in?"
                ),
                "caveats": ["evening departure carries higher reactionary-delay risk"],
            }
        )

    def _mock_monitor(self, user: str) -> str:
        late = "delay" in user.lower() and "0 min" not in user.lower()
        if late:
            return (
                "Heads-up — I'm watching your flight and the inbound aircraft is running about "
                "an hour behind, so a delay is likely. I'm already holding an earlier alternative "
                "and will arrange a transport buffer on arrival. Want me to move you? I've got it covered."
            )
        return (
            "Quick note — I'm keeping an eye on your flight. Conditions are a little unsettled at "
            "your destination, so I've pre-staged a backup just in case. Nothing for you to do; I'll "
            "reach out the moment anything changes."
        )

    def _mock_judge(self, user: str) -> str:
        s = _seed(user) % 3
        score = [7, 8, 9][s]
        return json.dumps(
            {
                "score": score,
                "reasoning": "Extraction captured route and cabin; minor omission on dates.",
            }
        )
