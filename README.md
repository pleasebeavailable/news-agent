# NemoClaw — Portfolio Intelligence Bot

Telegram bot running inside an OpenShell sandbox (`rich-biatch`) on Nemotron-3-super-120b-a12b.
Monitors news, prices, earnings, and runs on-demand research for a personal portfolio.
Any message that isn't a command gets a free-form LLM response with rolling conversation context.

---

## Daily use

The bot runs persistently via `nohup` — **SSH disconnects do not stop it**.

```bash
nemoclaw rich-biatch connect     # reconnect to sandbox
tail -f /tmp/nemoclaw.log        # watch live logs
start                            # (re)start bot
kill $(cat /tmp/nemoclaw.lock)   # stop bot
```

---

## Full setup from scratch

If the sandbox was destroyed or you're setting up on a new machine, follow every step.
If the sandbox already exists, skip to [Deploy & restart](#deploy--restart).

### 1. Prerequisites (Mac)

- Docker Desktop running (check: `docker ps`)
- `openshell` CLI installed (`openshell --version`, needs 0.0.12+)
- `nemoclaw` CLI installed
- `.env` file in repo root with credentials (copy from `.env.example`):
  ```
  TELEGRAM_BOT_TOKEN=<your bot token>
  TELEGRAM_CHAT_ID=<your chat id>
  NVIDIA_API_KEY=<your nvidia api key>
  ```

### 2. Start the gateway

```bash
openshell gateway start --name nemoclaw
```

Wait for it to fully complete — do not interrupt. Then select it:

```bash
openshell gateway select nemoclaw
```

Verify it's healthy:

```bash
openshell gateway select    # should show nemoclaw as active
```

### 3. Onboard (creates sandbox + inference identity)

```bash
nemoclaw onboard
```

- When prompted for sandbox name, enter: `rich-biatch`
- Choose **Nemotron 3 Super 120B** when prompted for model
- If step 6 fails with "sandbox not found": run `openshell sandbox create --name rich-biatch`, then `bash ~/openclaw-agent/bin/install.sh --from-step 7`
- Let it fully complete — do not Ctrl+C

> **WARNING:** `nemoclaw onboard` always does a FULL reset — it destroys the existing
> gateway and sandbox. Only run this for first-time setup or when the inference
> identity (`/sandbox/.nemoclaw/config.json` + `/sandbox/.openclaw-data/identity/`)
> is missing. For other issues, try `deploy.sh` or `openshell gateway start` first.

### 4. Configure inference provider

After onboard, verify the inference provider is set up correctly:

```bash
openshell inference get
openshell provider list
```

The provider **must** be `type: nvidia` (not `type: openai`). If it shows `openai`, fix it:

```bash
# Load your API key
set -a; source .env; set +a

# Create correct nvidia-type provider
openshell provider create --name nvidia-cloud --type nvidia --from-existing

# Point inference routing to it
openshell inference set --provider nvidia-cloud --model nvidia/nemotron-3-super-120b-a12b
```

Verify it validates against the real endpoint:

```bash
openshell inference get
# Should show:
#   Route: inference.local
#   Provider: nvidia-cloud
#   Validated Endpoints: https://integrate.api.nvidia.com/v1/chat/completions
```

> **How inference.local works:** Code in the sandbox calls `https://inference.local/v1/...`.
> The OpenShell gateway intercepts this virtual hostname, injects the real NVIDIA API
> credentials from the provider config, and forwards to `integrate.api.nvidia.com`.
> The sandbox never sees the real API key. This is separate from network policies —
> `inference.local` does NOT need to be in `no_proxy` or the network policy allowlist
> (though having it there doesn't hurt).

### 5. Deploy (one command does everything)

```bash
bash ~/openclaw-agent/bin/deploy.sh
```

This automatically:
- Creates directories on sandbox
- Uploads `.env` with all credentials (Telegram, NVIDIA)
- Uploads all code, config, prompts, start script
- Creates Python venv and installs dependencies
- Sets up `start` command (symlink + PATH in `.bashrc`)
- Applies network policy (Telegram, Yahoo Finance, RSS, PyPI)

### 6. Start the bot

```bash
nemoclaw rich-biatch connect
start
tail -f /tmp/nemoclaw.log
```

### 7. Verify

- Send `status` in Telegram — should reply "All systems go"
- Send `watchlist` — should return live prices
- Send `morning brief` — should generate a brief (takes ~30-45s due to model reasoning)
- Send any free-form message (e.g. "what's up") — should get an LLM response
- Check logs: `tail -f /tmp/nemoclaw.log`

---

## Deploy & restart

After code changes, from your Mac:

```bash
bash ~/openclaw-agent/bin/deploy.sh
```

Then on the sandbox:

```bash
start    # kills old process and restarts
```

`deploy.sh` is idempotent — safe to run repeatedly. It re-uploads `.env`,
reinstalls deps, re-applies network policy every time.

---

## Bot commands

| Command | What it does |
|---|---|
| `morning brief` | Run morning brief now |
| `weekly summary` | Run weekly summary now |
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
| *(anything else)* | Free-form chat with LLM (keeps 20-message context) |

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
                                             └── free-form chat       (LLM, 20-msg history)

Background scheduler (30s tick):
  ├── every N min  → run_news_cycle()   [fetch all → score → store → alert]
  ├── every 20 min → run_geo_scan()     [fetch geo only → score → store → alert if ≥7]
  ├── weekdays 07:00 → morning_brief
  └── Saturday 07:00 → weekly_summary

Startup:
  1. init_db() — creates SQLite tables (WAL mode)
  2. scheduler thread starts
  3. startup news cycle fires in background thread
  4. Telegram poll loop starts
```

| Component | Value |
|---|---|
| Sandbox | rich-biatch |
| Workspace | /sandbox/workspace/ |
| Model | nvidia/nemotron-3-super-120b-a12b |
| Inference URL | https://inference.local/v1 (virtual — routed by OpenShell gateway) |
| Interface | Telegram |
| Log file | /tmp/nemoclaw.log |
| News DB | /sandbox/workspace/data/news_log.db |
| Python | /sandbox/.venv/bin/python3 (uv-managed) |

---

## Sandbox network policy

Policy file: `~/openclaw-agent/bin/sandbox-policy.yaml`
Applied automatically by `deploy.sh`.

**Important:** The network policy controls which binaries can reach which external hosts.
`inference.local` is handled separately by the OpenShell gateway (see step 4 above) —
it does NOT need a network policy entry to work for POST requests.

| Policy block | Hosts | Why |
|---|---|---|
| `nvidia_inference` | inference.local, integrate.api.nvidia.com | LLM inference (must have `rules: allow method: "*"` for POST) |
| `telegram` | api.telegram.org | bot send/receive (must allow POST to `/bot*/**`) |
| `yahoo_finance` | query1/query2/finance.yahoo.com, fc.yahoo.com | yfinance + crumb auth |
| `rss_feeds` | marketwatch, dowjones, cnbc, bbc, feedburner, investing, rsshub, seekingalpha, aljazeera, guardian, ft, bloomberg, google news, hoisington, gorozen, artberman, geopoliticalfutures, geopoliticalalpha | news + research fetching |
| `pypi` | pypi.org, files.pythonhosted.org | pip install |

**Critical: endpoint rules.** The OpenShell L7 proxy defaults to **read-only (GET only)**
if no `access` or `rules` field is set. Any endpoint that needs POST must explicitly allow it:

```yaml
# Option A: wildcard rules (used in official NemoClaw policy)
rules:
- allow: { method: "*", path: "/**" }

# Option B: access field
access: full
```

Without this, POST requests return 403 even though GET works. This is the #1 gotcha.
See [NemoClaw #314](https://github.com/NVIDIA/NemoClaw/issues/314).

**Critical: binary matching.** The proxy checks which binary is making the request.
Each policy block has a `binaries` list — the actual Python binary must be listed.
The sandbox uses uv-managed Python via venv symlinks:

```
/sandbox/.venv/bin/python3 → /sandbox/.uv/python/cpython-X.Y-linux-aarch64-gnu/bin/pythonX.Y
```

The policy uses `/sandbox/.uv/python/**` glob to match any uv-installed Python version.
If you get `403 Forbidden` proxy errors after a Python upgrade, check the real path:

```bash
readlink -f /sandbox/.venv/bin/python3
```

Then ensure that path (or a matching glob) is in `binaries` for each policy block
in `bin/sandbox-policy.yaml`.

To manually apply/update policy:
```bash
openshell policy set --policy ~/openclaw-agent/bin/sandbox-policy.yaml rich-biatch --wait
```

### Adding a new RSS feed or research source

When you add a feed to `config/news_sources.yaml`, you **must also** add its hostname
to `bin/sandbox-policy.yaml` under the `rss_feeds` block. Otherwise the sandbox proxy
blocks the request with `403 Forbidden` / `ProxyError: Tunnel connection failed`.

Checklist:
1. Add the feed to `config/news_sources.yaml`
2. Extract the hostname: `python3 -c "from urllib.parse import urlparse; print(urlparse('THE_URL').hostname)"`
3. Add `- host: <hostname>` + `port: 443` under `rss_feeds.endpoints` in `bin/sandbox-policy.yaml`
4. If the feed is a geo source, add `geo: true` to the YAML entry and add the feed name to `GEO_SOURCES` in `core/news_fetcher.py`
5. Deploy: `bash ~/openclaw-agent/bin/deploy.sh` (re-applies policy automatically)

---

## Troubleshooting

**Bot not responding**
```bash
tail -f /tmp/nemoclaw.log    # check if it's running
start                        # restart if needed
```

**`start` command not found**
```bash
ln -sf /sandbox/workspace/start ~/start
echo 'export PATH="$HOME:$PATH"' >> ~/.bashrc
source ~/.bashrc
```
Or just: `bash /sandbox/workspace/start`

**Telegram/Yahoo/RSS 403 proxy errors**
1. Check policy is applied: `openshell policy get rich-biatch`
2. Check binary matches: `readlink -f /sandbox/.venv/bin/python3` — must match a `binaries` glob in policy
3. Re-apply: `openshell policy set --policy ~/openclaw-agent/bin/sandbox-policy.yaml rich-biatch --wait`
4. After sandbox rebuild, policy is wiped — `deploy.sh` re-applies it automatically

**LLM calls fail (403 Forbidden from inference.local)**

This is almost always an inference provider/routing issue, NOT a network policy issue.

1. Check inference routing from your Mac:
   ```bash
   openshell inference get
   ```
   - If provider is missing or wrong type: see [step 4](#4-configure-inference-provider)
   - Provider must be `type: nvidia`, not `type: openai`

2. Check provider has credentials:
   ```bash
   openshell provider get <provider-name>
   ```
   If credentials are missing, recreate:
   ```bash
   set -a; source .env; set +a
   openshell provider create --name nvidia-cloud --type nvidia --from-existing
   openshell inference set --provider nvidia-cloud --model nvidia/nemotron-3-super-120b-a12b
   ```

3. Verify the endpoint validates:
   ```bash
   openshell inference get
   # Must show: Validated Endpoints: https://integrate.api.nvidia.com/v1/chat/completions
   ```

4. If all above looks correct, test from sandbox:
   ```bash
   curl -s https://inference.local/v1/models | head -5
   ```

5. If still broken, check gateway is running:
   ```bash
   openshell gateway info    # from Mac
   ```
   If no gateway: `openshell gateway start --name nemoclaw && openshell gateway select nemoclaw`

6. Nuclear option — full re-onboard (destroys everything):
   ```bash
   nemoclaw onboard
   bash ~/openclaw-agent/bin/deploy.sh
   ```

**LLM returns empty response (0 chars, finish=length)**

Nemotron 3 Super generates internal reasoning tokens before producing visible output.
If `max_tokens` is too low, all tokens go to reasoning and content is empty.
The `finish_reason: length` confirms the token budget ran out. Increase `max_tokens`
in the calling skill (morning brief uses 4096, free-form chat uses 2048).

**Gateway won't start / K8s errors**
```bash
openshell gateway destroy --name nemoclaw
openshell gateway start --name nemoclaw
openshell gateway select nemoclaw
```
Then re-onboard and deploy.

**`nemoclaw onboard` step 6 fails ("sandbox not found")**
The sandbox name exists in config but the container is gone.
```bash
openshell sandbox create --name rich-biatch
bash ~/openclaw-agent/bin/install.sh --from-step 7
bash ~/openclaw-agent/bin/deploy.sh
```

**pip / ModuleNotFoundError**
Dependencies not installed. Run on sandbox:
```bash
/sandbox/.venv/bin/pip install -r /sandbox/workspace/requirements.txt
```
Or re-deploy: `bash ~/openclaw-agent/bin/deploy.sh` (installs deps automatically).

**`.env` missing / TELEGRAM_BOT_TOKEN not set**
```bash
bash ~/openclaw-agent/bin/deploy.sh    # uploads .env from local repo
```

**Log flooding (same error repeating fast)**
The poll loop has exponential backoff (5s → 60s max). If you see rapid repeats,
it's likely an older version of the code. Redeploy.

**Policy file format errors**
- `version` must be integer `1`, not string `"1"`
- Old format (`network: allow:`) is no longer accepted — use `network_policies:` with the new OpenShell format
- Reference the official policy: [nemoclaw-blueprint/policies/openclaw-sandbox.yaml](https://github.com/NVIDIA/NemoClaw/blob/main/nemoclaw-blueprint/policies/openclaw-sandbox.yaml)

---

## Key files

| File | Purpose |
|---|---|
| `.env` | Credentials (gitignored) |
| `.env.example` | Template for `.env` |
| `bin/deploy.sh` | One-command deploy to sandbox |
| `bin/sandbox-setup.sh` | Post-deploy setup (runs inside sandbox) |
| `bin/sandbox-policy.yaml` | Network policy for proxy allowlist |
| `bin/start` | Bot start script (nohup + PID lock) |
| `bin/install.sh` | Full installer (gateway + onboard + config) |
| `main.py` | Entry point — poll loop, scheduler, command router |
| `core/` | LLM client, Telegram bot, stock data, news store |
| `skills/` | Morning brief, weekly summary, research, earnings, etc. |
| `config/` | Portfolio, theses, keywords, news sources |
| `prompts/` | LLM prompt templates |
