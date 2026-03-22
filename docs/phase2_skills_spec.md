# Phase 2: Portfolio Intelligence Skills — Full Specification

**Agent**: NemoClaw on OpenShell sandbox `rich-biatch`
**Model**: nvidia/nemotron-3-super-120b-a12b (nvidia-nim, GPU-accelerated)
**Interface**: Telegram bot
**Scheduling**: `schedule` library in `main.py` (news every 15m, geo every 30m, briefs at 07:00)

---

## Global Configuration

### `config/portfolio.yaml`

```yaml
# ── Portfolio & Watchlist ──────────────────────────────────────
# To add/remove positions: edit this list + run `reload` in Telegram
# Or use Telegram commands: `add TICKER` / `remove TICKER`
# Tickers are auto-resolved (e.g., CSPX → CSPX.L for yfinance)

watchlist:
  # ── AI Infra (46.8% of portfolio) ──
  - ticker: NVDA
    type: stock
    exchange: NASDAQ
    theme: AI Infra
    shares: 105
    cost: 96.63
  - ticker: NBIS
    type: stock
    exchange: NASDAQ
    theme: AI Infra
    shares: 80
    cost: 37.30
  - ticker: AMZN
    type: stock
    exchange: NASDAQ
    theme: AI Infra
    shares: 52
    cost: 230.64
  - ticker: GOOG
    type: stock
    exchange: NASDAQ
    theme: AI Infra
    shares: 22
    cost: 191.65
  - ticker: GLW
    type: stock
    exchange: NYSE
    theme: AI Infra
    shares: 45
    cost: 137.84
  - ticker: MRVL
    type: stock
    exchange: NASDAQ
    theme: AI Infra
    shares: 63
    cost: 82.68

  # ── China/EM (11.0%) ──
  - ticker: BABA
    type: stock
    exchange: NYSE
    theme: China/EM
    shares: 60
    cost: 215.34
  - ticker: "2689.HK"
    type: stock
    exchange: HKEX
    theme: China/EM
    shares: 4000
    cost: 3.47

  # ── Crypto (17.8%) ──
  - ticker: BMNR
    type: stock
    exchange: NASDAQ
    theme: Crypto
    shares: 533
    cost: 33.85
  - ticker: HOOD
    type: stock
    exchange: NASDAQ
    theme: Crypto
    shares: 84
    cost: 103.61
  - ticker: ORBS
    type: stock
    exchange: OTC
    theme: Crypto
    shares: 964
    cost: 2.80

  # ── Brazil (8.4%) ──
  - ticker: PBR
    type: adr
    exchange: NYSE
    theme: Brazil
    shares: 300
    cost: 15.55
  - ticker: VALE
    type: adr
    exchange: NYSE
    theme: Brazil
    shares: 200
    cost: 15.58

  # ── Vol/Options (6.1%) ──
  - ticker: FLOW.AS
    type: stock
    exchange: AMS
    theme: Vol/Options
    shares: 200
    cost: 16.22

  # ── Satellites ──
  - ticker: OPEN
    type: stock
    exchange: NASDAQ
    theme: Satellite
    shares: 137
    cost: 3.36
  - ticker: SKYX
    type: stock
    exchange: NASDAQ
    theme: Satellite
    shares: 450
    cost: 1.25

  # ── Frozen (excluded from active monitoring) ──
  # - ticker: OGZD  # Gazprom ADR — sanctioned, frozen, ignore
  #   type: adr
  #   exchange: LSE
  #   theme: Sanctioned
  #   shares: 104
  #   cost: 5.99

# ── Display ────────────────────────────────────────────────────
display:
  currency: USD
  telegram_format: markdown  # structured with headers/sections

# ── Scheduling ─────────────────────────────────────────────────
schedule:
  morning_brief:
    time: "07:00"
    timezone: "Europe/Zagreb"  # CET/CEST auto
    days: [mon, tue, wed, thu, fri]
  weekly_summary:
    time: "07:00"
    timezone: "Europe/Zagreb"
    day: sat

# ── Alert Thresholds ───────────────────────────────────────────
alerts:
  news_score_immediate: 7       # score >= 7 → instant Telegram alert
  news_score_log: 5             # score 5-6 → logged for morning brief
  news_score_drop: 4            # score < 5 → discarded
  premarket_mover_pct: 3.0      # % change to flag in morning brief
  earnings_alert: immediate     # for watchlist tickers
  earnings_others: morning      # non-watchlist → morning brief
```

### `config/theses.yaml`

