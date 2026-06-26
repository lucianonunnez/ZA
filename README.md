# Ascend Concierge Copilot

> A working slice of an AI-native travel concierge: it turns a messy WhatsApp-style
> traveler request into a quoted, **disruption-risk-scored**, points-optimized,
> paste-ready recommendation — over a **multi-model gateway** that routes by task,
> tracks cost/latency per call, falls back when a model rate-limits, and is
> benchmarked with **evals**.

Built as an interview demo, but built like production: typed contracts at every
stage, verification over vibes, and honest degradation when a key or a network
isn't there (it runs **fully offline** with a deterministic mock provider).

```bash
uv venv && uv pip install -e ".[dev]"
copilot quote "I need NYC to London next Thursday, business, morning arrival, flexible budget"
copilot watch   AA100              # live status + inbound-aircraft tracking
copilot monitor AA100 --to LHR     # post-purchase proactive alert (the Ascend loop)
copilot models                     # registry + active provider
python evals/run_evals.py          # multi-model scorecard
pytest -q                          # 18 tests, all offline
```

---

## Why this design (and what it signals)

| Capability | Where it lives | What it shows |
|---|---|---|
| **Manage multiple models** | `gateway/router.py` | Routes by *task tier* (cheap/strong/judge), not by hardcoding a model. Swap GLM in for the cheap tier in one line. |
| **Resilience** | `router.py` fallback chains | If the primary model errors or rate-limits, the router walks a fallback chain instead of failing the request. ("hit usage limits on Claude/Codex/Cursor") |
| **Cost discipline** | `observability/trace.py` + budget cap | Every call is charged to a ledger; a configurable `COPILOT_BUDGET_USD` hard-stops spend. |
| **Evidence over vibes** | `evals/` | A scorecard benchmarks models on field-accuracy, an LLM-judge score, cost and latency. Standards you can hand to a team. |
| **Proactive disruption mgmt** | `pipeline/risk.py` + `live.py` + `monitor.py` | At quote time, an *evidence-weighted* risk index; after booking, a **live ADS-B watch** on the inbound aircraft that proactively alerts the member (see below). |
| **Points/miles arbitrage** | `pipeline/flights.py` | Surfaces cash-vs-points value and ranks by savings. |
| **Data-handling judgment** | `guardrails/pii.py` | PII is redacted before any text reaches a model or a log. |
| **Provider-agnostic** | `gateway/*.py` | OpenRouter (one key → GLM, DeepSeek, Claude, GPT, Gemini), native Anthropic, or offline mock. |

## The pipeline

```
"NYC to London thursday, business, morning arrival"
        │
        ▼  extract  (cheap model, JSON-validated → TripBrief; PII redacted first)
        ▼  flights  (inventory + points arbitrage; live API/scraper drops in here)
        ▼  risk     (deterministic feature score + cheap model writes the explanation)  ← fans out concurrently
        ▼  recommend(strong model → ranked pick + paste-ready WhatsApp message)
        ▼
   brief + recommendation + full cost/latency trace
```

## The disruption-risk model is grounded in data, not vibes

The first draft weighted **weather at 45%**. The data says that's wrong, so it was
fixed. Validated drivers, in order of real impact:

1. **Late-arriving aircraft / reactionary delay — the #1 cause.** US DOT/BTS: ~3.9%
   of flights vs ~0.16% from extreme weather. EUROCONTROL: ~8.2 min/flight, the
   largest single category. At quote time we can't see the prior rotation, so
   **departure time of day** is the proxy: delays compound through the day
   (>80% on-time before 8am vs 53% after 10pm; pre-11am flights ~10× less likely
   to cancel).
2. **Airline reliability** (carrier-controlled: maintenance, crew, baggage).
3. **Weather** — small on *average*, but owns the catastrophic tail.
4. **Connections** — each one compounds reactionary risk.
5. **Airport congestion** (NAS / ATC capacity).

Current weights: `time_of_day 0.35 · airline 0.22 · weather 0.20 · connections 0.13
· congestion 0.10` (see `pipeline/risk.py`).

**Deliberately *not* a cancellation probability.** Models that hit 90%+ accuracy use
rich historical features unavailable at quote time. This is a transparent,
explainable risk *index* with the most actionable lever — "take the earlier
flight" — on top. Honesty over false precision.

