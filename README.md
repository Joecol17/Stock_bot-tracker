# Stock Bot Tracker — Mission Control Dashboard

An AI-powered automated trading system with a real-time web dashboard ("Mission Control").
The bot uses a local Ollama LLM for BUY/SELL/HOLD decisions, Trading 212 for order execution,
and yfinance + ta for live market data and technical indicators.

---

## Current State (as of 2026-05-16)

### What is fully built and working

| Area | Status | Notes |
|------|--------|-------|
| Web dashboard (Flask) | ✅ Working | `python dashboard.py` → http://localhost:5000 |
| Mission Control UI (React) | ✅ Working | Overview, Data Sources, Trades pages all live |
| AI Engine setup page | ✅ Working | Model picker from Ollama, temperature/tokens sliders, saves to .env |
| Broker setup page | ✅ Working | API key input, demo/live toggle, account stats, test connection |
| Risk & Config setup page | ✅ Working | All trading parameters with sliders, saves to .env |
| Bot pipeline display | ✅ Working | Shows real step (from bot_state.json), idle state shows all steps clearly |
| Live BotData bridge | ✅ Working | Polls /api/botdata every 30s, fires `botdatarefreshed` event |
| start_bot.bat | ✅ Working | Single launcher: checks Python, installs deps, starts Ollama, opens dashboard |
| Auto trader bot | ✅ Working | Writes bot_state.json at each step for real-time pipeline display |
| Ollama integration | ✅ Working | Uses `llama3.2:latest` (configured in .env) |
| yfinance + ta indicators | ✅ Working | RSI, MACD, SMA, Bollinger Bands, volume, support/resistance |
| Discord notifications | ✅ Working | 5 webhooks: trades, risk, portfolio, discovery, alerts |
| Watchlist + screener | ✅ Working | Auto-discovery, top-N scoring, SL/TP tracking |
| Trade history logging | ✅ Working | `trade_history.json` persists all non-HOLD trades |

### Known issue — CRITICAL (must fix first)

**Trading 212 API → 401 Unauthorized on every call.**

Every BUY/SELL attempt fails with:
```
API request failed: 401 Client Error: Unauthorized for url: https://demo.trading212.com/api/v0/equity/account/cash
```

**Cause:** The API key in `.env` (`TRADING212_API_KEY`) is either:
- A Live account key being used with `TRADING212_DEMO_MODE=true` (hits the demo endpoint)
- Expired or revoked

**Fix:**
1. Open Trading 212 app → switch to **Demo/Practice account**
2. Settings → API → generate/copy the **Demo account API key**
3. Go to dashboard → Broker page (sidebar key 5) → paste new key → Save
4. Or edit `.env` directly: `TRADING212_API_KEY=<new key>`
5. Restart `start_bot.bat`

Note: Trading 212 has separate API keys for Demo and Live accounts. Do not mix them.

---

## How to Start Everything

### Quickest way
Double-click `start_bot.bat` in the project root. It will:
1. Check Python is installed
2. `pip install -r requirements.txt`
3. Load `.env` variables
4. Start Ollama (if `ollama.exe` is on PATH)
5. Open the dashboard in a new window and launch the browser
6. Run `auto_trader.py` in the foreground

### Manual start
```powershell
# Terminal 1 — dashboard
python dashboard.py
# Then open http://localhost:5000

# Terminal 2 — bot
python auto_trader.py
```

---

## Project File Map