```yaml
# ── Investment Theses ──────────────────────────────────────────
# Source: Claude portfolio project (Position Theses artifact)
# Used by Skill 5 (Weekly Summary) for drift detection
# Update via: edit this file OR Telegram `set thesis TICKER: text`

NVDA:
  thesis: >
    Undisputed GPU monopoly — 92% data center GPU share, $216B FY26 revenue (+65% YoY).
    Vera Rubin architecture shipping H2 2026 extends generational lead. GTC 2026 guided
    $1T+ cumulative Blackwell/Rubin revenue through 2027. Forward P/E ~21x on FY28
    consensus ($10.80 EPS). Groq LPX inference chips add new TAM layer.
  kill: "Hyperscaler capex pivot or custom ASIC (Broadcom/Marvell) displacing >15% of GPU workloads. China export restrictions tightening further."
  stance: "HOLD. Core conviction. Add aggressively on pullback to $140-150."
  strategy: core_hold

NBIS:
  thesis: >
    Neocloud leader — $27B Meta deal (largest neocloud contract ever) + Nvidia $2B
    strategic investment (8.3% stake). ARR trajectory from $1.25B to $7-9B in 2026.
    Full-stack AI infra. $4B convertible notes for data center buildout.
  kill: "Neocloud business model proves unprofitable at scale. Meta or major customer churns. Dilution from convertible notes overwhelming growth."
  stance: "HOLD. +215% gain. Add on pullbacks to $90-100. Next earnings Apr 29."
  strategy: core_hold

AMZN:
  thesis: >
    AWS dominant cloud platform — AI workload migration driving re-acceleration.
    Trainium custom chips reduce Nvidia dependence. Retail margins expanding.
    Advertising ~$60B+ run rate. 1M Nvidia chips deal through 2027.
  kill: "AWS growth decelerating below 15%. Capex cycle not translating to revenue acceleration. Antitrust action forcing structural changes."
  stance: "HOLD. Position sized appropriately. Thesis intact despite near-term FCF headwind."
  strategy: core_hold

GOOG:
  thesis: >
    Search + AI moat deepening with Gemini integration. YouTube + Cloud triple-engine
    growth. Google Cloud growing 30%+ with AI workloads. TPU competitive for inference.
    Cheapest Mag7 stock on forward P/E basis.
  kill: "Search market share erosion from AI-native competitors (Perplexity, ChatGPT). Antitrust forced divestiture of Chrome/Android."
  stance: "HOLD. Trimmed 10 shares @ $305.10 on Mar 9. Core AI Infra allocation."
  strategy: core_hold

GLW:
  thesis: >
    Fiber optic monopoly play on AI data center buildout — $6B Meta deal anchors
    multi-year visibility. OFC 2026: multicore fiber (4x capacity), co-packaged optics,
    PRIZM TMT connectors. Springboard plan targets $11B incremental annualized sales by 2028.
  kill: "AI capex cycle reversal. Chinese fiber competitors (YOFC) undercutting on price."
  stance: "HOLD. Add on pullback to $120-125. Meta deal validates thesis."
  strategy: core_hold

MRVL:
  thesis: >
    Custom ASIC leadership — designing AI chips for Amazon, Google, Microsoft.
    1.6T optical DSP leadership. Celestial AI acquisition adds photonics.
    Revenue inflection as custom ASIC ramp accelerates in 2026.
  kill: "Custom ASIC programs cancelled or delayed. Optical DSP competition from Broadcom. Celestial AI integration risk."
  stance: "HOLD. Just added 30 shares @ $87.50. Add on pullback to $78-82."
  strategy: accumulate

BABA:
  thesis: >
    China's preeminent AI cloud play — Qwen 300M MAU, cloud revenue +36% to $6.2B.
    $52B AI/cloud capex over 3 years. Steep valuation discount — 18-22x P/E with
    $41B net cash. Xi-Jack Ma rapprochement signals regulatory thaw.
  kill: "US-China escalation (delisting, expanded sanctions). Cloud/AI monetization stalls. Consumer spending deterioration."
  stance: "TRIMMED 102 shares @ $125.54 on Mar 19. Remaining 60 shares reduced weight. Reassess at Trump-Xi summit."
  strategy: reduced_hold

"2689.HK":
  thesis: >
    China packaging/paper leader riding stimulus + containerboard pricing recovery.
    +109% gain — house money position after 50% trim at HKD 8.08.
    Low-maintenance China consumer recovery proxy.
  kill: "Close below HKD 6.00 on heavy volume. Earnings miss. Chinese economic deterioration."
  stance: "LET IT RIDE. Kill switch at HKD 6.00. House money."
  strategy: house_money

BMNR:
  thesis: >
    World's largest public ETH treasury — 4.6M ETH (3.81% of supply), $11.5B in
    crypto+cash+moonshots. MAVAN staking network imminent (Q1 2026) — 3M+ ETH staked,
    ~$180M annualized revenue. Trading at ~0.8x book value (20% NAV discount).
  kill: "ETH price collapse below $1,200. MAVAN launch delays or security breach. Excessive dilution."
  stance: "LOT RESHAPING in progress. Adding cheap lots post-BABA trim. Pure ETH beta play."
  strategy: lot_reshape

HOOD:
  thesis: >
    Fintech platform evolution — 27M+ funded customers, $279B AUC. Revenue +52% to $4.5B.
    Prediction markets + crypto + tokenized assets. Banking scaling past $1B deposits.
    EU expansion with tokenized private equity (SpaceX, OpenAI exposure).
  kill: "Crypto volume collapse (>50% of transaction revenue). PFOF regulatory ban. Valuation compression."
  stance: "HOLD. Tax-loss harvest planned — sell Oct 2025 lots (~$131.85 cost) before year-end."
  strategy: tax_harvest_pending

ORBS:
  thesis: >
    Only publicly listed equity with direct OpenAI exposure — $50M OpenAI equity purchase
    funded by BMNR's $80M investment. Lottery ticket on OpenAI valuation appreciation.
  kill: "OpenAI investment write-down. Company runs out of cash. BMNR withdraws support."
  stance: "LOTTERY TICKET. Continue periodic ~$250 adds. Accept high loss probability."
  strategy: lottery

PBR:
  thesis: >
    State-controlled oil major at ~4x earnings, 8%+ dividend yield. Pre-salt reserves
    lowest cost globally. Hard asset hedge counterbalancing growth-heavy portfolio.
  kill: "Government interference in pricing/dividend policy. Oil collapse below $55. Export tax expansion."
  stance: "HOLD. No aggressive additions at current levels."
  strategy: income_hold

VALE:
  thesis: >
    World's largest iron ore producer. Trump-Xi summit potential catalyst for Chinese
    infrastructure stimulus. Preferred vehicle for incremental Brazil capital.
  kill: "Chinese steel demand collapse. Samarco/Brumadinho liability escalation. Iron ore below $80/ton sustained."
  stance: "ACCUMULATE. Target ~10% combined PBR+VALE. VALE absorbs ~70% of incremental Brazil capital."
  strategy: accumulate

FLOW.AS:
  thesis: >
    Global market maker benefiting from structural volatility — 41% EBITDA margins.
    Crypto market making adds high-margin revenue. ETF proliferation expands TAM.
    Remaining 200 shares = house money after 60-70% trim.
  kill: "Prolonged low-volatility regime. Regulatory constraints on market making."
  stance: "HOLD remaining 200 shares. Broken vol hedge thesis but core business performing."
  strategy: house_money

OPEN:
  thesis: >
    iBuying platform — optionality play on US housing market recovery. Rate cuts
    would unlock transaction volume. Warrants (OPENL/W/Z) expire Nov 2026.
  kill: "Continued housing market freeze. Cash burn accelerates. Bankruptcy risk."
  stance: "HOLD. Satellite position. Warrants expire Nov 2026 — binary outcome."
  strategy: lottery

SKYX:
  thesis: >
    Smart home platform with plug-and-play lighting/ceiling fan tech. 60+ patents.
    Micro-cap optionality play.
  kill: "No commercial traction within 12 months. Cash depletion without revenue scaling."
  stance: "HOLD. Satellite. No additional capital planned."
  strategy: lottery
```

---

## File Structure

