# NemoClaw — Full Project Summary

## What it is

A personal portfolio intelligence Telegram bot running on a remote sandbox. You message it like a human assistant; it routes to specialized skills or falls back to free-form chat with "Rich" — a stateful LLM persona that knows your portfolio.

**Model:** `nvidia/nemotron-3-super-120b-a12b` via local inference proxy at `inference.local/v1`

---

## Portfolio it watches

| Theme | Tickers | Weight |
|---|---|---|
| AI Infra | NVDA, NBIS, AMZN, GOOG, GLW, MRVL | 46.8% |
| Crypto | BMNR, HOOD, ORBS | 17.8% |
| China/EM | BABA, 2689.HK | 11.0% |
| Brazil | PBR, VALE | 8.4% |
| Vol/Options | FLOW.AS | 6.1% |
| Satellites | OPEN, SKYX | small |

Each position has a full thesis, kill switch condition, and stance (`core_hold`, `accumulate`, `lot_reshape`, `house_money`, `lottery`, etc.) in `config/theses.yaml`.

---

## Architecture

```
Telegram → poll_loop() → handle_message() → skill router
                                              ├── skill_stock_price
                                              ├── skill_news_monitor
                                              ├── skill_earnings
                                              ├── skill_morning_brief
                                              ├── skill_weekly_summary
                                              ├── skill_research
                                              ├── skill_geopolitical
                                              └── free-form chat (LLM, 10-msg history)

Background scheduler (30s tick):
  ├── every 15 min → run_news_cycle()   [fetch → score → store → alert]
  ├── every 30 min → run_geo_scan()     [geo alert if score ≥7]
  ├── weekdays 07:00 CET → morning_brief
  └── Saturday 07:00 CET → weekly_summary
```

---

## Core modules (`core/`)

| File | Role |
|---|---|
| `telegram_bot.py` | Send/receive Telegram messages, 409 conflict handling |
| `llm_client.py` | OpenAI-compatible client pointing to `inference.local/v1` — logs each call + response time |
| `stock_data.py` | yfinance wrapper — quotes, comparisons, earnings — logs each fetch |
| `news_fetcher.py` | RSS + research URL fetcher — logs per-feed item counts |
| `news_scorer.py` | LLM batch scorer — assigns score/category/tickers/impact |
| `news_store.py` | SQLite store (`data/news_log.db`) — save, dedup, query — UTC bug fixed (uses local time) |
| `config_loader.py` | YAML config loader with hot-reload (`reload` command) |

---

## Skills (`skills/`)

| Skill | Telegram trigger | What it does |
|---|---|---|
| `skill_stock_price` | `watchlist`, `portfolio`, `NVDA`, `NVDA vs AMD` | Live prices, P&L, theme grouping, comparisons |
| `skill_news_monitor` | `news`, `news AI`, `alerts`, `kills`, any news on X | Serves scored headlines from DB; sends immediate alerts score ≥7 |
| `skill_earnings` | `earnings`, `calendar` | Upcoming earnings for portfolio tickers |
| `skill_morning_brief` | auto weekdays 07:00 | LLM brief: overnight news + portfolio movers. News items date-stamped for LLM |
| `skill_weekly_summary` | auto Saturday 07:00 | Weekly performance + macro themes. Covers true Mon–Sun window |
| `skill_research` | `Research PLTR`, `Deep dive NVDA`, `What's happening with X?` | Bull/bear LLM analysis using thesis + recent news. All news date-stamped |
| `skill_geopolitical` | `geo` (on-demand) + auto every 30 min | Geo brief from scored news; immediate alert for score ≥7 geo items. Date-stamped |

---

## News pipeline

**Sources — `config/news_sources.yaml`**

*RSS feeds (16 total, 15 working):*
- Tier 1 free: Reuters, CNBC ×2, MarketWatch ×2, Yahoo Finance, AP, BBC, Al Jazeera, Reuters World
- Tier 1 paid: Seeking Alpha (RSS still works)
- Tier 2: Investing.com, ZeroHedge
- Tier 3 paywalled headlines: FT, Bloomberg
- Geo: Al Jazeera, Reuters World
- Broken: CFR (malformed XML — known issue, skipped silently)

*X/Twitter accounts (28 handles, not yet wired to live feed — config ready)*

*Research URLs (6 free, auto-fetched; 5 reference-only):*

| Source | Method | Status |
|---|---|---|
| Hoisington (Lacy Hunt) | PDF scrape | ✓ 16 PDFs |
| G&R Quarterly Commentary | PDF scrape | ✓ 3 PDFs |
| Art Berman Blog | RSS `/feed` | ✓ 12 entries |
| Geopolitical Futures | RSS `/feed` | ✓ 5 entries |
| G&R Blog | RSS probe | — no RSS found |
| Geopolitical Alpha | RSS probe | — no RSS found |

**Scoring — `config/keywords.yaml`**

Alert threshold: score ≥7 → immediate Telegram push. Score ≥5 → stored for briefs.

---

## Logging

All modules have structured logging to `/tmp/nemoclaw.log`:

- `main.py` — startup, lock acquired, message routing (every command logged)
- `core/llm_client.py` — every LLM call: message count, response time, char count
- `core/stock_data.py` — every yfinance fetch: ticker, price, change %
- `core/news_fetcher.py` — per-feed new item counts; probe failures at DEBUG
- `core/news_store.py` — DB saves (DEBUG), query results (DEBUG), errors (ERROR)
- `skills/` — all skills log their request type and key params
- Heartbeat every 60s: uptime + time until next scheduled job

---

## Date relevance

- **UTC bug fixed**: `news_store.get_recent()` now uses `datetime.now()` (local time) matching SQLite's `CURRENT_TIMESTAMP`
- **LLM prompts date-stamped**: All news fed to LLM includes `[YYYY-MM-DD]` prefix on each headline — LLM knows article age
- **Weekly summary**: Uses true Mon 00:00 → now window instead of rolling 144h

---

## Infrastructure

- **Deploy:** `bash ~/openclaw-agent/deploy.sh` from Mac
- **Start:** `start` on sandbox — uses `nohup`, survives SSH disconnects
- **Logs:** `/tmp/nemoclaw.log` — `tail -f /tmp/nemoclaw.log`
- **Stop:** `kill $(cat /tmp/nemoclaw.lock)`
- **Single-instance lock:** `/tmp/nemoclaw.lock` with PID
- **`.env` persistence:** `/sandbox/.openclaw-data/.env` → symlinked to workspace
- **Proxy note:** `inference.local` resolves through the proxy — NOT in `no_proxy`
- **tmux/screen:** not available on sandbox (no root) — nohup used instead
- **Quick reference:** printed on every `nemoclaw <your-sandbox> connect` via `~/.bashrc`

---

## What's not yet implemented

- **X/Twitter live feed** — handles defined in config, no fetcher yet (needs RSS Bridge or API)
- **G&R Blog + Geopolitical Alpha** — no RSS found; would need HTML scraping
