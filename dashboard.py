"""
Web dashboard for the Stock Bot Tracker.

Run with:  python dashboard.py
Then open: http://localhost:5000
"""

import json
import os
from collections import deque
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from config import Config
from watchlist import WatchlistManager
from swing_filters import get_market_regime
from equity_tracker import compute_projections

# ---------------------------------------------------------------------------
# Bot control file (pause / run-cycle-now flags read by auto_trader.py)
# ---------------------------------------------------------------------------

_CONTROL_FILE = "bot_control.json"


def _read_bot_control() -> Dict[str, Any]:
    try:
        with open(_CONTROL_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"paused": False, "run_cycle_now": False}


def _write_bot_control(data: Dict[str, Any]) -> None:
    try:
        with open(_CONTROL_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

app = Flask(__name__)

# Allow the GitHub Pages remote dashboard (and any other origin) to call /api/*
CORS(app, resources={r"/api/*": {"origins": "*"}})


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------

def _is_local_request() -> bool:
    """True when the HTTP request originates from this machine."""
    return request.remote_addr in ("127.0.0.1", "::1")


def _auth_configured() -> bool:
    """True when the operator has set credentials in .env."""
    return bool(os.getenv("DASHBOARD_USERNAME", "").strip())


def _check_auth() -> bool:
    """Return True if the request is authorised to call a protected endpoint."""
    # Requests from localhost are always trusted (local dashboard on port 5000)
    if _is_local_request():
        return True
    # No credentials configured → open access (local/trusted-network use)
    secret = os.getenv("DASHBOARD_SECRET", "").strip()
    if not secret:
        return True
    # Accept token from three places so both JS fetch() and curl work easily
    if request.headers.get("X-Auth-Token", "") == secret:
        return True
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth[7:] == secret:
        return True
    try:
        body = request.get_json(silent=True) or {}
        if body.get("token", "") == secret:
            return True
    except Exception:
        pass
    return False


@app.before_request
def require_auth_on_api():
    """Guard every /api/* route except the login endpoint and CORS preflight."""
    if request.method == "OPTIONS":
        return  # flask-cors handles preflight
    if not request.path.startswith("/api/"):
        return  # static page routes are fine
    if request.path == "/api/auth/login":
        return  # the login endpoint itself must be reachable
    if not _check_auth():
        return jsonify({"error": "Unauthorized", "login_required": True}), 401


# Lazy-initialised — app starts even without an API key
_system = None


def _get_system():
    global _system
    if _system is None and Config.TRADING212_API_KEY:
        from trading_system import TradingSystem
        _system = TradingSystem(
            api_key=Config.TRADING212_API_KEY,
            api_secret=Config.TRADING212_API_SECRET,
            is_demo=Config.TRADING212_DEMO_MODE,
        )
    return _system


def _get_watchlist() -> WatchlistManager:
    return WatchlistManager(Config.WATCHLIST_FILE)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "dashboard.html",
        mode="DEMO" if Config.TRADING212_DEMO_MODE else "LIVE",
        model=Config.OLLAMA_MODEL,
    )


# ---------------------------------------------------------------------------
# API — authentication (remote dashboard login)
# ---------------------------------------------------------------------------

@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    """
    Validate username + password and return the session token.

    Required .env keys (all three must be set together):
        DASHBOARD_USERNAME=your_username
        DASHBOARD_PASSWORD=your_password
        DASHBOARD_SECRET=some-long-random-string   ← this becomes the bearer token

    If DASHBOARD_USERNAME is not set, login is not required and any request is
    accepted (open/local-network mode).
    """
    username_cfg = os.getenv("DASHBOARD_USERNAME", "").strip()
    password_cfg = os.getenv("DASHBOARD_PASSWORD", "").strip()
    secret_cfg   = os.getenv("DASHBOARD_SECRET",   "").strip()

    # Auth not configured — tell the client it can proceed without a token
    if not username_cfg:
        return jsonify({"ok": True, "auth_required": False, "token": ""})

    # Misconfigured — secret must accompany username/password
    if not secret_cfg:
        return jsonify({
            "error": "Server misconfigured: set DASHBOARD_SECRET in .env alongside DASHBOARD_USERNAME",
        }), 500

    body = request.get_json(silent=True) or {}
    if body.get("username") == username_cfg and body.get("password") == password_cfg:
        return jsonify({"ok": True, "auth_required": True, "token": secret_cfg})

    return jsonify({"error": "Invalid username or password"}), 401