```
rich-biatch/
├── config/
│   ├── portfolio.yaml          # watchlist, display, schedule, thresholds
│   ├── theses.yaml             # investment theses per ticker
│   ├── news_sources.yaml       # RSS feeds + X/fintwit config
│   └── keywords.yaml           # keyword groups for news scoring
├── skills/
│   ├── skill_stock_price.py    # Skill 1: Stock Price & Fundamentals
│   ├── skill_news_monitor.py   # Skill 2: News Monitoring
│   ├── skill_earnings.py       # Skill 3: Earnings Calendar
│   ├── skill_morning_brief.py  # Skill 4: Morning Brief
│   ├── skill_weekly_summary.py # Skill 5: Weekly Summary
│   └── skill_research.py       # Skill 6: On-Demand Research
├── core/
│   ├── llm_client.py           # Nemotron API wrapper
│   ├── telegram_bot.py         # Telegram send/receive
│   ├── news_fetcher.py         # RSS + X/fintwit aggregator
│   ├── news_scorer.py          # LLM-based relevance scoring
│   ├── news_store.py           # SQLite log for scored articles
│   └── stock_data.py           # yfinance wrapper
├── data/
│   ├── news_log.db             # SQLite: scored articles
│   └── earnings_cache.json     # cached earnings dates
├── prompts/
│   ├── news_scoring.txt        # scoring rubric prompt
│   ├── morning_brief.txt       # morning brief generation prompt
│   ├── weekly_summary.txt      # weekly summary generation prompt
│   ├── research_bull_bear.txt  # research skill prompt
│   └── earnings_analysis.txt   # post-earnings analysis prompt
└── main.py                     # Telegram command router
```

---

## Skill 1: Stock Price & Fundamentals

### Commands

| Command | Response |
|---------|----------|
| `NVDA` | Current price, daily change ($ and %), P/E, market cap, 52w range + news one-liner |
| `watchlist` | All 16 positions grouped by theme with prices, daily %, news flags |
| `portfolio` | Full view: weights, P&L, cost bases per position |
| `NVDA vs MRVL` | Side-by-side: price, P/E, market cap, YTD%, 1Y%, key metrics |
| `PBR vs VALE` | Side-by-side comparison (works for any two tickers) |

### Data Source

`yfinance` — free, no API key, covers all tickers including LSE-listed ETFs.

### Implementation: `skills/skill_stock_price.py`

```python
import yfinance as yf
from config import load_watchlist

def get_quote(ticker: str) -> dict:
    """Single ticker quote with key fundamentals."""
    t = yf.Ticker(ticker)
    info = t.info
    return {
        "ticker": ticker,
        "price": info.get("regularMarketPrice"),
        "change": info.get("regularMarketChange"),
        "change_pct": info.get("regularMarketChangePercent"),
        "pe": info.get("trailingPE"),
        "market_cap": info.get("marketCap"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "currency": "USD",  # we normalize everything to USD
    }

def get_watchlist() -> list[dict]:
    """All watchlist tickers with daily snapshot."""
    watchlist = load_watchlist()
    return [get_quote(item["ticker"]) for item in watchlist]

def compare_etfs(ticker_a: str, ticker_b: str) -> dict:
    """Side-by-side ETF comparison."""
    a, b = yf.Ticker(ticker_a), yf.Ticker(ticker_b)
    # Pull: price, TER (expense ratio), AUM (total assets),
    # YTD%, 1Y%, dividend yield, tracking difference
    # Format as comparison dict
    ...
```

### Telegram Output Format

```markdown
📊 **NVDA** — NVIDIA Corp
━━━━━━━━━━━━━━━━━━━
💰 Price: $172.70 (+3.21 / +1.89%)
📈 P/E: 21.3 (FY28E)
🏦 Market Cap: $4.23T
📉 52W Range: $98.40 — $185.62
📰 Vera Rubin samples shipping to hyperscalers — [link]
```

```markdown
📋 **Watchlist** (16 positions)
━━━━━━━━━━━━━━━━━━━

🟢 **AI Infra** (46.8%)
NVDA   $172.70   +1.89%  📰 Vera Rubin samples shipping
NBIS   $117.62   +0.45%
AMZN   $205.37   -0.32%
GOOG   $298.79   +0.67%
GLW    $124.58   +2.10%  📰 Meta fiber deal expanded
MRVL   $87.91    +4.22%  🔥📰 Celestial AI integration update

🟡 **China/EM** (11.0%)
BABA   $122.41   -1.20%
2689   HKD 7.27  +0.83%

🟣 **Crypto** (17.8%)
BMNR   $20.94    +6.50%  🔥📰 MAVAN staking beta live
HOOD   $70.89    -0.44%
ORBS   $0.94     +2.17%

🔵 **Brazil** (8.4%)
PBR    $18.80    +0.54%
VALE   $14.05    +1.21%  📰 Iron ore +3% on China PMI

💗 **Vol/Options** (6.1%)
FLOW   €26.84    +0.37%

⚪ **Satellites**
OPEN   $4.91     +1.03%
SKYX   $1.66     -0.60%

━━━━━━━━━━━━━━━━━━━
🔥 = moved > 3% | 📰 = news today (tap for details)
```

---

## Skill 2: Geopolitical & Market News Monitoring

### Architecture

```
RSS Feeds ──┐
             ├──→ news_fetcher.py ──→ news_scorer.py ──→ news_store.py
X/Fintwit ──┘         │                    │                   │
                  deduplicate         LLM scores 1-10     SQLite log
                  & normalize              │
                                     ┌─────┴─────┐
                                     │           │
                                  score≥7    score 5-6
                                     │           │
                              Telegram alert  Log for
                              (immediate)    morning brief
```

### Config: `config/news_sources.yaml`