```
Stock_bot-tracker/
│
├── start_bot.bat              ← MAIN LAUNCHER — double-click to start everything
│
├── .env                       ← ALL configuration (API keys, model, risk params)
│                                  DO NOT commit real keys to git
│
├── auto_trader.py             ← The trading bot loop
│                                  Writes bot_state.json at every pipeline step
│                                  Reads Config → calls TradingSystem → logs results
│
├── dashboard.py               ← Flask web server (port 5000)
│                                  Serves the React UI from /static/
│                                  API routes: /api/botdata, /api/config,
│                                              /api/status, /api/trades,
│                                              /api/watchlist, /api/orders,
│                                              /api/ollama/models
│
├── trading_system.py          ← Main orchestrator class TradingSystem
│                                  Connects DecisionEngine + Trading212Client + OrderExecutor
│
├── trading212_client.py       ← Trading 212 REST API client
│                                  Supports demo (demo.trading212.com) and live
│                                  Uses Authorization header (no Bearer prefix)
│
├── order_executor.py          ← Translates AI decisions into T212 orders
│                                  Maintains in-memory SL/TP tracking per position
│                                  Writes to trade_history.json
│
├── decision_system.py         ← Ollama LLM wrapper
│                                  Sends market context as JSON prompt
│                                  Parses BUY/SELL/HOLD + confidence from response
│
├── watchlist.py               ← WatchlistManager (watchlist.json) + Screener
│                                  Screener scores symbols by volume/momentum
│
├── discovery.py               ← Auto-discovers new watchlist candidates
│                                  Uses predefined universe + yfinance screening
│                                  Removed delisted: PARA, PXD, SQ
│
├── config.py                  ← All config as class attributes, loaded from .env
│
├── notifier.py                ← Discord webhook notifications
│                                  Channels: trades, risk, portfolio, discovery, alerts
│
├── requirements.txt           ← Python dependencies
│
├── templates/
│   └── dashboard.html         ← Single HTML shell; loads React from CDN + JSX files
│
├── static/
│   ├── styles.css             ← Full design system (oklch colors, IBM Plex + Space Grotesk)
│   ├── live_data.js           ← Polls /api/botdata every 30s → window.BotData
│   │                             Fires 'botdatarefreshed' custom event on each update
│   ├── app.jsx                ← App shell: sidebar, topbar, page router
│   │                             Keyboard shortcuts: 1=Overview 2=Sources 3=Trades
│   │                                                 4=AI Engine 5=Broker 6=Risk
│   │                                                 7=Predictions 8=Logs 9=Watchlist
│   ├── overview.jsx           ← Overview page: KPIs, pipeline, equity chart, risk
│   ├── sources.jsx            ← Data sources page: world map, latency, sample packet
│   ├── trades.jsx             ← Trades page: positions table, decisions list
│   ├── ai-engine.jsx          ← Setup: Ollama model picker, temperature, max tokens
│   ├── broker.jsx             ← Setup: API key, demo/live toggle, account stats
│   ├── risk-config.jsx        ← Setup: position sizing, ATR stops, filters, discovery
│   ├── predictions.jsx        ← Insight: day/month/year profit forecast from equity history
│   ├── viz.jsx                ← Reusable charts: Sparkline, AreaChart, StackedBars, Donut
│   ├── icons.jsx              ← SVG icon components (I.Dashboard, I.Globe, etc.)
│   └── tweaks-panel.jsx       ← Tweaks drawer: accent colour, density, activity toggle
│
├── watchlist.json             ← Persisted watchlist symbols
├── trade_history.json         ← Persisted trade records (created on first trade)
├── bot_state.json             ← Written by auto_trader.py each pipeline step (runtime only)
└── trading_bot.log            ← Bot log file (created on first run)
```

---

## Codebase map — grouped by job

The code splits into clear layers. Top to bottom is roughly **decide → trade → show**.

**⚙️ Configuration & entry points**
- `config.py` — every tunable in one place (risk, stops, filters, schedule, focus period, Ollama, broker), each read from `.env` with a sane default.
- `.env` — your private keys + settings (git-ignored); `.env.example` is the documented template to copy from.
- `requirements.txt` — Python dependencies.
- `auto_trader.py` — **the bot**: the continuous loop that drives everything below (detailed under *orchestration*).
- `interactive.py` — a manual CLI menu (analyse a stock, view the account, run a backtest) for hands-on use.
- `main.py` — a one-shot demo of the decide→execute path against a hard-coded sample context.

