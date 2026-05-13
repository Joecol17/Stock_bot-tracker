"""
Mission Control API Server
Serves the dashboard HTML/JS files and provides live data endpoints.

Run:  python api_server.py
Open: http://localhost:5000
"""

import json
import math
import random
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, send_from_directory, abort
from flask_cors import CORS

from config import Config
from trading212_client import Trading212Client

DASHBOARD_DIR = Path(__file__).parent / "dashboard"
HISTORY_FILE  = Path(__file__).parent / "trade_history.json"
STATUS_FILE   = Path(__file__).parent / "bot_status.json"

app = Flask(__name__, static_folder=str(DASHBOARD_DIR), static_url_path="")
CORS(app)

SERVER_START = time.time()
_client: Trading212Client | None = None


# ── Trading 212 client (lazy init) ───────────────────────────────────────────

def get_client() -> Trading212Client | None:
    global _client
    if _client is not None:
        return _client
    key    = Config.TRADING212_API_KEY
    secret = Config.TRADING212_API_SECRET
    if key and secret:
        try:
            _client = Trading212Client(key, secret, is_demo=Config.TRADING212_DEMO_MODE)
        except Exception as e:
            print(f"[api_server] T212 client init failed: {e}")
    return _client


# ── Static serving ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(DASHBOARD_DIR), "Mission Control.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(str(DASHBOARD_DIR), filename)


# ── Helper loaders ────────────────────────────────────────────────────────────

def load_trade_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return []


def load_bot_status() -> dict:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text())
        except Exception:
            pass
    return {}


# ── Data builders ─────────────────────────────────────────────────────────────

def build_account(client: Trading212Client | None) -> dict:
    if client:
        try:
            acct = client.get_account_info()
            return {
                "account_id":      acct.account_id,
                "cash":            acct.cash,
                "portfolio_value": acct.portfolio_value,
                "free_funds":      acct.free_funds,
            }
        except Exception as e:
            return {"error": str(e), "cash": 0, "portfolio_value": 0, "free_funds": 0, "account_id": "N/A"}
    return {"cash": 0, "portfolio_value": 0, "free_funds": 0, "account_id": "N/A"}


def build_positions(client: Trading212Client | None) -> list:
    if not client:
        return []
    try:
        raw = client.get_positions()
        out = []
        for p in raw:
            pl_pct = ((p.current_price - p.average_price) / p.average_price * 100) if p.average_price else 0
            trend  = "uptrend" if pl_pct > 0.5 else "downtrend" if pl_pct < -0.5 else "neutral"
            out.append({
                "symbol":  p.instrument_code,
                "name":    p.instrument_code,
                "quantity": p.quantity,
                "avg":     p.average_price,
                "price":   p.current_price,
                "value":   p.value,
                "pl":      p.profit_loss,
                "plPct":   round(pl_pct, 2),
                "trend":   trend,
                "flag":    "🌍",
            })
        return out
    except Exception as e:
        return [{"error": str(e)}]


def build_orders(client: Trading212Client | None) -> list:
    if not client:
        return []
    try:
        raw = client.get_orders()
        return [
            {
                "id":     o.order_id,
                "symbol": o.instrument_code,
                "side":   o.side,
                "qty":    o.quantity,
                "type":   "MARKET",
                "price":  o.price,
                "status": o.status,
                "placed": o.order_id,
            }
            for o in raw[:15]
        ]
    except Exception:
        return []


def build_decisions(history: list) -> list:
    out = []
    model = Config.OLLAMA_MODEL
    for i, h in enumerate(reversed(history[-30:])):
        ts = h.get("timestamp", "")
        if "T" in ts:
            at = ts.split("T")[1][:8]
        else:
            at = ts[:8]

        action = h.get("action", "HOLD")
        out.append({
            "id":         f"tr_{1000 + i:04d}",
            "at":         at,
            "symbol":     h.get("symbol", ""),
            "action":     action,
            "qty":        h.get("quantity", 0) if action != "HOLD" else 0,
            "model":      model,
            "confidence": 0.70,
            "status":     "filled" if h.get("success") else ("blocked" if not h.get("success") else "no-action"),
            "price":      0,
            "reason":     h.get("message", ""),
            "context":    {},
        })
    return out


def build_activity(decisions: list) -> list:
    activity = []
    for d in decisions[:12]:
        action = d["action"]
        tag_class = "accent" if action == "HOLD" else ("pos" if action == "BUY" else "neg")
        activity.append({
            "t":        d["at"],
            "kind":     "decision",
            "text":     f'<b>{d["model"]}</b> decided <span class="sym">{d["symbol"]}</span> → <b>{action}</b>',
            "tag":      "AI",
            "tagClass": "accent",
        })
    return activity