@app.route("/api/auth/check", methods=["GET"])
def api_auth_check():
    """Quick endpoint the remote dashboard uses to check if a stored token is still valid."""
    return jsonify({"ok": True, "auth_required": _auth_configured()})


# ---------------------------------------------------------------------------
# API — account & positions
# ---------------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    system = _get_system()
    if not system:
        return jsonify({"error": "TRADING212_API_KEY not configured"}), 503

    try:
        account = system.get_account_status()
        tracked = system.get_tracked_positions()

        positions = account.get("positions", [])
        for pos in positions:
            symbol = pos.get("symbol", "")
            if symbol in tracked:
                t = tracked[symbol]
                pos["stop_loss"]   = t.get("stop_loss")
                pos["take_profit"] = t.get("take_profit")
                pos["entry_price"] = t.get("entry_price")

        return jsonify({
            "account_id":      account.get("account_id"),
            "mode":            "DEMO" if system.is_demo else "LIVE",
            "cash":            account.get("cash", 0),
            "portfolio_value": account.get("portfolio_value", 0),
            "free_funds":      account.get("free_funds", 0),
            # portfolio_value maps to Trading 212's "total" = full account equity
            # (free cash + holdings), so it IS the total — don't add cash again.
            "total_value":     account.get("portfolio_value", 0),
            "positions":       positions,
            "positions_count": len(positions),
            "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — trade history
# ---------------------------------------------------------------------------

@app.route("/api/trades")
def api_trades():
    history_file = "trade_history.json"
    if not os.path.exists(history_file):
        return jsonify([])
    try:
        with open(history_file, "r") as f:
            trades = json.load(f)
        # Most recent first, cap at 100
        return jsonify(list(reversed(trades))[:100])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — watchlist
# ---------------------------------------------------------------------------

@app.route("/api/watchlist")
def api_watchlist():
    wl = _get_watchlist()
    return jsonify(wl.list_symbols())


@app.route("/api/watchlist/add", methods=["POST"])
def api_watchlist_add():
    symbol = (request.json or {}).get("symbol", "").upper().strip()
    if not symbol:
        return jsonify({"error": "symbol required"}), 400
    wl = _get_watchlist()
    added = wl.add(symbol)
    return jsonify({"added": added, "symbols": wl.list_symbols()})


@app.route("/api/watchlist/remove", methods=["POST"])
def api_watchlist_remove():
    symbol = (request.json or {}).get("symbol", "").upper().strip()
    if not symbol:
        return jsonify({"error": "symbol required"}), 400
    wl = _get_watchlist()
    removed = wl.remove(symbol)
    return jsonify({"removed": removed, "symbols": wl.list_symbols()})


_QUEUE_FILE = "symbol_queue.json"
_PREFS_FILE = "symbol_prefs.json"


@app.route("/api/watchlist/queue")
def api_watchlist_queue():
    """Return the current per-symbol status written by auto_trader.py."""
    try:
        with open(_QUEUE_FILE, "r") as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"cycle": 0, "symbols": {}, "updated": ""})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist/prefs", methods=["GET"])
def api_watchlist_prefs_get():
    """Return enabled/disabled preference for every symbol."""
    try:
        with open(_PREFS_FILE, "r") as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist/prefs", methods=["POST"])