**🧠 The decision brain (what to do)**
- `decision_system.py` — talks to local Ollama (`OllamaClient`) and turns a market-context dict into a structured BUY/SELL/HOLD with stop, target, confidence and setup type (`DecisionEngine`). Robustly extracts JSON from the model's reply (handles code fences / pretty-printed / embedded objects).
- `swing_filters.py` — four pre-trade quality gates that run *before* the LLM: market regime (SPY vs its SMAs), earnings-date avoidance, relative strength vs SPY, and a 0–100 technical setup score. A symbol must clear `MIN_FILTER_SCORE` to be analysed at all.

**🔎 What to look at (data & screening)**
- `watchlist.py` — `WatchlistManager` (the symbol list, persisted to `watchlist.json`) and `Screener` (cheap 5-day activity scoring to pick the top N symbols each cycle).
- `discovery.py` — periodically scans a ~150-stock universe and auto-adds the most active fresh names to the watchlist.
- `get_market_context()` (in `auto_trader.py`) — pulls 1y of daily bars for one symbol and computes RSI / MACD / SMA20-50-200 / ATR / Bollinger plus ATR-based suggested stop & target.
- `equity_tracker.py` — records one equity snapshot per day and computes the day/month/year profit projections shown on the Predictions page.

**💸 Making & managing trades (execution)**
- `trading_system.py` — the façade that wires the brain to the broker: `analyze_and_trade()`, `check_risk_exits()`, account status.
- `order_executor.py` — the workhorse: risk-based **fractional** position sizing (capped by `MAX_POSITION_PCT` and free cash), stop/target placement, market buys/sells, and exit management (hard stop, take-profit, and a trailing stop with a **breakeven floor**). Persists open positions to `tracked_positions.json` and every fill to `trade_history.json`.
- `trading212_client.py` — the raw Trading 212 REST client: auth, account/cash, positions, orders, ticker resolution (`AAPL` → `AAPL_US_EQ`), and market/limit/stop order placement.

**🔁 The bot itself (orchestration)**
- `auto_trader.py` — the live loop. Honours the trading schedule + market-open "focus period", and each cycle: checks risk exits → (occasionally) runs discovery → reads the regime → screens the watchlist → analyses each symbol through filters + LLM + executor → records equity → writes state for the dashboard. `config.py` holds every tunable (read from `.env`).

**🔔 Notifications**
- `notifier.py` — fans out Discord webhooks per channel: trades, risk exits, cycle summaries, discovery, errors, bot start/stop.

**🖥️ Local dashboard (web UI)**
- `dashboard.py` — Flask app serving the UI and the JSON API (`/api/botdata`, `/api/config`, `/api/trades`, watchlist, bot pause/run-cycle, PC power, logs).
- `templates/dashboard.html` + `static/live_data.js` — the HTML shell and the live-data bridge (`window.BotData`, polled every 30s).
- `static/app.jsx` — the app shell: sidebar, top bar, page router, pause / run-cycle buttons, and remote PC-power controls.
- Pages (sidebar shortcut key in brackets):
  - `overview.jsx` **[1]** — KPIs, the live decision pipeline, equity chart, market regime, and risk / swing stats.
  - `sources.jsx` **[2]** — a world-map view of the data sources (broker / market / AI) with live latency.
  - `trades.jsx` **[3]** — open positions table and the recent BUY/SELL/HOLD decision feed.
  - `ai-engine.jsx` **[4]** — Ollama model picker, temperature, max-tokens, and a prompt preview.
  - `broker.jsx` **[5]** — Trading 212 API key (masked), demo/live toggle, account stats, and a "test connection" button.
  - `risk-config.jsx` **[6]** — position sizing, ATR/% stops, pre-trade filters, and screener/discovery settings (writes `.env`).
  - `predictions.jsx` **[7]** — day/month/year profit forecast, equity history chart, confidence, and 1-year outlook.
  - `logs.jsx` **[8]** — a live tail of `trading_bot.log`.
  - `watchlist.jsx` **[9]** — watchlist symbols, each one's per-cycle status, and on-demand AI analysis.