```yaml
# ── RSS Feeds (reliable, free) ─────────────────────────────────
rss_feeds:
  # Tier 1: Most reliable, free, fast
  - name: Reuters Business
    url: https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best
    tier: 1
  - name: CNBC Top News
    url: https://www.cnbc.com/id/100003114/device/rss/rss.html
    tier: 1
  - name: CNBC World
    url: https://www.cnbc.com/id/100727362/device/rss/rss.html
    tier: 1
  - name: MarketWatch Top Stories
    url: https://feeds.marketwatch.com/marketwatch/topstories/
    tier: 1
  - name: MarketWatch Markets
    url: https://feeds.marketwatch.com/marketwatch/marketpulse/
    tier: 1

  # Tier 1+: Paid subscription — full article access
  - name: Seeking Alpha
    url: https://seekingalpha.com/market_currents.xml  # RSS for real-time market currents
    tier: 1
    api: true  # also use SA Premium API for full articles, analysis, quant ratings
    note: paid subscription — use API for deep research (Skill 6), RSS for monitoring (Skill 2)
  - name: ZeroHedge
    url: https://feeds.feedburner.com/zerohedge/feed
    tier: 2
    trust_flag: editorial  # flag in scoring: treat as opinion, verify claims

  # Tier 3: Paywalled but sometimes accessible via RSS summary
  - name: FT Markets
    url: https://www.ft.com/rss/home
    tier: 3
    note: may only get headlines
  - name: Bloomberg
    url: https://feeds.bloomberg.com/markets/news.rss
    tier: 3
    note: often restricted

  # Additional free reliable sources
  - name: Yahoo Finance
    url: https://finance.yahoo.com/news/rssindex
    tier: 1
  - name: Investing.com News
    url: https://www.investing.com/rss/news.rss
    tier: 2
  - name: AP Business
    url: https://rsshub.app/apnews/topics/business
    tier: 1
  - name: BBC Business
    url: http://feeds.bbci.co.uk/news/business/rss.xml
    tier: 1

# ── X/Fintwit (via RSS bridge) ────────────────────────────────
x_fintwit:
  method: rss_bridge  # options: nitter, rss_app, rsshub
  bridge_url: ""  # to be configured — nitter instance or rss.app endpoint
  poll_interval_minutes: 5
  accounts:
    # Breaking news / fast signals
    - handle: DeItaone        # Walter Bloomberg — breaks news fastest
      category: breaking
    - handle: unusual_whales  # options flow, unusual activity
      category: flow
    - handle: financialjuice  # real-time market headlines
      category: breaking

    # Macro / geopolitics
    - handle: MacroAlf        # macro analysis
      category: macro
    - handle: zaborarna       # geopolitics
      category: geopolitics

    # Semiconductors / tech specific
    - handle: SemiAnalysis    # deep semiconductor analysis
      category: semiconductors
    - handle: chiikiiii       # NVIDIA / GPU specific
      category: semiconductors

    # General market commentary
    - handle: TruthGundlach   # bond market, macro
      category: macro
    - handle: elerianm        # Mohamed El-Erian — macro
      category: macro

  # You can add/remove accounts anytime
  # Run: edit config/news_sources.yaml → restart news fetcher
```

### Config: `config/keywords.yaml`

```yaml
# ── Keyword Groups for News Scoring ─────────────────────────────
# Used by news_scorer.py to pre-filter before LLM scoring
# Articles matching 0 keyword groups are skipped entirely (no LLM call)
#
# Portfolio: ~$84K NAV, 17 positions across AI Infra, China/EM,
#            Crypto, Brazil, Vol/Options, Satellites
# Last updated: 2026-03-22

keyword_groups:

  # ━━━ TIER 1 — DIRECT PORTFOLIO HOLDINGS ━━━

  portfolio_tickers:
    weight: 2.5  # highest — directly names a held position
    terms:
      # AI Infra (46.8%)
      - NVDA
      - NVIDIA
      - Nvidia
      - NBIS
      - Nebius
      - GOOG
      - Alphabet
      - AMZN
      - Amazon
      - GLW
      - Corning
      - MRVL
      - Marvell
      # China/EM (11.0%)
      - BABA
      - Alibaba
      - Nine Dragons Paper
      - "2689"
      # Crypto (17.8%)
      - BMNR
      - Bitmine
      - HOOD
      - Robinhood
      - ORBS
      - Eightco
      # Brazil (8.4%)
      - PBR
      - Petrobras
      - VALE
      - Vale SA
      # Vol/Options (6.1%)
      - FLOW
      - Flow Traders
      # Satellites
      - OPEN
      - Opendoor
      - SKYX

  portfolio_adjacent:
    weight: 2.0  # companies/products directly tied to held positions
    terms:
      # NVDA ecosystem
      - Blackwell
      - Vera Rubin
      - Jensen Huang
      - GTC
      - CUDA
      - Groq LPX
      # NBIS ecosystem
      - Nebius Meta deal
      - neocloud
      - CoreWeave
      # BMNR ecosystem
      - MAVAN
      - MAVAN staking
      - Ethereum treasury
      - Beast Industries
      # BABA ecosystem
      - Qwen
      - Alibaba Cloud
      - Taobao
      - Tmall
      # GLW ecosystem
      - GlassWorks AI
      - PRIZM TMT
      - multicore fiber
      - co-packaged optics
      # MRVL ecosystem
      - Celestial AI
      - optical DSP
      - custom ASIC
      # HOOD ecosystem
      - Robinhood prediction markets
      - Kalshi
      # ORBS/OpenAI link
      - OpenAI equity
      - OpenAI valuation

  # ━━━ TIER 2 — THEMATIC / SECTOR ━━━

  ai_infrastructure:
    weight: 1.8  # core theme — 46.8% of portfolio
    terms:
      - AI chip
      - GPU
      - data center
      - hyperscaler capex
      - AI infrastructure
      - AI spending
      - inference
      - training cluster
      - AI factory
      - neocloud
      - GPU cluster
      - AI server
      - AI accelerator
      - TPU
      - Trainium
      - HBM
      - CoWoS

  semiconductors:
    weight: 1.5
    terms:
      - chip
      - semiconductor
      - TSMC
      - foundry
      - wafer
      - EUV
      - ASML
      - Broadcom
      - AVGO
      - export controls
      - chip ban
      - advanced packaging

  fiber_optics_networking:
    weight: 1.5  # GLW + MRVL theme
    terms:
      - fiber optic
      - optical fiber
      - OFC conference
      - optical connectivity
      - optical transceiver
      - 800G
      - 1.6T
      - coherent optics
      - data center interconnect
      - DCI
      - submarine cable

  crypto_digital_assets:
    weight: 1.5  # BMNR + HOOD + ORBS = 17.8%
    terms:
      - Ethereum
      - ETH
      - Bitcoin
      - BTC
      - crypto treasury
      - staking
      - staking yield
      - Ethereum staking
      - crypto regulation
      - GENIUS Act
      - stablecoin
      - tokenization
      - SEC crypto
      - spot ETF
      - crypto ETF
      - DeFi

  china_tech:
    weight: 1.3  # BABA + 2689 = 11%
    terms:
      - China tech
      - Chinese AI
      - DeepSeek
      - China cloud
      - China stimulus
      - China consumer
      - China e-commerce
      - JD.com
      - Tencent
      - Meituan
      - Hang Seng
      - HSCEI
      - China regulatory
      - China tech crackdown
      - Jack Ma

  brazil_commodities:
    weight: 1.2  # PBR + VALE = 8.4%
    terms:
      - Petrobras
      - Brazil oil
      - pre-salt
      - iron ore
      - Brazil macro
      - Brazilian real
      - BRL
      - Lula
      - Brazil export tax
      - commodity prices
      - oil prices
      - Brent crude
      - WTI
      - OPEC
      - Vale mining
      - China iron ore demand

  # ━━━ TIER 3 — MACRO & CROSS-CUTTING ━━━

  geopolitics:
    weight: 1.5  # elevated — BABA/NVDA binary on US-China
    terms:
      - US-China
      - Trump Xi
      - tariff
      - sanctions
      - trade war
      - export ban
      - chip ban
      - Taiwan
      - South China Sea
      - decoupling
      - CHIPS Act
      - entity list
      - Pentagon list
      - delisting
      - ADR risk
      - Beijing summit

  macro_rates:
    weight: 1.0
    terms:
      - Fed rate
      - FOMC
      - Powell
      - rate cut
      - rate hike
      - inflation
      - CPI
      - PPI
      - PCE
      - NFP
      - nonfarm
      - employment
      - GDP
      - recession
      - yield curve
      - treasury yield
      - 10-year yield
      - ECB
      - Lagarde

  market_regime:
    weight: 1.0
    terms:
      - VIX
      - volatility
      - margin call
      - S&P 500
      - Nasdaq
      - correction
      - bear market
      - risk-off
      - flight to safety
      - put/call ratio
      - gamma exposure
      - market breadth
      - Magnificent Seven
      - Mag7

  earnings_catalysts:
    weight: 1.3
    terms:
      - earnings
      - quarterly results
      - revenue miss
      - revenue beat
      - EPS
      - guidance
      - analyst upgrade
      - analyst downgrade
      - price target
      - buyback
      - share repurchase
      - dividend
      - investor day

  # ━━━ TIER 4 — MARGIN & TAX (operational) ━━━

  broker_tax:
    weight: 0.8
    terms:
      - Interactive Brokers
      - IBKR
      - margin interest
      - margin requirement
      - FIFO
      - tax-loss harvest
      - capital gains tax
      - withholding tax
      - W-8BEN
      - Croatian tax
      - EU broker regulation
```

