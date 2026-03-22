# NemoClaw — Portfolio Intelligence Bot

Telegram bot running inside an OpenShell sandbox (`rich-biatch`) on Nemotron-3-super-120b-a12b.
Monitors news, prices, earnings, and runs on-demand research for a personal portfolio.

---

## Daily use

The bot runs persistently via `nohup` — **SSH disconnects do not stop it**.

```bash
nemoclaw rich-biatch connect     # reconnect to sandbox
tail -f /tmp/nemoclaw.log        # watch live logs
start                            # (re)start bot
kill $(cat /tmp/nemoclaw.lock)   # stop bot
```

The quick reference above prints automatically on every `nemoclaw rich-biatch connect`.

---

## Deploy & first-time setup

### 1. Deploy files from Mac

```bash
bash ~/openclaw-agent/deploy.sh
```

Pushes all code + config + start script to `/sandbox/workspace/` and `/sandbox/bin/start`.

### 2. Install Python dependencies (once per sandbox)

```bash
pip install -q --break-system-packages yfinance feedparser pyyaml schedule requests aiohttp
```

### 3. Start the bot

```bash
start
```

`.env` is stored at `/sandbox/.openclaw-data/.env` (persistent) and symlinked to `/sandbox/workspace/.env`.
Created automatically by `deploy.sh` — survives reconnects.

---

## Bot commands

| Command | What it does |
|---|---|
| `watchlist` | Live prices for all positions, grouped by theme |
| `portfolio` | Portfolio with P&L per position |
| `NVDA` | Quote for any single ticker |
| `NVDA vs AMD` | Side-by-side comparison |
| `news` | Latest scored headlines from DB |
| `news AI` | Headlines filtered by topic |
| `Any news on NVDA?` | News for a specific ticker |
| `alerts` | High-score alerts only (≥7) |
| `kills` | Kill switch status for all positions |
| `geo` | On-demand geopolitical brief |
| `earnings` | Upcoming earnings (next 30 days) |
| `calendar` | Earnings next 7 days |
| `Research PLTR` | Bull/bear LLM analysis |
| `Deep dive NVDA` | Full deep analysis |
| `What's happening with China?` | Topic context from news DB |
| `status` | Bot health check |
| `reload` | Reload config without restarting |

---

## Architecture

```
Telegram → poll_loop() → handle_message() → skill router
                                             ├── skill_stock_price    (yfinance)
                                             ├── skill_news_monitor   (SQLite news DB)
                                             ├── skill_earnings       (yfinance)
                                             ├── skill_morning_brief  (LLM)
                                             ├── skill_weekly_summary (LLM)
                                             ├── skill_research       (LLM)
                                             ├── skill_geopolitical   (LLM)
                                             └── free-form chat       (LLM, 10-msg history)

Background scheduler (30s tick):
  ├── every 15 min → run_news_cycle()   [fetch → score → store → alert]
  ├── every 30 min → run_geo_scan()     [geo alert if score ≥7]
  ├── weekdays 07:00 → morning_brief
  └── Saturday 07:00 → weekly_summary
```

| Component | Value |
|---|---|
| Sandbox | rich-biatch |
| Workspace | /sandbox/workspace/ |
| Model | nvidia/nemotron-3-super-120b-a12b |
| Inference URL | https://inference.local/v1 |
| Interface | Telegram |
| Log file | /tmp/nemoclaw.log |
| News DB | /sandbox/workspace/data/news_log.db |

---

## Logging

All modules emit structured logs to `/tmp/nemoclaw.log`:

- Startup: lock acquired, scheduler setup
- Every message: routed to which skill
- LLM calls: message count, response time
- Stock fetches: ticker, price, change
- News cycle: per-feed item counts
- DB: query results (DEBUG), save errors (ERROR)
- Heartbeat: every 60s — uptime + time until next scheduled job

---

## Sandbox network policy

Proxy: `10.200.0.1:3128` — blocks all traffic by default.
Policy file: `~/.nemoclaw/source/nemoclaw-blueprint/policies/openclaw-sandbox.yaml`

| Block | Hosts | Why |
|---|---|---|
| `pypi` | pypi.org, files.pythonhosted.org | pip install |
| `yahoo_finance` | query1/query2/finance.yahoo.com, fc.yahoo.com | yfinance + crumb auth |
| `telegram` | api.telegram.org | bot send/receive |

`inference.local` routes through the proxy (internal DNS) — must **not** be in `no_proxy`.

To push policy:
```bash
openshell policy set --policy <file.yaml> rich-biatch --wait
```

**Critical:** policy binaries must use `/usr/bin/python3.11` (not `/usr/bin/python3` symlink).

---

## Troubleshooting

**Bot not responding**
```bash
tail -f /tmp/nemoclaw.log    # check if it's running
start                        # restart if needed
```

**pip install 403**
- Check pypi policy: `openshell policy get rich-biatch --full | grep pypi`
- Binary must be `/usr/bin/python3.11` in policy

**yfinance errors**
- `fc.yahoo.com` must be in the yahoo_finance policy block

**LLM calls fail**
- `inference.local` must go through the proxy — do NOT add to `no_proxy`

**`.env` missing**
```bash
bash ~/openclaw-agent/deploy.sh    # recreates and symlinks .env
```