- Shared UI: `viz.jsx` (chart primitives — Sparkline / AreaChart / StackedBars / Donut), `icons.jsx` (SVG icons), `tweaks-panel.jsx` (accent/density drawer), `styles.css` (the design system).

**🌍 Remote access (from your phone)**
- `docs/index.html` + `docs/config.js` — GitHub Pages gateway: signs in, wakes the PC if it's asleep, then forwards to the full dashboard over the tunnel.
- `tunnel_helper.py` — opens the public tunnel (Cloudflare / ngrok) and writes `tunnel_url.txt`.
- `wol_relay/` — a tiny Flask service hosted on Render that sends the Wake-on-LAN magic packet to the PC.
- `headless_launcher.py` — boots the whole stack silently (tunnel + dashboard + bot) for Windows Task Scheduler.
- `start_bot.bat` — interactive one-click launcher · `setup_remote.bat` / `setup_ngrok.bat` / `setup_named_tunnel.bat` — one-time remote-access setup · `boot_notify.ps1` — sends a "PC is up" notice on boot · `tunnel_config.yml.example` — template for a permanent Cloudflare named tunnel.

**🧪 Offline testing & manual use**
- `backtest.py` — replays historical daily data through the same decision logic (AI or fast rule mode) without touching the broker.
- `interactive.py` — a manual CLI to analyse a stock, view the account, or run a backtest. `main.py` is a one-shot demo of the decide→execute path.

### How one cycle flows
```
schedule / focus gate → check_risk_exits  (sell anything that hit SL / TP / trailing stop)
  → (every N cycles) discovery → market regime → screen watchlist to top-N
  → for each symbol:  market context → swing filters → [pass?] → Ollama decision
       → risk-sized order via Trading 212 → register stop/target tracking
  → record equity snapshot → Discord cycle summary → sleep to next slot
```
The dashboard reads everything from JSON the bot writes (`bot_state.json`, `trade_history.json`,
`tracked_positions.json`, `symbol_queue.json`, `equity_history.json`) plus live Trading 212 / Ollama calls.

### 🗂️ Runtime state files (created as the bot runs — git-ignored)
- `watchlist.json` — your tracked symbols · `universe.json` — cached discovery universe
- `trade_history.json` — every fill and exit · `tracked_positions.json` — open positions + their stop / target / trailing state
- `bot_state.json` — current pipeline step & status (the dashboard reads it) · `bot_control.json` — pause / run-cycle flags (dashboard writes, bot reads)
- `symbol_queue.json` — per-symbol status for the current cycle · `symbol_prefs.json` — per-symbol enable/disable from the dashboard
- `equity_history.json` — one equity row per day (powers Predictions) · `tunnel_url.txt` — the current public URL
- `trading_bot.log` / `launcher.log` — run logs

### 📄 Docs
`README.md` (this file) · `QUICK_START.md` · `SETUP.md` · `REMOTE_SETUP.md` · `setup_guide.html` (a styled in-browser setup walkthrough).

---

## .env Configuration Reference