Sources: [US DOT/BTS — causes of delay](https://www.bts.gov/topics/airlines-and-airports/understanding-reporting-causes-flight-delays-and-cancellations) ·
[EUROCONTROL — all-causes delay 2023](https://www.eurocontrol.int/publication/all-causes-delays-air-transport-europe-annual-2023) ·
[DOT data analysis — first flight of the day](https://thriftytraveler.com/guides/flights/data-analysis-first-flight-of-the-day/) ·
[Flight delay prediction (arXiv)](https://arxiv.org/pdf/2409.00607)

## The post-purchase loop: from a risk *index* to a live *signal*

The risk index above is a **proxy** used when quoting (we can't yet see which
physical aircraft will fly). Once a member books a specific flight, the same
system upgrades to a **live signal** — and this is where the #1 driver
(late-arriving aircraft) is observed directly, for free:

```
booked flight (number + date)
        │
        ▼  live status   (AeroDataBox / AviationStack: status, times, AIRCRAFT REG)
        ▼  inbound watch (OpenSky ADS-B, free: is the feeder leg already late?)
        ▼  + weather at destination
        ▼
   ProactiveAlert: level (clear|watch|warning|critical), on-time confidence,
                   recommended action, and a paste-ready concierge message
```

`copilot monitor AA100 --to LHR` → if the inbound aircraft is running an hour
late, it raises a **CRITICAL** alert and drafts: *"Heads-up — I'm watching your
flight and the inbound aircraft is running about an hour behind… I'm already
holding an earlier alternative."* That is Ascend's "proactive handling of
disruptions," automated.

**Why this is mostly free:** [OpenSky](https://opensky-network.org/data/api) gives
live ADS-B positions (4k credits/day, free) so you can watch the feeder leg; a
cheap schedule source ([AeroDataBox](https://aerodatabox.com/flight-api-2024/) from
~$0.99/mo, or [AviationStack](https://aviationstack.com/) free 500/mo) resolves
`flight number → aircraft registration`. Honest caveat: ADS-B only sees what's
flying now, so the schedule source is what links a future flight number to its
tail. Offline, `live.py` returns a deterministic demo.

## Configuration

Copy `.env.example` → `.env`. Runs with **zero keys** on the mock provider. Add an
OpenRouter key and set `COPILOT_PROVIDER=openrouter` to route to real models
(GLM, DeepSeek, Claude, GPT, Gemini) — a single key, ~$30 covers heavy eval runs.

| Var | Purpose |
|---|---|
| `COPILOT_PROVIDER` | `mock` (default, offline) · `openrouter` · `anthropic` |
| `OPENROUTER_API_KEY` | one key, many labs |
| `COPILOT_BUDGET_USD` | hard ceiling on spend per process |
| `AERODATABOX_API_KEY` | optional — live flight status + aircraft reg for `monitor`/`watch` |

## Layout

```
src/copilot/
  config.py            model registry, tiers, settings, budget
  schemas.py           Pydantic contracts (TripBrief, FlightOption, RiskAssessment, Recommendation)
  gateway/             router + provider adapters (openrouter, anthropic, mock)
  pipeline/            extract · flights · weather · risk · recommend · live · monitor · orchestrator
  guardrails/          PII redaction
  observability/       cost/latency ledger
  cli.py  api.py       demo entrypoints (Typer CLI: quote/watch/monitor/models + FastAPI)
evals/                 dataset + LLM-judge + multi-model scorecard
tests/                 18 tests, all offline
```

## What's mocked vs real (honest scope)

- **Real:** the gateway, routing, fallback, budget guard, cost ledger, the
  evidence-weighted risk model, points arbitrage math, PII redaction, evals harness,
  CLI/API, the full async pipeline.
- **Real (logic) behind a network seam:** the proactive `monitor`/`watch` loop —
  alert levels, live-override scoring, the concierge message — is real; the
  AeroDataBox + OpenSky adapters in `live.py` activate with a key/network and fall
  back to a deterministic demo offline.
- **Stubbed behind a clean seam:** live flight inventory (offline dataset; drop in
  Amadeus/Kiwi or a Playwright scraper in `flights.py`) and live weather
  (Open-Meteo adapter present in `weather.py`, falls back to a heuristic offline).
- **Why:** the demo must run anywhere with zero secrets. The seams are where
  production integrations plug in without touching the rest.
