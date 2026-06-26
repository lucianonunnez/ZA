# Concierge Copilot

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
copilot member vip1 --learn JFK,LHR,BA,business   # teach the member CRM
copilot quote "two of us to London thursday" --member vip1   # 2nd quote uses memory
copilot watch   AA100              # live status + inbound-aircraft tracking
copilot monitor AA100 --to LHR     # post-purchase proactive alert (the proactive loop)
copilot models                     # registry + active provider
python evals/run_evals.py          # multi-model scorecard
pytest -q                          # 25 tests, all offline
```

## Run it in the cloud (no local install)

Built to run **without touching your machine** — handy under corporate restrictions.
GitHub's runners have open internet, so even real models work, with the key kept
as a repo Secret (never in code or chat).

1. **Add the key once (optional, for real models):** repo → Settings → Secrets and
   variables → Actions → New repository secret → `OPENROUTER_API_KEY`.
2. **Demo a quote:** Actions → **Demo — concierge quote** → *Run workflow* → type a
   request (pick `openrouter` if you added the key). The recommendation renders in
   the run summary.
3. **Run the arena:** Actions → **Eval arena — model scorecard** → *Run workflow*.
   The multi-model leaderboard renders in the run summary (and runs weekly).
4. **Interactive shell, in the browser:** Code → **Codespaces** → *Create* — a full
   environment (devcontainer) where `copilot quote/watch/monitor` just work. Run
   `uvicorn copilot.api:app --host 0.0.0.0 --port 8000` and open the forwarded port
   to use the **web UI** (a form → live recommendation) in your browser.
5. **Public URL (optional):** Render → New → Blueprint → this repo (`render.yaml`).
   Sets up `uvicorn copilot.api:app`; add `OPENROUTER_API_KEY` in the dashboard.

Locally it's the same commands (`uvicorn copilot.api:app` → http://localhost:8000);
nothing is cloud-only.

## Telegram bot — the concierge on a real chat channel

The concierge model is chat-first (Ascend uses WhatsApp). The same pipeline is
exposed on Telegram, so you can message it from your phone and get a quote with
real disruption risk back. Each Telegram user is treated as a member, so the
customer-intelligence layer personalizes their next quote.

```bash
# 1. Create a bot with @BotFather on Telegram → copy the token
export TELEGRAM_BOT_TOKEN=...
export COPILOT_FLIGHT_SOURCE=opensky   # real flights for any route
python -m copilot.telegram_bot         # long-polling, no public URL needed
# 2. Message your bot: "NYC to London next Thursday, business, morning arrival"
```

Dependency-light (raw Bot API over httpx long-polling) and reuses the exact
pipeline — nothing duplicated.

## Stack (every choice maps to a need, nothing for its own sake)

**Polyglot by plane** — the senior decision that ties it together:
- **FastAPI** — the low-latency *quoting hot path* (`api.py`), async.
- **Django** — the *control plane*: member CRM + customer intelligence, with the
  ORM, migrations and an admin panel the concierge team actually uses (`crm/`).
  Postgres in prod (SQLite by default), so it runs anywhere.
- **MCP server** (`mcp_server.py`) — exposes the tools so an agent calls the same
  pipeline the CLI and API use. **Playwright** scraper (`pipeline/scraper.py`) is
  the no-API flight source. **Docker** + **GitHub Actions** (ruff · pytest ·
  pip-audit · gitleaks) + **Dependabot** are the CI/security gates.

> **Deliberately *not* included** (the most senior signal): no queue/Kafka/
> microservices. There's no async-heavy workload to justify them yet; adding them
> would be complexity without a problem. Knowing when *not* to add tech matters.

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
| **Customer intelligence** | `memory/` + `crm/` | Learns each member's preferences so the next quote beats the first; swappable JSON ↔ Django/Postgres store. |
| **AI-native interface (MCP)** | `mcp_server.py` | Agents call `quote_trip`/`watch_flight`/`monitor_flight`/`member_profile` as tools. |
| **Scraping / browser automation** | `pipeline/scraper.py` | Playwright flight source behind the inventory seam (the JD bonus). |
| **CI / security gates** | `.github/`, `Dockerfile` | ruff + pytest + pip-audit + gitleaks + Dependabot; containerized, non-root. |

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
holding an earlier alternative."* That is the "proactive handling of
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
| `COPILOT_FLIGHT_SOURCE` | `opensky` for real flights on any route (free, no key) · `scrape` for the Playwright source · unset = bundled inventory |
| `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET` | optional — real fares via Amadeus (note: Amadeus' free self-service portal is being decommissioned mid-2026); takes priority over OpenSky when set |

## Layout

```
src/copilot/
  config.py            model registry, tiers, settings, budget
  schemas.py           Pydantic contracts (TripBrief, FlightOption, RiskAssessment, FlightStatus, ...)
  gateway/             router + provider adapters (openrouter, anthropic, mock)
  pipeline/            extract · flights · scraper · weather · risk · recommend · live · monitor · orchestrator
  memory/              MemoryStore protocol + JSON store + shared learning logic
  guardrails/          PII redaction
  observability/       cost/latency ledger
  mcp_server.py        MCP server exposing the tools to agents
  cli.py  api.py       Typer CLI (quote/watch/monitor/member/models) + FastAPI
crm/                   Django control plane: members app (models, admin, migrations, DjangoMemoryStore)
evals/                 dataset + LLM-judge + multi-model scorecard
.github/ Dockerfile    CI (ruff/pytest/pip-audit/gitleaks), Dependabot, container
tests/                 25 tests, all offline
```

## What's mocked vs real (honest scope)

- **Real:** the gateway, routing, fallback, budget guard, cost ledger, the
  evidence-weighted risk model, points arbitrage math, PII redaction, evals harness,
  CLI/API, the full async pipeline.
- **Real (logic) behind a network seam:** the proactive `monitor`/`watch` loop —
  alert levels, live-override scoring, the concierge message — is real; the
  AeroDataBox + OpenSky adapters in `live.py` activate with a key/network and fall
  back to a deterministic demo offline.
- **Real flights for any route, no key:** `pipeline/opensky_source.py` reconstructs
  real flights from OpenSky ADS-B data (`COPILOT_FLIGHT_SOURCE=opensky`). Carriers,
  routings and times are real; price is a distance-based estimate (labeled "est.",
  no fabricated award pricing). Optional `pipeline/amadeus.py` adds real fares when
  `AMADEUS_*` is set. Live weather via Open-Meteo for ~55 bundled airports. Every
  source falls back gracefully (→ bundled inventory / heuristic), so it runs anywhere.
- **Why:** the demo must run anywhere with zero secrets. The seams are where
  production integrations plug in without touching the rest.