```env
# ── Trading 212 ──────────────────────────────────────────
TRADING212_API_KEY=<your key>          # Demo key → demo.trading212.com
                                        # Live key → live.trading212.com
TRADING212_DEMO_MODE=true              # true=demo account, false=live (real money!)

# ── Ollama ───────────────────────────────────────────────
OLLAMA_MODEL=llama3.2:latest           # Must match `ollama list` output exactly
OLLAMA_TEMPERATURE=0.2                 # 0.0–1.0 (lower = more consistent)
OLLAMA_MAX_TOKENS=256                  # Max tokens in LLM response

# ── Risk management ──────────────────────────────────────
STOP_LOSS_PCT=0.06                     # Fallback stop if no ATR level (6% below entry)
TAKE_PROFIT_PCT=0.12                   # Fallback target if trailing stop inactive (12%)
MAX_DAILY_TRADES=0                     # 0 = unlimited (default); risk sizing + stops cap exposure
MIN_ACCOUNT_VALUE=100                  # Bot halts if account drops below this
DEFAULT_TRADE_QUANTITY=1               # Fallback shares per order (risk sizing computes the real qty)

# ── Screener & discovery ─────────────────────────────────
MAX_SYMBOLS_PER_CYCLE=5                # Symbols analysed per bot cycle
DISCOVERY_INTERVAL_CYCLES=6           # Run discovery every N cycles
DISCOVERY_TOP_N=10                     # Max new symbols added per discovery
MAX_WATCHLIST_SIZE=20                  # Watchlist capped at this size

# ── Discord webhooks ─────────────────────────────────────
DISCORD_WEBHOOK_TRADES=https://...     # #trades channel
DISCORD_WEBHOOK_RISK=https://...       # #risk-exits channel
DISCORD_WEBHOOK_PORTFOLIO=https://...  # #portfolio channel
DISCORD_WEBHOOK_DISCOVERY=https://...  # #discovery channel
DISCORD_WEBHOOK_ALERTS=https://...     # #alerts channel
```

---

## Dashboard UI Architecture

The UI is React 18 + Babel CDN — **no build step**. All JSX is compiled in-browser.

### Key pattern: window.BotData

`live_data.js` initialises `window.BotData` with defaults and polls `/api/botdata` every 30 seconds.
After each poll it fires a `botdatarefreshed` custom event. Every page component subscribes to that event and re-renders.

```
/api/botdata (Flask)
    reads: bot_state.json, trade_history.json, Trading212 API
    returns: positions, decisions, orders, equity curve, bot status,
             cycle#, step#, step_name, current_symbol, uptime_seconds,
             model, temperature, mode, cash, free_funds, total_value
        ↓
live_data.js
    Object.assign(window.BotData, response)
    window.dispatchEvent(new CustomEvent('botdatarefreshed'))
        ↓
React components
    read window.BotData directly (no props/state for live data)
    re-render on 'botdatarefreshed' event
```

### Critical Babel rule

Each `<script type="text/babel">` runs in its own local scope.
Any component defined in a JSX file **must** be assigned to `window` to be accessible from other files:
```javascript
// At the bottom of each JSX file:
window.OverviewPage = OverviewPage;
window.AiEnginePage = AiEnginePage;
// etc.
```
Forgetting this causes a silent "Element type is invalid: undefined" crash → blank black page.

### Bot pipeline state (bot_state.json)

`auto_trader.py` calls `_write_state(step, step_name, symbol)` at each pipeline stage:

| step | step_name | when |
|------|-----------|------|
| 0 | idle | before/after each cycle |
| 1 | Risk exits | checking SL/TP positions |
| 2 | Screener | ranking watchlist symbols |
| 3 | Fetch context | downloading yfinance data for a symbol |
| 4 | Ollama decide | waiting for LLM response |
| 5 | Execute order | placing the T212 order |

The Overview pipeline track reads `D.step` and `D.bot_status` from `window.BotData`
and colours nodes: done=green checkmark, active=amber pulse, ready=neutral grey (idle).

---

## Bot Decision Flow

```
Every 300s (configurable):
│
├─ Step 1: Risk exits
│   Check all tracked positions against SL/TP levels
│   Execute market SELL for any that triggered
│
├─ Every 6 cycles: Discovery
│   Screen 500-stock universe for momentum/volume
│   Auto-add top candidates to watchlist (capped at MAX_WATCHLIST_SIZE)
│
├─ Step 2: Screener
│   Score all watchlist symbols by recent volume + price change
│   Pick top MAX_SYMBOLS_PER_CYCLE for this cycle
│
├─ For each symbol:
│   ├─ Step 3: Fetch context
│   │   yfinance: 60d/1h OHLCV data
│   │   ta library: RSI14, MACD, SMA20/50, Bollinger Bands
│   │   Derived: trend, volume label, support/resistance, bb_position
│   │
│   ├─ Step 4: Ollama decide
│   │   Sends JSON context to local Ollama model
│   │   Expects response: {"action":"BUY|SELL|HOLD","confidence":0-1,"reason":"...","quantity":N}
│   │   Falls back to raw text scan if JSON parse fails
│   │
│   └─ Step 5: Execute order
│       BUY → check free_funds > 0 → place market order → register SL/TP tracking
│       SELL → check position exists → place market order
│       HOLD → log only, no order
│
└─ Step 0: back to idle, sleep 300s
```

