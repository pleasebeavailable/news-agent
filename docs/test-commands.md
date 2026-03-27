# NemoClaw — Verification & Test Commands

## 1. Bot management

```bash
# Connect to sandbox
nemoclaw <your-sandbox> connect

# Start bot (survives SSH disconnect)
start

# Watch live logs
tail -f /tmp/nemoclaw.log

# Stop bot
kill $(cat /tmp/nemoclaw.lock)

# Restart bot
start
```

---

## 2. Verify bot is running

```bash
# Check process
ps aux | grep main.py

# Check lock file
cat /tmp/nemoclaw.lock

# Last 50 log lines
tail -50 /tmp/nemoclaw.log
```

Expected in logs on startup:
```
INFO __main__ — Lock acquired (PID=XXXXX)
INFO __main__ — NemoClaw Phase 2 starting up
INFO __main__ — News polling every 15 min
INFO __main__ — Scheduler started
INFO __main__ — Telegram poll loop started
```

Expected heartbeat every 60s:
```
INFO __main__ — heartbeat — uptime Xm, next job in Xm
```

---

## 3. Telegram command tests

Send each command in Telegram and verify the response:

| Command | Expected |
|---|---|
| `status` | "NemoClaw Phase 2 running. All systems go." |
| `watchlist` | Prices grouped by theme (AI Infra, Crypto, etc.) |
| `portfolio` | P&L per position + total |
| `NVDA` | Single ticker quote |
| `NVDA vs AMD` | Side-by-side comparison |
| `news` | Scored headlines from DB |
| `alerts` | High-score news only |
| `geo` | Geopolitical brief |
| `earnings` | Upcoming earnings calendar |
| `Research NVDA` | Bull/bear analysis with dated headlines |
| `reload` | "Config reloaded." |

---

## 4. Logging verification

After sending `watchlist`:
```
INFO __main__ — routing: watchlist
INFO skills.skill_stock_price — price request — watchlist
INFO core.stock_data — fetching quote NVDA
INFO core.stock_data — quote NVDA — $XXX.XX (+X.XX%)
... (one line per ticker)
INFO core.llm_client — LLM call — ...   (NOT expected for watchlist — no LLM)
```

After sending `Research NVDA`:
```
INFO __main__ — routing: research → NVDA
INFO core.stock_data — fetching quote NVDA
INFO skills.skill_research — research request — ticker=NVDA, news_items=N, as_of=YYYY-MM-DD
INFO core.llm_client — LLM call — 1 messages, max_tokens=1000
INFO core.llm_client — LLM response — X.Xs, NNN chars
```

Research output should include dated headlines like:
```
[2026-03-21] NVDA beats earnings — analyst raises target...
```

---

## 5. News cycle verification

```bash
# Trigger news cycle manually — check logs for feed activity
# (normally runs every 15 min automatically)
tail -f /tmp/nemoclaw.log
```

Expected after a news cycle:
```
INFO core.news_fetcher — fetched Reuters RSS — N new items
INFO core.news_fetcher — fetched CNBC Top News — N new items
...
DEBUG core.news_store — get_recent(16h, score>=5) → N articles
```

---

## 6. Deploy verification

```bash
# From Mac — deploy latest code
bash ~/openclaw-agent/deploy.sh

# On sandbox — restart
start

# Verify new code loaded
tail -20 /tmp/nemoclaw.log
```

---

## 7. Network / policy checks

```bash
# Check current active policy
openshell policy get <your-sandbox> --full

# Verify Yahoo Finance works (should return JSON)
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/NVDA?interval=1d&range=1d" | head -c 200

# Verify Telegram API reachable
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" | python3 -m json.tool
```

---

## 8. Database check

```bash
# Check news DB has recent items
python3 -c "
import sqlite3
from datetime import datetime, timedelta
conn = sqlite3.connect('/sandbox/workspace/data/news_log.db')
total = conn.execute('SELECT COUNT(*) FROM scored_news').fetchone()[0]
recent = conn.execute(
    'SELECT COUNT(*) FROM scored_news WHERE fetched_at >= ?',
    ((datetime.now() - timedelta(hours=24)).isoformat(),)
).fetchone()[0]
print(f'Total articles: {total}')
print(f'Last 24h: {recent}')
conn.close()
"
```