### LLM Scoring Prompt: `prompts/news_scoring.txt`

```
You are a financial news analyst for a personal portfolio intelligence system.

PORTFOLIO CONTEXT (~$84K NAV, margin ~$17K):
AI Infra (46.8%): NVDA (17.9%), NBIS (9.3%), AMZN (10.6%), GOOG (6.5%), GLW (5.5%), MRVL (5.5%)
China/EM (11.0%): BABA (7.3%), 2689.HK (3.7%)
Crypto (17.8%): BMNR (11.0%), HOOD (5.9%), ORBS (0.9%)
Brazil (8.4%): PBR (5.6%), VALE (2.8%)
Vol/Options (6.1%): FLOW.AS (6.1%)
Satellites: OPEN (0.7%), SKYX (0.7%)

KEY THESIS DRIVERS:
- NVDA: GPU monopoly, Vera Rubin H2 2026, $1T Blackwell/Rubin guidance
- NBIS: Neocloud leader, $27B Meta deal, Nvidia strategic investment
- BMNR: ETH treasury play, MAVAN staking imminent
- BABA: China AI cloud, regulatory thaw watch, Trump-Xi summit catalyst
- GLW/MRVL: Fiber optics + custom ASIC plays on AI data center buildout
- PBR/VALE: Brazil hard asset hedge, commodity exposure

KILL SWITCHES (immediate alert if triggered):
- NVDA: Hyperscaler capex pivot, custom ASIC displacing >15% GPU workloads
- BABA: US-China delisting escalation
- BMNR: ETH below $1,200, MAVAN security breach
- 2689.HK: Close below HKD 6.00
- HOOD: PFOF regulatory ban

TASK:
Score the following news article for relevance and urgency to this portfolio.

ARTICLE:
Source: {source_name} (Tier: {source_tier})
Title: {title}
Summary: {summary}
Published: {pub_date}
Matched Keywords: {matched_keywords}
Keyword Groups: {matched_groups}

SCORING RUBRIC (1-10):
1-2: No relevance to portfolio or markets
3-4: General market news, no actionable signal
5-6: Relevant to a sector/theme the portfolio is exposed to, moderate signal
7-8: Directly impacts portfolio holdings or a key macro factor, actionable
9-10: Critical — earnings surprise, regulatory action, geopolitical escalation directly affecting holdings, or kill switch triggered

TRUST ADJUSTMENT:
- If source is flagged as "editorial" (e.g., ZeroHedge), cap score at 7 unless corroborated
- Tier 1 sources get full trust
- Seeking Alpha (paid): full trust for analysis, treat market currents as Tier 1
- Tier 2 sources: consider if claim is verifiable
- Tier 3 sources: treat headlines cautiously if full text unavailable

RESPOND IN THIS EXACT JSON FORMAT:
{
  "score": <int 1-10>,
  "category": "<ai_infra|semiconductors|crypto|china|brazil|geopolitics|macro|earnings|market_move|fiber_optics|other>",
  "affected_tickers": ["<ticker>", ...],
  "summary": "<2-3 sentence summary of what happened>",
  "portfolio_impact": "<1-2 sentences: how this affects the user's specific holdings>",
  "suggested_action": "<1 sentence: what to consider doing, referencing actual positions, or 'No action needed'>",
  "kill_switch_triggered": <true|false>,
  "confidence": "<high|medium|low>"
}
```

### News Storage: `core/news_store.py`

```sql
-- SQLite schema for news_log.db
CREATE TABLE IF NOT EXISTS scored_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_tier INTEGER,
    title TEXT NOT NULL,
    url TEXT,
    published_at DATETIME,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    matched_keywords TEXT,       -- JSON array
    matched_groups TEXT,         -- JSON array
    score INTEGER NOT NULL,
    category TEXT,
    affected_tickers TEXT,       -- JSON array
    summary TEXT,
    portfolio_impact TEXT,
    suggested_action TEXT,
    confidence TEXT,
    alerted BOOLEAN DEFAULT 0,  -- 1 if Telegram alert was sent
    included_in_brief BOOLEAN DEFAULT 0  -- 1 if included in morning brief
);

CREATE INDEX idx_score ON scored_news(score);
CREATE INDEX idx_fetched ON scored_news(fetched_at);
CREATE INDEX idx_category ON scored_news(category);
```

### Telegram Alert Format (score ≥ 7)

