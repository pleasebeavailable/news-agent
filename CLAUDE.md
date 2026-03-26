# CLAUDE.md — NemoClaw

Personal portfolio intelligence Telegram bot. Python 3, SQLite, RSS feeds, yfinance, LLM-scored news.

## Quick reference

```bash
# Compile check
python -m py_compile main.py core/*.py skills/*.py

# Tests
pytest tests/test_fixes.py -v

# Deploy to sandbox (idempotent)
bash bin/deploy.sh

# Start bot on sandbox
start

# Logs (on sandbox)
log              # all logs
log news         # news pipeline only
log -f llm       # follow LLM calls
log -f geo 50    # last 50 geo lines + follow
# Categories: app, news, llm, geo, all (default)
```

## Project layout

- `main.py` — entry point: Telegram poll loop + scheduler + skill router
- `core/` — telegram_bot, llm_client, stock_data, news_fetcher, news_scorer, news_store, config_loader
- `skills/` — stock_price, news_monitor, earnings, morning_brief, weekly_summary, research, geopolitical
- `config/` — portfolio.yaml, theses.yaml, keywords.yaml, news_sources.yaml
- `prompts/` — LLM prompt templates (.txt with `{placeholders}`)
- `bin/` — deploy.sh, start, sandbox-setup.sh, sandbox-policy.yaml
- `tests/` — test_fixes.py (pytest)
- `data/` — news_log.db (SQLite, WAL mode)

## Critical landmines

- **Prompt template braces**: templates use `{var}` for Python `.format()`. Literal JSON braces in prompt .txt files MUST be escaped as `{{ }}` or scoring crashes.
- **Timezone mismatch**: `news_store` writes with `CURRENT_TIMESTAMP` (UTC) but `get_recent()` queries with `datetime.now()` (local time). Known issue — don't make it worse.
- **Telegram Markdown**: uses legacy `parse_mode="Markdown"` (not MarkdownV2). Escape `_` and `*` in dynamic content. Do NOT switch to MarkdownV2 — would break all format strings.
- **Sandbox restrictions**: no sudo, no tmux, no ps/pkill, restricted network via L7 proxy with hostname allowlist.
- **New RSS feed = policy update**: adding a feed requires adding its hostname to `bin/sandbox-policy.yaml` and redeploying with `openshell policy set`.
- **POST must be explicit**: sandbox network policy defaults to GET-only. Non-GET endpoints need `method: "*"` or `access: full` in policy rules.

## Key patterns

- **LLM client**: `llm_client.chat()` retries 3x with backoff [5s, 15s, 30s], 90s timeout. `json_chat()` strips markdown fences before JSON parse.
- **Single instance**: enforced via `/tmp/nemoclaw.lock` (fcntl.flock + PID file).
- **Config hot-reload**: `config_loader.reload_all()` re-reads all YAML at runtime.
- **News pipeline**: fetch -> dedup (URL + fuzzy title 0.85) -> keyword filter -> LLM score -> store (SQLite) -> alert (Telegram).
- **Geo sources** (Al Jazeera, BBC World, Guardian World): bypass keyword filtering with 15-article cap.
- **Score thresholds**: save if >= 5, alert if >= 7, editorial sources capped at 7.
- **Scheduler**: `schedule` library, 30s tick in background thread. News every 60 min, geo every 20 min, morning brief weekdays 07:00 CET, weekly Saturday 07:00 CET.
- **Threading**: scheduler in background thread, chat history protected by `_CHAT_LOCK`.

## Environment

- `.env` holds `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `NVIDIA_API_KEY` — never commit
- `inference.local` is a gateway-injected virtual host (always reachable from sandbox)
- LLM: Nemotron-3-super-120b via OpenAI-compatible API at `https://inference.local/v1`

## Environment Constraints

This project runs on sandboxed environments with restricted network policies, no sudo, no tmux, no pkill/ps, and limited package installation. Always check for these constraints before suggesting installation commands or system-level operations.

## Code style

- Private functions: `_prefixed()`
- Module logger: `logger = logging.getLogger(__name__)`
- Constants: `UPPERCASE`
- Config keys: `snake_case` in YAML
- Synchronous design — no async/await

## Don'ts

- Don't refactor or add abstractions unless asked
- Don't add type annotations or docstrings to existing code unless asked
- Don't add error handling for impossible scenarios
- Don't switch to APScheduler/celery or add async
- Don't install new dependencies without asking
- Don't add retry/backoff logic beyond what already exists in llm_client