---

## Setup / Config & Insight pages (sidebar keys 4–7)

All three pages read `.env` via `GET /api/config` on mount and write via `POST /api/config`.
Changes take effect after restarting the bot (`.env` is loaded at startup).

- **AI Engine (4)**: Model dropdown (populated from `GET /api/ollama/models` → Ollama local API),
  temperature slider 0–1, max tokens slider 64–1024, prompt preview.
- **Broker (5)**: API key input (masked), demo/live toggle with live-mode warning,
  account stats from live BotData, "Test connection" button hits `/api/status`.
- **Risk & Config (6)**: Position sizing (risk per trade, ATR stop ×, min R:R, max position %,
  max hold days), pre-trade filters (filter score, earnings buffer, relative strength, regime
  benchmark, bear-market policy), fallback SL/TP %, min account value, and screener/discovery.
- **Predictions (7)**: Day / month / year profit forecast — a linear fit of the recorded daily
  equity curve (`equity_tracker.py`), with confidence, trend stats, and a 1-year outlook.

---

## Troubleshooting

### Trades all blocked / 401 Unauthorized
→ See "Known issue" section at the top. API key mismatch between demo/live.

### Setup pages show blank black screen
→ Each JSX file must export its component to `window` (e.g. `window.AiEnginePage = AiEnginePage`).
  Check browser console for "Element type is invalid: undefined".

### Pipeline shows nothing / all steps look the same
→ Bot not started = "ready" state (neutral grey dots, all labels visible).
  Start the bot via `start_bot.bat` to see the pipeline animate.

### Ollama 404 on every symbol
→ Model name in `.env` doesn't match what's installed.
  Run `ollama list` and set `OLLAMA_MODEL=<exact name from list>`.
  Currently installed: `llama3.2:latest`, `0xroyce/plutus:latest`.

### UnicodeEncodeError on Windows console
→ A `→` character in a log message can't be encoded by Windows cp1252.
  Already fixed in `watchlist.py` (changed to `->`).

### Delisted symbol errors (yfinance 404)
→ `PARA`, `PXD`, `SQ` removed from `BUILTIN_UNIVERSE` in `discovery.py`.

### Dashboard port in use
→ Set `DASHBOARD_PORT=5001` in `.env` (or any free port).

---

## Pending / Future Work

- [ ] **Fix 401 API key** (blocker for all trading)
- [ ] Wire "Pause" and "Run cycle" buttons in the topbar to actual Flask endpoints
- [ ] Add real-time log streaming to the dashboard (tail `trading_bot.log`)
- [ ] Backtesting page (infrastructure exists in `backtest.py`)
- [ ] Confidence scores from Ollama are always 0.0 (LLM returns them but they aren't plumbed through to the dashboard decisions)
- [ ] The `price` field in `trade_history.json` records are often 0 (the executor doesn't record fill price, only context price)
- [ ] Consider adding an error boundary in React so a broken page component doesn't crash the whole app
- [ ] Push config changes in the Setup pages live to the running bot (currently requires restart)

---

## Dependencies

```
flask          — web dashboard server
requests       — Trading 212 API HTTP calls
yfinance       — market data
ta             — technical analysis indicators (RSI, MACD, Bollinger, SMA)
python-dotenv  — .env file loading
ollama         — Ollama Python client (optional; HTTP calls also work directly)
```

React 18, Babel standalone, and fonts are loaded from CDN in `dashboard.html` — no npm needed.

---

## Disclaimer

Educational/experimental project. Always use Demo mode first.
AI trading decisions can be wrong. Never risk money you cannot afford to lose.