```markdown
🚨 **ALERT** (Score: 8/10)
━━━━━━━━━━━━━━━━━━━
📰 *New US export controls on AI chips to China*
📡 Source: Reuters (Tier 1)

**What happened:**
The US Commerce Department announced expanded restrictions on AI chip exports to China, including new controls on NVIDIA's H20 chip.

**Portfolio impact:**
Directly affects NVDA (17.9% of portfolio) — China ~20% of data center sales. Secondary impact on BABA if retaliatory measures follow. NBIS/GLW/MRVL exposed as AI infra supply chain.

**Consider:**
Monitor NVDA kill switch (custom ASIC displacement threshold). Watch BABA for ADR delisting rhetoric escalation.

⚠️ Kill switch proximity: NVDA — not triggered but elevated risk
🏷️ Semiconductors | Tickers: NVDA, BABA, NBIS, GLW, MRVL
```

### Deduplication Logic

```python
# In news_fetcher.py
# Articles are deduplicated by:
# 1. Exact URL match
# 2. Title similarity > 85% (fuzzy match via difflib)
# 3. Same story from multiple sources within 2-hour window
#    → keep highest-tier source, log others as "corroborating"
```

---

## Skill 3: Earnings Calendar & Tracking

### Data Source

`yfinance` for earnings dates + Yahoo Finance earnings API for estimates/actuals.

### Implementation: `skills/skill_earnings.py`

```python
import yfinance as yf
from datetime import datetime, timedelta

def get_upcoming_earnings(watchlist: list[str], days_ahead: int = 30) -> list[dict]:
    """Get earnings dates for watchlist tickers."""
    results = []
    for ticker in watchlist:
        t = yf.Ticker(ticker)
        cal = t.calendar
        if cal and "Earnings Date" in cal:
            earnings_date = cal["Earnings Date"]
            if isinstance(earnings_date, list):
                earnings_date = earnings_date[0]  # take earliest
            results.append({
                "ticker": ticker,
                "earnings_date": earnings_date,
                "days_until": (earnings_date - datetime.now()).days,
            })
    return sorted(results, key=lambda x: x["earnings_date"])

def get_earnings_result(ticker: str) -> dict:
    """Post-earnings: actual vs estimate."""
    t = yf.Ticker(ticker)
    # quarterly earnings history
    earnings = t.quarterly_earnings
    # Also check: t.earnings_history for EPS estimates vs actuals
    ...
```

### Alert Flow

```
Daily check (6:00 AM CET):
  For each watchlist ticker:
    If earnings_date == tomorrow:
      → Send Telegram reminder

Post-earnings check (every 30 min from 4 PM - 11 PM ET on earnings days):
  For each watchlist ticker with earnings today:
    If results available:
      → Fetch actual vs estimate
      → Send to Nemotron for analysis
      → Telegram alert (IMMEDIATE for watchlist)
```

### LLM Prompt: `prompts/earnings_analysis.txt`

```
You are an earnings analyst for a personal portfolio.

PORTFOLIO CONTEXT:
The user holds {ticker} ({shares} shares @ ${cost} cost basis, current weight {weight}%).
Theme: {theme}
Thesis: {thesis}
Kill switch: {kill_switch}
Stance: {stance}

EARNINGS DATA:
Ticker: {ticker}
Quarter: {quarter}
EPS Estimate: {eps_estimate}
EPS Actual: {eps_actual}
Revenue Estimate: {rev_estimate}
Revenue Actual: {rev_actual}
Guidance: {guidance_notes}
Seeking Alpha quant rating: {sa_quant}

RESPOND IN THIS EXACT JSON FORMAT:
{
  "beat_miss": "<beat|miss|inline>",
  "surprise_pct": <float>,
  "sentiment": "<bullish|neutral|bearish>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "thesis_impact": "<Does this support or weaken the investment thesis? Reference specific thesis points. 1-2 sentences>",
  "kill_switch_check": "<Is the kill switch closer to triggering? Yes/No + why>",
  "stance_update": "<Should the stance change? e.g., 'Maintain HOLD' or 'Consider upgrading to ACCUMULATE'>",
  "suggested_action": "<1 sentence referencing position size and cost basis>"
}
```

### Telegram Output

```markdown
📊 **NVDA Earnings** — Q4 FY2025
━━━━━━━━━━━━━━━━━━━
✅ **BEAT** (+8.2%)

**EPS:** $0.89 vs $0.82 est
**Revenue:** $39.3B vs $38.1B est (+3.2%)

**Key Takeaways:**
1. Data center revenue +40% YoY, beating estimates
2. China revenue declined 15% due to export controls
3. Guided Q1 above consensus

**Thesis Check:** ✅ AI infrastructure thesis intact — data center growth accelerating despite China headwinds.

**Consider:** Maintain position; leveraged ETFs may see amplified move at open.
```

---

## Skill 4: Morning Brief (Scheduled)

### Schedule

Every weekday at 07:00 CET (Europe/Zagreb timezone, auto-adjusts for DST).

### Data Assembly (runs at 06:45 CET)

```python
def assemble_morning_brief():
    """Gather all data for the morning brief."""
    data = {}

    # 1. US Futures
    data["futures"] = {
        "sp500": get_futures("ES=F"),      # S&P 500 futures
        "nasdaq": get_futures("NQ=F"),     # Nasdaq futures
        "vix": get_quote("^VIX"),          # VIX
    }

    # 2. Overnight news (scored 5+ from last 16 hours)
    data["news"] = get_scored_news(
        since_hours=16,
        min_score=5,
        limit=10,
        order_by="score DESC"
    )

    # 3. Today's events
    data["earnings_today"] = get_earnings_today(watchlist)
    data["fed_speakers"] = get_fed_calendar()  # from RSS/scraped
    data["econ_data"] = get_economic_calendar()  # CPI, NFP, etc.

    # 4. Watchlist pre-market movers (>3%)
    data["movers"] = get_premarket_movers(watchlist, threshold_pct=3.0)

    return data
```

### LLM Prompt: `prompts/morning_brief.txt`

```
You are a personal portfolio briefing assistant. Generate a morning brief in EXACTLY this format. Keep it under 300 words. Use Telegram markdown formatting.

DATA:
{assembled_data_json}

PORTFOLIO CONTEXT (~$84K NAV, margin ~$17K):
AI Infra (46.8%): NVDA, NBIS, AMZN, GOOG, GLW, MRVL
China/EM (11.0%): BABA, 2689.HK
Crypto (17.8%): BMNR, HOOD, ORBS
Brazil (8.4%): PBR, VALE
Vol/Options (6.1%): FLOW.AS
Satellites: OPEN, SKYX

FORMAT:
☀️ **Morning Brief** — {date}
━━━━━━━━━━━━━━━━━━━

📈 **Futures & Sentiment**
S&P 500: {value} ({change})
Nasdaq: {value} ({change})
VIX: {value}
One-line sentiment read.

📰 **Overnight News**
• [Score X] Headline — 1 sentence impact on specific holdings
• [Score X] Headline — 1 sentence impact
(Top 3-5 stories only, highest score first. Always name affected tickers.)

📅 **Today's Events**
• Earnings: {tickers}
• Fed speakers: {names}
• Data: {releases}
(Skip section if empty)

🔥 **Watchlist Movers**
• TICKER: +X.X% — why if known
(Only tickers moving >3%, skip section if none)

💡 **Action Items**
1-2 sentences max. Only if something needs attention today. Reference specific positions and theses.

RULES:
- Under 300 words, no fluff
- Always name specific tickers when discussing impact (not "your AI stocks" — say "NVDA, NBIS, GLW")
- Reference kill switches if any are close to triggering
- If nothing notable, say "Quiet morning. No action needed."
```