def api_watchlist_prefs_set():
    """Set enabled/disabled for one or more symbols.
    Body: { "AAPL": true, "META": false, ... }
    """
    data = request.json or {}
    try:
        try:
            with open(_PREFS_FILE, "r") as f:
                prefs = json.load(f)
        except Exception:
            prefs = {}
        for sym, enabled in data.items():
            sym = sym.upper().strip()
            if sym:
                prefs.setdefault(sym, {})["enabled"] = bool(enabled)
        with open(_PREFS_FILE, "w") as f:
            json.dump(prefs, f)
        return jsonify({"ok": True, "prefs": prefs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist/analyze", methods=["POST"])
def api_watchlist_analyze():
    """
    Fetch live market data for a symbol and ask Ollama for a BUY/SELL/HOLD
    decision with plain-English reasoning.  Returns a dict the UI can render
    directly on the watchlist card.
    """
    symbol = (request.json or {}).get("symbol", "").upper().strip()
    if not symbol:
        return jsonify({"error": "symbol required"}), 400

    result: Dict[str, Any] = {"symbol": symbol}

    # ── 1. Market data via yfinance ──────────────────────────────────────────
    try:
        import yfinance as yf
        import ta
        import numpy as np

        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period="3mo")
        info   = ticker.info or {}

        if hist.empty:
            return jsonify({"error": f"No data found for {symbol}"}), 404

        close   = hist["Close"]
        volume  = hist["Volume"]
        price   = float(close.iloc[-1])
        prev    = float(close.iloc[-2]) if len(close) > 1 else price
        chg_pct = (price - prev) / prev * 100 if prev else 0

        # RSI
        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
        rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else None

        # Relative strength vs SPY (20-day)
        try:
            spy = yf.Ticker("SPY").history(period="1mo")["Close"]
            if len(spy) >= 2 and len(close) >= 2:
                sym_ret = float(close.iloc[-1]) / float(close.iloc[-min(20, len(close))])
                spy_ret = float(spy.iloc[-1])   / float(spy.iloc[-min(20, len(spy))])
                rs = sym_ret / spy_ret if spy_ret else 1.0
            else:
                rs = 1.0
        except Exception:
            rs = 1.0

        # Volume (millions, 5-day avg)
        vol_m = float(volume.tail(5).mean()) / 1_000_000

        result.update({
            "name":       info.get("longName") or info.get("shortName") or symbol,
            "price":      round(price, 2),
            "change_pct": round(chg_pct, 2),
            "rsi":        round(rsi, 1) if rsi is not None else None,
            "rs":         round(rs, 4),
            "volume_m":   round(vol_m, 1),
        })
    except Exception as e:
        result["data_error"] = str(e)

    # ── 2. Swing filters ─────────────────────────────────────────────────────
    try:
        from swing_filters import run_all_filters, get_market_regime
        regime_data = get_market_regime()
        result["regime"] = regime_data.get("regime", "unknown")

        filters = run_all_filters(symbol)
        score   = sum(1 for v in filters.values() if v is True)
        result["filter_score"]  = score
        result["earnings_ok"]   = filters.get("earnings_ok")
        result["filters_detail"]= filters
    except Exception:
        result["regime"] = "unknown"

    # ── 3. Ollama reasoning ──────────────────────────────────────────────────
    try:
        import requests as _req

        price_str   = f"${result.get('price','N/A')}"
        chg_str     = f"{result.get('change_pct','N/A')}%"
        rsi_str     = f"{result.get('rsi','N/A')}"
        rs_str      = f"{result.get('rs','N/A')}"
        regime_str  = result.get("regime", "unknown")
        filter_str  = f"{result.get('filter_score','?')}/4"
        earnings_str= "YES" if result.get("earnings_ok") else "NO"

        prompt = (
            f"You are a swing trading analyst. Analyse {symbol} and give a clear BUY, SELL, or HOLD recommendation.\n\n"
            f"Current data:\n"
            f"- Price: {price_str}  1-day change: {chg_str}\n"
            f"- RSI(14): {rsi_str}\n"
            f"- Relative strength vs SPY (20d): {rs_str}\n"
            f"- Market regime: {regime_str}\n"
            f"- Pre-trade filter score: {filter_str} (earnings safe: {earnings_str})\n\n"
            f"Reply in this exact format (no extra text):\n"
            f"ACTION: BUY|SELL|HOLD\n"
            f"REASONING: (2-4 sentences explaining why, what to watch, and any risks)"
        )

        ollama_model = Config.OLLAMA_MODEL
        resp = _req.post(
            "http://localhost:11434/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        if resp.ok:
            raw = resp.json().get("response", "").strip()
            action    = "HOLD"
            reasoning = raw
            for line in raw.splitlines():
                if line.upper().startswith("ACTION:"):
                    a = line.split(":", 1)[-1].strip().upper()
                    if a in ("BUY", "SELL", "HOLD"):
                        action = a
                elif line.upper().startswith("REASONING:"):
                    reasoning = line.split(":", 1)[-1].strip()
            result["action"]    = action
            result["reasoning"] = reasoning
    except Exception as e:
        result["reasoning_error"] = str(e)

    return jsonify(result)


# ---------------------------------------------------------------------------
# API — combined BotData (used by the Mission Control dashboard)
# ---------------------------------------------------------------------------

@app.route("/api/botdata")
def api_botdata():
    result = {
        "positions": [],
        "decisions": [],
        "orders": [],
        "activity": [],
        "equity": [{"i": i, "v": 10000} for i in range(72)],
        "decisionHist": [{"h": h, "buy": 0, "sell": 0, "hold": 0} for h in range(24)],
        "cash": 0,
        "free_funds": 0,
        "total_value": 0,
        "mode": "DEMO" if Config.TRADING212_DEMO_MODE else "LIVE",
        "model": Config.OLLAMA_MODEL,
        # Config values for UI
        "temperature": Config.OLLAMA_TEMPERATURE,
        "max_tokens": Config.OLLAMA_MAX_TOKENS,
        "min_account_value": Config.MIN_ACCOUNT_VALUE,
        "max_daily_trades": Config.MAX_DAILY_TRADES,
        "cycle_interval": Config.BOT_CYCLE_INTERVAL,
        # Bot state (from bot_state.json written by auto_trader.py)
        "bot_status": "idle",
        "cycle": 0,
        "step": 0,
        "step_name": "idle",
        "current_symbol": "",
        "uptime_seconds": 0,
        "last_cycle_time": "",
        "avg_confidence": 0.0,
        "paused": False,
        # Schedule
        "schedule_enabled":  Config.TRADING_SCHEDULE_ENABLED,
        "in_trading_window": False,
        "next_run":          "",
        "trading_hours":     f"{Config.TRADING_START_HOUR:02d}:00–{Config.TRADING_END_HOUR:02d}:00 Mon–Fri",
        "cycles_per_hour":   Config.TRADING_CYCLES_PER_HOUR,
        # Focus period (market-open overdrive)
        "in_focus_period":   Config.in_focus_period(),
        "focus_window":      (f"{Config.FOCUS_START_HOUR:02d}:{Config.FOCUS_START_MIN:02d}–"
                              f"{Config.FOCUS_END_HOUR:02d}:{Config.FOCUS_END_MIN:02d}"),
        # Swing-trading config surfaced to the dashboard
        "risk_per_trade_pct":  Config.RISK_PER_TRADE_PCT,
        "atr_stop_multiplier": Config.ATR_STOP_MULTIPLIER,
        "min_risk_reward":     Config.MIN_RISK_REWARD,
        "max_hold_days":       Config.MAX_HOLD_DAYS,
        "earnings_buffer_days":Config.EARNINGS_BUFFER_DAYS,
        "min_filter_score":    Config.MIN_FILTER_SCORE,
        # Market regime (populated below)
        "regime": {
            "regime": "unknown",
            "benchmark": Config.MARKET_REGIME_SYMBOL,
            "price": 0, "sma50": 0, "sma200": 0,
            "above_sma50": None, "above_sma200": None,
        },
    }

    # Read bot state written by auto_trader.py
    if os.path.exists("bot_state.json"):
        try:
            with open("bot_state.json") as f:
                bs = json.load(f)
            result["bot_status"]       = bs.get("status", "idle")
            result["cycle"]            = bs.get("cycle", 0)
            result["step"]             = bs.get("step", 0)
            result["step_name"]        = bs.get("step_name", "idle")
            result["current_symbol"]   = bs.get("current_symbol", "")
            result["uptime_seconds"]   = bs.get("uptime_seconds", 0)
            result["last_cycle_time"]  = bs.get("last_updated", "")
            result["in_trading_window"]= bs.get("in_trading_window", False)
            result["next_run"]         = bs.get("next_run", "")
            result["trading_hours"]    = bs.get("trading_hours", result["trading_hours"])
            result["cycles_per_hour"]  = bs.get("cycles_per_hour", Config.TRADING_CYCLES_PER_HOUR)
        except Exception:
            pass

    # Overlay pause state from control file
    ctrl = _read_bot_control()
    result["paused"] = ctrl.get("paused", False)
    if result["paused"] and result["bot_status"] == "running":
        result["bot_status"] = "paused"

    # Market regime (cached 1 h inside swing_filters)
    try:
        result["regime"] = get_market_regime(Config.MARKET_REGIME_SYMBOL)
    except Exception:
        pass

    # Cloudflare tunnel URL (written by tunnel_helper.py)
    try:
        if os.path.exists("tunnel_url.txt"):
            with open("tunnel_url.txt") as f:
                result["tunnel_url"] = f.read().strip()
        else:
            result["tunnel_url"] = None
    except Exception:
        result["tunnel_url"] = None

    # Account status & positions
    system = _get_system()
    if system:
        try:
            account = system.get_account_status()
            tracked = system.get_tracked_positions()
            result["cash"] = account.get("cash", 0)
            result["free_funds"] = account.get("free_funds", account.get("cash", 0))

            today_str = datetime.now().strftime("%Y-%m-%d")
            for pos in account.get("positions", []):
                symbol = pos.get("symbol", "")
                t      = tracked.get(symbol, {})
                entry  = t.get("entry_price") or pos.get("avg_price", 0) or 0
                price  = pos.get("current_price", 0) or 0
                qty    = pos.get("quantity", 0) or 0
                value  = pos.get("value", price * qty) or 0
                pl     = pos.get("profit_loss", 0) or 0
                pl_pct = ((price - entry) / entry * 100) if entry else 0
                trend  = "uptrend" if pl_pct > 1 else "downtrend" if pl_pct < -1 else "neutral"
                # Days held — from entry_date recorded at buy time
                days_held = None
                entry_date_str = t.get("entry_date")
                if entry_date_str:
                    try:
                        from datetime import date
                        days_held = (date.today() - date.fromisoformat(entry_date_str)).days
                    except Exception:
                        pass
                result["positions"].append({
                    "symbol":    symbol,
                    "name":      symbol,
                    "quantity":  qty,
                    "avg":       round(float(entry), 4),
                    "price":     round(float(price), 4),
                    "value":     round(float(value), 2),
                    "pl":        round(float(pl), 2),
                    "plPct":     round(float(pl_pct), 2),
                    "trend":     trend,
                    "flag":      "🇺🇸",
                    "days_held": days_held,
                    "stop_loss":   t.get("stop_loss"),
                    "take_profit": t.get("take_profit"),
                })

            # portfolio_value is Trading 212's "total" = full account equity already,
            # so use it directly as the total (adding cash would double-count it).
            total_portfolio = account.get("portfolio_value", 0) or 0
            result["total_value"] = round(float(total_portfolio), 2)
        except Exception:
            pass

        try:
            for o in (system.get_open_orders() or []):
                result["orders"].append({
                    "id": str(o.get("order_id", "")),
                    "symbol": o.get("symbol", ""),
                    "side": o.get("side", ""),
                    "qty": o.get("quantity", 0),
                    "type": o.get("type", "MARKET"),
                    "price": float(o.get("price", 0) or 0),
                    "status": o.get("status", ""),
                    "placed": str(o.get("placed", "")),
                })
        except Exception:
            pass

    # Load trade history
    import os as _os
    trades = []
    if _os.path.exists("trade_history.json"):
        try:
            with open("trade_history.json", "r") as f:
                trades = json.load(f)
        except Exception:
            pass

    today = datetime.now().strftime("%Y-%m-%d")
    today_trades = [t for t in trades if t.get("timestamp", "").startswith(today)]

    # Decisions (from trade history, most recent first, cap 50)
    for i, t in enumerate(list(reversed(trades))[:50]):
        ts = t.get("timestamp", "")
        at = ts[11:19] if len(ts) >= 19 else ts
        action = t.get("action", "HOLD")
        result["decisions"].append({
            "id":         f"tr_{i:04d}",
            "at":         at,
            "symbol":     t.get("symbol", ""),
            "action":     action,
            "qty":        t.get("quantity", 0),
            "model":      Config.OLLAMA_MODEL,
            "confidence": float(t.get("confidence", 0) or 0),
            "status":     "filled" if t.get("success") else "blocked",
            "price":      float(t.get("price", 0) or 0),
            "reason":     t.get("reasoning", t.get("message", "")),
            "risk_notes": t.get("risk_notes", ""),
            "context":    t.get("context_snapshot", {}),
            # Swing accountability
            "setup_type":          t.get("setup_type", "unknown"),
            "expected_hold_days":  t.get("expected_hold_days"),
            "stop_loss_price":     t.get("stop_loss_price"),
            "take_profit_price":   t.get("take_profit_price"),
            "risk_reward":         t.get("risk_reward"),
        })

    # Avg confidence (decisions that have it)
    conf_vals = [d["confidence"] for d in result["decisions"] if d["confidence"] > 0]
    result["avg_confidence"] = round(sum(conf_vals) / len(conf_vals), 2) if conf_vals else 0.0

    # Activity feed (last 10)
    for t in list(reversed(trades))[:10]:
        ts = t.get("timestamp", "")
        at = ts[11:16] if len(ts) >= 16 else ts
        action = t.get("action", "")
        symbol = t.get("symbol", "")
        qty = t.get("quantity", 0)
        price = float(t.get("price", 0) or 0)
        msg = t.get("message", "")
        tag_cls = "pos" if action == "BUY" else "neg" if action == "SELL" else ""
        text = f'<b>{action}</b> <span class="sym">{symbol}</span> ×{qty} @ ${price:.2f}'
        if msg:
            text += f" — {msg[:80]}"
        result["activity"].append({"t": at, "text": text, "tag": action or "INFO", "tagClass": tag_cls})

    # Decision histogram (today, grouped by hour)
    hist: Dict[int, Any] = {h: {"h": h, "buy": 0, "sell": 0, "hold": 0} for h in range(24)}
    for t in today_trades:
        ts = t.get("timestamp", "")
        try:
            h = int(ts[11:13])
            action = t.get("action", "HOLD").lower()
            if action in ("buy", "sell", "hold"):
                hist[h][action] += 1
        except Exception:
            pass
    result["decisionHist"] = list(hist.values())

    # Equity curve: flat at total_value if no history, otherwise build from trades
    base = result["total_value"] or 10000.0
    if today_trades:
        curve = [{"i": 0, "v": round(base, 2)}]
        running = base
        for i, t in enumerate(today_trades[1:], 1):
            action = t.get("action", "")
            qty = float(t.get("quantity", 0) or 0)
            price = float(t.get("price", 0) or 0)
            delta = price * qty if action == "SELL" else -(price * qty) if action == "BUY" else 0
            running = round(running + delta * 0.01, 2)
            curve.append({"i": i, "v": running})
        # Pad to 72 points
        while len(curve) < 72:
            curve.append({"i": len(curve), "v": curve[-1]["v"]})
        result["equity"] = curve[:72]
    else:
        result["equity"] = [{"i": i, "v": round(base, 2)} for i in range(72)]

    # Profit projections (day / month / year) from the recorded equity history
    try:
        result["projections"] = compute_projections()
    except Exception as e:
        result["projections"] = {"ready": False, "days_tracked": 0, "message": str(e)}

    return jsonify(result)


# ---------------------------------------------------------------------------
# API — open orders
# ---------------------------------------------------------------------------

@app.route("/api/orders")
def api_orders():
    system = _get_system()
    if not system:
        return jsonify([])
    try:
        return jsonify(system.get_open_orders())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — profit projections (day / month / year)
# ---------------------------------------------------------------------------

@app.route("/api/predictions")
def api_predictions():
    """Day / month / year profit projections from the recorded equity history."""
    try:
        return jsonify(compute_projections())
    except Exception as e:
        return jsonify({"ready": False, "days_tracked": 0, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API — bot control (pause / run-cycle-now)
# ---------------------------------------------------------------------------

@app.route("/api/bot/pause", methods=["POST"])
def api_bot_pause():
    paused = bool((request.json or {}).get("paused", True))
    ctrl = _read_bot_control()
    ctrl["paused"] = paused
    _write_bot_control(ctrl)
    return jsonify({"ok": True, "paused": paused})


@app.route("/api/bot/run_cycle", methods=["POST"])
def api_bot_run_cycle():
    ctrl = _read_bot_control()
    ctrl["run_cycle_now"] = True
    ctrl["paused"] = False  # unpause so the bot actually runs
    _write_bot_control(ctrl)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API — remote PC power control
# ---------------------------------------------------------------------------

@app.route("/api/pc/shutdown", methods=["POST"])
def api_pc_shutdown():
    """Schedule a Windows shutdown (2-minute warning, cancellable)."""
    import threading
    delay = int((request.json or {}).get("delay_seconds", 120))
    def _do():
        import time as _t
        _t.sleep(2)
        os.system(f"shutdown /s /t {delay}")
    threading.Thread(target=_do, daemon=True).start()
    return jsonify({
        "ok": True,
        "message": f"PC will shut down in {delay}s. Run 'shutdown /a' to cancel.",
        "delay_seconds": delay,
    })


@app.route("/api/pc/cancel_shutdown", methods=["POST"])
def api_pc_cancel_shutdown():
    os.system("shutdown /a")
    return jsonify({"ok": True, "message": "Shutdown cancelled"})


@app.route("/api/pc/sleep", methods=["POST"])
def api_pc_sleep():
    """Put PC to sleep (hibernate)."""
    import threading
    def _do():
        import time as _t
        _t.sleep(2)
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    threading.Thread(target=_do, daemon=True).start()
    return jsonify({"ok": True, "message": "PC going to sleep in 2s"})


# ---------------------------------------------------------------------------
# API — live log tail
# ---------------------------------------------------------------------------

@app.route("/api/logs")
def api_logs():
    n = min(int(request.args.get("lines", 150)), 500)
    log_file = "trading_bot.log"
    if not os.path.exists(log_file):
        return jsonify({"lines": [], "ok": False, "error": "Log file not found — start the bot first"})
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = list(deque(f, n))
        return jsonify({"lines": [ln.rstrip("\n") for ln in lines], "ok": True})
    except Exception as e:
        return jsonify({"lines": [], "ok": False, "error": str(e)})


# ---------------------------------------------------------------------------
# API — config (read / write .env)
# ---------------------------------------------------------------------------

_ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

# Keys that are safe to expose and edit via the dashboard
_EDITABLE_KEYS = {
    # Model
    "OLLAMA_MODEL", "OLLAMA_TEMPERATURE", "OLLAMA_MAX_TOKENS",
    # Broker
    "TRADING212_DEMO_MODE",
    # Core risk
    "MAX_DAILY_TRADES", "MIN_ACCOUNT_VALUE",
    "STOP_LOSS_PCT", "TAKE_PROFIT_PCT",
    # Swing position sizing
    "RISK_PER_TRADE_PCT", "ATR_STOP_MULTIPLIER", "MIN_RISK_REWARD",
    "MAX_POSITION_PCT", "MAX_HOLD_DAYS",
    # Swing filters
    "EARNINGS_BUFFER_DAYS", "MIN_RELATIVE_STRENGTH",
    "MIN_FILTER_SCORE", "REGIME_STRICT", "MARKET_REGIME_SYMBOL",
    # Cycle
    "BOT_CYCLE_INTERVAL",
    # Screener / discovery
    "MAX_SYMBOLS_PER_CYCLE", "DISCOVERY_INTERVAL_CYCLES",
    "DISCOVERY_TOP_N", "MAX_WATCHLIST_SIZE",
}

# Keys that may be set but should be masked in the response
_SECRET_KEYS = {"TRADING212_API_KEY"}


def _read_env_file() -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    if not os.path.exists(_ENV_FILE):
        return pairs
    with open(_ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            pairs[k.strip()] = v.strip()
    return pairs


def _write_env_file(updates: Dict[str, str]) -> None:
    lines: list = []
    seen: set = set()
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines: list = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        k = stripped.split("=", 1)[0].strip()
        if k in updates:
            new_lines.append(f"{k}={updates[k]}\n")
            seen.add(k)
        else:
            new_lines.append(line)

    # Append any keys that weren't already in the file
    for k, v in updates.items():
        if k not in seen:
            new_lines.append(f"{k}={v}\n")

    with open(_ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


@app.route("/api/config", methods=["GET"])
def api_config_get():
    env = _read_env_file()
    result: Dict[str, Any] = {}
    for k in _EDITABLE_KEYS:
        result[k] = env.get(k, "")
    for k in _SECRET_KEYS:
        result[k] = "***" if env.get(k) else ""
    result["api_key_set"] = bool(env.get("TRADING212_API_KEY"))
    return jsonify(result)


@app.route("/api/config", methods=["POST"])
def api_config_post():
    data: Dict[str, Any] = request.json or {}
    updates: Dict[str, str] = {}

    for k, v in data.items():
        if k in _EDITABLE_KEYS:
            updates[k] = str(v).strip()
        elif k == "TRADING212_API_KEY" and v and v != "***":
            updates[k] = str(v).strip()

    if not updates:
        return jsonify({"error": "no valid keys provided"}), 400

    try:
        _write_env_file(updates)
        return jsonify({"ok": True, "updated": list(updates.keys())})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — Ollama model list
# ---------------------------------------------------------------------------

@app.route("/api/ollama/models")
def api_ollama_models():
    import urllib.request
    try:
        req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        data = json.loads(req.read())
        models = [m["name"] for m in data.get("models", [])]
        return jsonify({"models": models, "ok": True})
    except Exception as e:
        return jsonify({"models": [], "ok": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    print(f"\n  Stock Bot Tracker — Dashboard")
    print(f"  Open http://localhost:{port} in your browser\n")
    app.run(host="0.0.0.0", port=port, debug=False)