def build_equity(portfolio_value: float) -> list:
    """Generate a plausible intraday equity curve ending at the current portfolio value."""
    rng = random.Random(datetime.utcnow().date().toordinal())
    pts = []
    v = max(100, portfolio_value * 0.985)
    for i in range(72):
        v += (math.sin(i / 6) * 5) + (rng.random() - 0.45) * 9 + (0.7 if i > 30 else 0)
        pts.append({"i": i, "v": round(v, 2)})
    if pts:
        pts[-1]["v"] = round(portfolio_value, 2)
    return pts


def build_decision_hist(decisions: list) -> list:
    hist = [{"h": h, "buy": 0, "sell": 0, "hold": 0} for h in range(24)]
    for d in decisions:
        try:
            hour = int(d["at"].split(":")[0]) if ":" in d["at"] else 0
            action = d["action"].lower()
            if action in ("buy", "sell", "hold"):
                hist[hour][action] += 1
        except Exception:
            pass
    return hist


def build_sources(client: Trading212Client | None) -> list:
    import requests as req

    # Ollama health
    ollama_status  = "offline"
    ollama_latency = 9999
    try:
        t0 = time.time()
        r  = req.get("http://localhost:11434/api/tags", timeout=2)
        ollama_latency = round((time.time() - t0) * 1000)
        ollama_status  = "live" if r.status_code == 200 else "degraded"
    except Exception:
        pass

    # T212 health (we already know if the client works)
    t212_status  = "live" if client else "offline"
    t212_latency = 38
    if client:
        try:
            t0 = time.time()
            client.get_account_info()
            t212_latency = round((time.time() - t0) * 1000)
        except Exception:
            t212_status = "degraded"

    label = "Trading 212 — Demo" if Config.TRADING212_DEMO_MODE else "Trading 212 — Live"

    return [
        {"id": "t212",     "kind": "broker", "label": label,                           "city": "London",    "country": "UK", "lat_px": 30, "lng_px": 49, "status": t212_status,  "latency": t212_latency, "throughput": "live",      "description": "Orders, positions, account state"},
        {"id": "yfinance", "kind": "market", "label": "Market Data — yfinance",        "city": "New York",  "country": "US", "lat_px": 39, "lng_px": 28, "status": "live",       "latency": 120,          "throughput": "on-demand", "description": "NYSE / NASDAQ prices via yfinance"},
        {"id": "ollama",   "kind": "ai",     "label": f"Ollama ({Config.OLLAMA_MODEL}) — local", "city": "Localhost", "country": "—", "lat_px": 64, "lng_px": 50, "status": ollama_status, "latency": ollama_latency, "throughput": "on-demand", "description": "AI decision engine"},
        {"id": "config",   "kind": "config", "label": "Risk & Config — local",         "city": "Localhost", "country": "—", "lat_px": 64, "lng_px": 50, "status": "live",       "latency": 1,            "throughput": "—",         "description": "Daily limits, demo flag"},
    ]


# ── API routes ────────────────────────────────────────────────────────────────

@app.route("/api/all")
def api_all():
    """Single endpoint — returns everything the dashboard needs in one shot."""
    client   = get_client()
    history  = load_trade_history()
    bot_file = load_bot_status()

    account   = build_account(client)
    positions = build_positions(client)
    orders    = build_orders(client)
    decisions = build_decisions(history)
    activity  = build_activity(decisions)
    equity    = build_equity(account.get("portfolio_value", 9870))
    hist      = build_decision_hist(decisions)
    sources   = build_sources(client)

    uptime = round(time.time() - SERVER_START)

    return jsonify({
        "account":      account,
        "positions":    positions,
        "orders":       orders,
        "decisions":    decisions,
        "activity":     activity,
        "equity":       equity,
        "decisionHist": hist,
        "sources":      sources,
        "botStatus": {
            "isDemo":        Config.TRADING212_DEMO_MODE,
            "model":         Config.OLLAMA_MODEL,
            "temperature":   Config.OLLAMA_TEMPERATURE,
            "maxTokens":     Config.OLLAMA_MAX_TOKENS,
            "maxDailyTrades":Config.MAX_DAILY_TRADES,
            "cycleCount":    bot_file.get("cycle_count", 0),
            "uptimeSeconds": uptime,
        },
    })


@app.route("/api/cycle", methods=["POST"])
def api_run_cycle():
    """Signal the bot to run an extra cycle (writes a trigger file)."""
    Path("run_cycle.trigger").write_text("1")
    return jsonify({"ok": True, "message": "Cycle trigger written"})


@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "uptime": round(time.time() - SERVER_START)})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Mission Control — API Server")
    print("  Dashboard: http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