---

## Skill 5: Weekly Summary (Scheduled)

### Schedule

Every Saturday at 07:00 CET (Europe/Zagreb timezone).

### Data Assembly

```python
def assemble_weekly_summary():
    data = {}

    # 1. Weekly performance of ALL watchlist tickers (Mon close → Fri close)
    data["performance"] = get_weekly_performance(watchlist)
    # Returns: ticker, theme, week_open, week_close, weekly_change_pct, volume_vs_avg

    # 2. Key macro events that happened this week
    data["macro_events"] = get_scored_news(
        since_days=6,  # Sat morning looking back at Mon-Fri
        min_score=6,
        categories=["macro_rates", "geopolitics", "market_regime"],
        limit=10,
    )

    # 3. Portfolio-specific news this week
    data["portfolio_news"] = get_scored_news(
        since_days=6,
        min_score=5,
        has_affected_tickers=True,
        limit=15,
    )

    # 4. Next week's calendar
    data["next_week"] = {
        "earnings": get_upcoming_earnings(watchlist, days_ahead=7),
        "fed_events": get_fed_calendar_next_week(),
        "econ_data": get_economic_calendar_next_week(),
    }

    # 5. Theses + current prices for drift detection
    data["theses"] = load_theses()  # from config/theses.yaml
    data["current_prices"] = get_watchlist_snapshot()

    # 6. S&P 500 benchmark performance for comparison
    data["benchmark"] = get_weekly_performance(["^GSPC"])

    return data
```

### LLM Prompt: `prompts/weekly_summary.txt`

```
You are a personal portfolio analyst. Generate a Saturday morning weekly summary.

DATA:
{assembled_data_json}

INVESTMENT THESES (from config/theses.yaml):
{theses_yaml}

PORTFOLIO STRUCTURE:
AI Infra (46.8%): NVDA, NBIS, AMZN, GOOG, GLW, MRVL
China/EM (11.0%): BABA, 2689.HK
Crypto (17.8%): BMNR, HOOD, ORBS
Brazil (8.4%): PBR, VALE
Vol/Options (6.1%): FLOW.AS
Satellites: OPEN, SKYX

FORMAT:
📊 **Weekly Summary** — Week of {date_range}
━━━━━━━━━━━━━━━━━━━

📈 **Performance by Theme**
S&P 500 (benchmark): {weekly_%}

🟢 AI Infra: best/worst performer, theme avg
🟡 China/EM: summary
🟣 Crypto: summary
🔵 Brazil: summary
(Flag any ticker moving >5% with details)

📰 **Key Events This Week**
• Event — impact on specific holdings (2-3 most important only)

⚠️ **Thesis Check**
For EACH ticker with a defined thesis, evaluate:
- ✅ Thesis intact — no conflicting data
- ⚠️ Monitor — new data creates uncertainty (explain in 1 sentence)
- ❌ Thesis weakening — data contradicts thesis (explain + suggest action)
Also check kill switches — flag if any are closer to triggering.

Special attention:
- BABA: any US-China developments affecting delisting risk?
- BMNR: MAVAN staking status update?
- NVDA: any hyperscaler capex signals or custom ASIC progress?
- 2689.HK: still above HKD 6.00 kill switch?

🔮 **Next Week Preview**
• Earnings: {tickers with dates}
• Macro: {events}
• Key dates: {dates}

💡 **Positioning Thoughts**
2-3 sentences. Be specific about which positions to watch or adjust.
Reference the stance (HOLD/ACCUMULATE/TRIM) from theses when suggesting actions.

RULES:
- Under 500 words (more space than morning brief — it's the weekend deep-think)
- Be specific — reference numbers, dates, percentages, cost bases
- Thesis drift is the most valuable section. Be brutally honest.
- Compare portfolio performance to S&P 500 benchmark
- If a kill switch is close to triggering, lead with it
```

---

## Skill 6: On-Demand Research via Telegram

### Commands

| Command | Behavior |
|---------|----------|
| `Research PLTR` | Bull/bear case, key metrics, risks, catalysts |
| `Any news on semiconductors?` | Filtered summary from news_store.db |
| `What's happening with Taiwan?` | Geopolitical context from recent news |
| `Deep dive NVDA` | Extended analysis: technicals, fundamentals, sentiment, thesis check |

### Command Routing

```python
def route_research_command(message: str):
    """Route Telegram messages to appropriate research handler."""

    # Pattern: "Research <TICKER>"
    if match := re.match(r"(?i)research\s+(\w+)", message):
        return research_ticker(match.group(1))

    # Pattern: "Deep dive <TICKER>"
    if match := re.match(r"(?i)deep\s+dive\s+(\w+)", message):
        return deep_dive_ticker(match.group(1))

    # Pattern: "Any news on <topic>?"
    if match := re.match(r"(?i)any\s+news\s+on\s+(.+?)\??", message):
        return filtered_news_summary(match.group(1))

    # Pattern: "What's happening with <topic>?"
    if match := re.match(r"(?i)what'?s\s+happening\s+with\s+(.+?)\??", message):
        return topic_context(match.group(1))

    # Fallback: send to LLM with portfolio context for free-form question
    return freeform_research(message)
```

### LLM Prompt: `prompts/research_bull_bear.txt`

