"""
Web dashboard for the Stock Bot Tracker.

Run with:  python dashboard.py
Then open: http://localhost:5000
"""

import json
import os
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

from config import Config
from watchlist import WatchlistManager

app = Flask(__name__)

# Lazy-initialised — app starts even without an API key
_system = None


def _get_system():
    global _system
    if _system is None and Config.TRADING212_API_KEY:
        from trading_system import TradingSystem
        _system = TradingSystem(
            api_key=Config.TRADING212_API_KEY,
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
            "total_value":     account.get("cash", 0) + account.get("portfolio_value", 0),
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
    }

    # Account status & positions
    system = _get_system()
    if system:
        try:
            account = system.get_account_status()
            tracked = system.get_tracked_positions()
            result["cash"] = account.get("cash", 0)
            result["free_funds"] = account.get("free_funds", account.get("cash", 0))

            for pos in account.get("positions", []):
                symbol = pos.get("symbol", "")
                t = tracked.get(symbol, {})
                entry = t.get("entry_price") or pos.get("avg_price", 0) or 0
                price = pos.get("current_price", 0) or 0
                qty = pos.get("quantity", 0) or 0
                value = pos.get("value", price * qty) or 0
                pl = pos.get("profit_loss", 0) or 0
                pl_pct = ((price - entry) / entry * 100) if entry else 0
                trend = "uptrend" if pl_pct > 1 else "downtrend" if pl_pct < -1 else "neutral"
                result["positions"].append({
                    "symbol": symbol,
                    "name": symbol,
                    "quantity": qty,
                    "avg": round(float(entry), 4),
                    "price": round(float(price), 4),
                    "value": round(float(value), 2),
                    "pl": round(float(pl), 2),
                    "plPct": round(float(pl_pct), 2),
                    "trend": trend,
                    "flag": "🇺🇸",
                })

            total_portfolio = account.get("portfolio_value", 0) or 0
            result["total_value"] = round(float(result["cash"]) + float(total_portfolio), 2)
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
            "id": f"tr_{i:04d}",
            "at": at,
            "symbol": t.get("symbol", ""),
            "action": action,
            "qty": t.get("quantity", 0),
            "model": Config.OLLAMA_MODEL,
            "confidence": 0.0,
            "status": "filled" if t.get("success") else "blocked",
            "price": float(t.get("price", 0) or 0),
            "reason": t.get("message", ""),
            "context": {},
        })

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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    print(f"\n  Stock Bot Tracker — Dashboard")
    print(f"  Open http://localhost:{port} in your browser\n")
    app.run(host="0.0.0.0", port=port, debug=False)