```
You are a senior equity research analyst. The user wants a research brief on {ticker}.

AVAILABLE DATA:
Market data: {yfinance_data}
Seeking Alpha analysis: {sa_data}  # from paid API — quant rating, factor grades, estimates
Recent news (from database): {recent_news_about_ticker}
User's current thesis (if held): {thesis_or_none}
User's kill switch (if held): {kill_switch_or_none}
User's stance (if held): {stance_or_none}

USER'S FULL PORTFOLIO (for correlation/overlap analysis):
AI Infra (46.8%): NVDA, NBIS, AMZN, GOOG, GLW, MRVL
China/EM (11.0%): BABA, 2689.HK
Crypto (17.8%): BMNR, HOOD, ORBS
Brazil (8.4%): PBR, VALE
Vol/Options (6.1%): FLOW.AS
Satellites: OPEN, SKYX

GENERATE A RESEARCH BRIEF IN THIS FORMAT:

🔍 **Research: {ticker}** — {company_name}
━━━━━━━━━━━━━━━━━━━

📊 **Snapshot**
Price: $ | P/E: | Market Cap: | 52W: $low — $high
SA Quant Rating: {rating} | Factor Grades: {grades}

🐂 **Bull Case**
1. ...
2. ...
3. ...

🐻 **Bear Case**
1. ...
2. ...
3. ...

⚡ **Catalysts (Next 3 Months)**
• ...

⚠️ **Key Risks**
• ...

📐 **Valuation Quick Take**
2-3 sentences on whether current price is reasonable vs fundamentals.

{If user holds this ticker:}
🎯 **Thesis Alignment**
Does the current data support their thesis? Direct assessment.
Kill switch status: is it getting closer or further away?
Stance check: should the current stance (HOLD/ACCUMULATE/TRIM) change?

{If user does NOT hold this ticker:}
🔗 **Portfolio Fit**
How would this fit with the existing portfolio? Overlap with current positions?
Does it add diversification or concentration risk?

RULES:
- Be opinionated but balanced
- Use specific numbers, not vague claims
- If data is insufficient, say so rather than speculating
- Keep under 500 words
- Leverage Seeking Alpha quant data when available
```

---

## Telegram Command Reference (Full)

```
COMMANDS:
━━━━━━━━━━━━━━━━━━━

📊 MARKET DATA
  <TICKER>           → price, change, P/E, market cap + news one-liner
  watchlist           → all 16 positions grouped by theme
  portfolio           → full view: weights, P&L, cost bases
  <TICKER> vs <TICK>  → side-by-side comparison

📰 NEWS
  news                → top 5 recent scored articles
  news <topic>        → filtered by topic/keyword group
  alerts              → recent high-score alerts
  kills               → kill switch status for all positions

🔍 RESEARCH
  Research <TICKER>   → bull/bear case (uses SA Premium API)
  Deep dive <TICKER>  → extended analysis with SA quant ratings
  Any news on <X>?    → filtered news summary
  What's happening with <X>? → context

📅 CALENDAR
  earnings            → upcoming earnings for watchlist
  calendar            → next week events

⚙️ CONFIG
  status              → system health check
  add <TICKER>        → add to watchlist (also updates portfolio.yaml)
  remove <TICKER>     → remove from watchlist
  set thesis <TICKER>: <text> → update investment thesis
  set kill <TICKER>: <text>   → update kill switch
  reload              → reload config files without restart
```

---

## Dependencies

```
# Python packages (pip)
yfinance          # stock data
feedparser        # RSS parsing
python-telegram-bot  # Telegram integration
pyyaml            # config parsing
aiohttp           # async HTTP for X/RSS bridges
sqlite3           # built-in, no install
difflib           # built-in, fuzzy matching for dedup
schedule          # lightweight task scheduling
requests          # HTTP for Seeking Alpha API

# Seeking Alpha Premium API
# Auth: user's paid subscription credentials
# Endpoints: /symbols/{ticker}/ratings, /symbols/{ticker}/estimates,
#            /symbols/{ticker}/factor-grades, /articles (filtered)
# Rate limits: respect SA API limits, cache results 1-hour TTL

# Already available in sandbox
nvidia-nim client  # Nemotron inference
```

---

## Implementation Priority

```
Phase 2a (foundation):
  1. core/stock_data.py        — yfinance wrapper
  2. core/news_fetcher.py      — RSS aggregation
  3. core/news_scorer.py       — LLM scoring pipeline
  4. core/news_store.py        — SQLite storage
  5. core/telegram_bot.py      — command router

Phase 2b (skills):
  6. skill_stock_price.py      — Skill 1 (depends on: stock_data)
  7. skill_news_monitor.py     — Skill 2 (depends on: news_fetcher, scorer, store)
  8. skill_morning_brief.py    — Skill 4 (depends on: all core)
  9. skill_earnings.py         — Skill 3 (depends on: stock_data)
  10. skill_weekly_summary.py  — Skill 5 (depends on: all core + theses config)
  11. skill_research.py        — Skill 6 (depends on: all core)

Phase 2c (polish):
  12. X/fintwit RSS bridge setup
  13. Scheduling & persistence testing
  14. Deduplication tuning
  15. Prompt iteration based on output quality
```

---

## Notes & Open Items

1. **X/Fintwit RSS bridge**: Test which bridge works reliably from your network. Options:
   - `nitter.net` instances (check uptime at https://status.d420.de/)
   - `rss.app` (free tier: 5 feeds)
   - `rsshub.app` (self-hostable, covers Twitter)
   - Your own curated Twitter list → export via bridge

2. **ZeroHedge trust level**: Included but flagged as `editorial` in config. Scoring prompt caps its score at 7 unless corroborated by a Tier 1 source.

3. **Ticker resolution for yfinance**: Some tickers need exchange suffixes:
   - `2689.HK` (Nine Dragons Paper on HKEX)
   - `FLOW.AS` (Flow Traders on Amsterdam)
   - `OGZD.L` would be Gazprom but it's frozen/excluded
   - US tickers (NVDA, AMZN, etc.) work as-is
   - Test all tickers before going live

4. **Pre-market data reliability**: yfinance pre-market can be spotty. Futures (ES=F, NQ=F) are more reliable for morning brief sentiment.

5. **Theses populated**: All 16 active positions now have theses, kill switches, and stances from the Claude portfolio project. Update via `set thesis` command or edit `config/theses.yaml` directly.

6. **Rate limiting**: yfinance can throttle heavy usage with 17 tickers. Implement caching:
   - 5-min TTL for price quotes
   - 1-hour TTL for fundamentals
   - 1-hour TTL for Seeking Alpha API calls

7. **Seeking Alpha API**: Requires auth setup with your paid subscription credentials. Store in env vars, not in config files.

8. **Watchlist is config-driven**: Add/remove positions by editing `config/portfolio.yaml` or using Telegram `add`/`remove` commands. The `reload` command hot-reloads config without restarting the agent.

9. **OGZD (Gazprom)**: Deliberately excluded from all monitoring. Sanctioned/frozen. Listed as comment in portfolio.yaml for completeness only.
