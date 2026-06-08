"""
Discord notification system — multi-channel routing.

Set one webhook URL per channel in your environment:

  DISCORD_WEBHOOK_TRADES      → #trades      (BUY / SELL executions)
  DISCORD_WEBHOOK_RISK        → #risk-exits  (stop-loss / take-profit)
  DISCORD_WEBHOOK_PORTFOLIO   → #portfolio   (cycle account snapshots)
  DISCORD_WEBHOOK_DISCOVERY   → #discovery   (new stocks added)
  DISCORD_WEBHOOK_ALERTS      → #alerts      (errors, bot start/stop, limits)
  DISCORD_WEBHOOK_URL         → fallback used for any channel not configured

Any channel without a specific webhook falls back to DISCORD_WEBHOOK_URL.
If no webhooks are set at all, all methods silently no-op.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_COLOUR = {
    "buy":       0x2ECC71,
    "sell":      0xE74C3C,
    "stop":      0xE67E22,
    "profit":    0x27AE60,
    "info":      0x3498DB,
    "error":     0xFF0000,
    "portfolio": 0x9B59B6,
    "discovery": 0x1ABC9C,
    "alert":     0xF39C12,
}


class DiscordNotifier:
    """Route notifications to per-channel Discord webhooks."""

    def __init__(
        self,
        fallback: Optional[str] = None,
        trades: Optional[str] = None,
        risk: Optional[str] = None,
        portfolio: Optional[str] = None,
        discovery: Optional[str] = None,
        alerts: Optional[str] = None,
    ) -> None:
        self._fallback   = fallback
        self._trades     = trades     or fallback
        self._risk       = risk       or fallback
        self._portfolio  = portfolio  or fallback
        self._discovery  = discovery  or fallback
        self._alerts     = alerts     or fallback

        configured = sum(1 for u in [trades, risk, portfolio, discovery, alerts, fallback] if u)
        if configured:
            logger.info(f"Discord notifications enabled ({configured} webhook(s) configured)")
        else:
            logger.debug("Discord notifications disabled (no webhooks set)")

    # ------------------------------------------------------------------
    # #trades
    # ------------------------------------------------------------------

    def trade_executed(
        self,
        symbol: str,
        action: str,
        quantity: float,
        price: Optional[float] = None,
        order_id: Optional[str] = None,
        reasoning: Optional[str] = None,
        is_demo: bool = True,
    ) -> None:
        colour = _COLOUR["buy"] if action == "BUY" else _COLOUR["sell"]
        mode_tag = "🟡 DEMO" if is_demo else "🔴 LIVE"
        emoji = "📈" if action == "BUY" else "📉"
        title = f"{emoji} {action} — {symbol}  [{mode_tag}]"

        fields = [{"name": "Quantity", "value": str(quantity), "inline": True}]
        if price:
            fields.append({"name": "Price", "value": f"${price:,.4f}", "inline": True})
        if order_id:
            fields.append({"name": "Order ID", "value": order_id, "inline": True})
        if reasoning:
            fields.append({"name": "AI Reasoning", "value": reasoning[:300], "inline": False})

        self._send(self._trades, title=title, colour=colour, fields=fields)

    # ------------------------------------------------------------------
    # #risk-exits
    # ------------------------------------------------------------------

    def risk_exit(
        self,
        symbol: str,
        exit_type: str,
        entry_price: float,
        exit_price: float,
        pnl_pct: float,
        is_demo: bool = True,
    ) -> None:
        colour = _COLOUR["profit"] if exit_type == "TAKE_PROFIT" else _COLOUR["stop"]
        emoji = "✅" if exit_type == "TAKE_PROFIT" else "🛑"
        mode_tag = "🟡 DEMO" if is_demo else "🔴 LIVE"
        label = exit_type.replace("_", " ")
        title = f"{emoji} {label} — {symbol}  [{mode_tag}]"
        sign = "+" if pnl_pct >= 0 else ""

        fields = [
            {"name": "Entry",  "value": f"${entry_price:,.4f}",      "inline": True},
            {"name": "Exit",   "value": f"${exit_price:,.4f}",        "inline": True},
            {"name": "P/L",    "value": f"{sign}{pnl_pct:.2f}%",      "inline": True},
        ]
        self._send(self._risk, title=title, colour=colour, fields=fields)

    # ------------------------------------------------------------------
    # #portfolio
    # ------------------------------------------------------------------

    def cycle_summary(
        self,
        cycle: int,
        trades_this_cycle: int,
        total_trades: int,
        cash: float,
        portfolio_value: float,
        errors: int,
        is_demo: bool = True,
    ) -> None:
        mode_tag = "🟡 DEMO" if is_demo else "🔴 LIVE"
        # portfolio_value is the FULL account equity (free cash + holdings), so it
        # IS the total — holdings alone are total minus free cash. (Previously this
        # added cash to the total, double-counting it.)
        holdings = max(0.0, portfolio_value - cash)
        title = f"📊 Cycle {cycle} — Portfolio Snapshot  [{mode_tag}]"

        fields = [
            {"name": "💵 Cash",          "value": f"${cash:,.2f}",            "inline": True},
            {"name": "📦 Holdings",      "value": f"${holdings:,.2f}",        "inline": True},
            {"name": "💰 Total Value",   "value": f"${portfolio_value:,.2f}", "inline": True},
            {"name": "Trades (cycle)",   "value": str(trades_this_cycle),     "inline": True},
            {"name": "Trades (total)",   "value": str(total_trades),          "inline": True},
            {"name": "Errors",           "value": str(errors),                "inline": True},
        ]
        self._send(self._portfolio, title=title, colour=_COLOUR["portfolio"], fields=fields)

    # ------------------------------------------------------------------
    # #discovery
    # ------------------------------------------------------------------

    def discovery_update(self, added: List[str], watchlist_size: int) -> None:
        if not added:
            return
        title = f"🔍 {len(added)} new stock(s) discovered"
        fields = [
            {"name": "Added to watchlist", "value": "  ".join(f"`{s}`" for s in added), "inline": False},
            {"name": "Watchlist size",     "value": str(watchlist_size),                 "inline": True},
        ]
        self._send(self._discovery, title=title, colour=_COLOUR["discovery"], fields=fields)

    # ------------------------------------------------------------------
    # #alerts
    # ------------------------------------------------------------------

    def error(self, message: str, context: Optional[str] = None) -> None:
        title = "⚠️ Bot Error"
        fields = [{"name": "Error", "value": message[:500], "inline": False}]
        if context:
            fields.append({"name": "Context", "value": context[:200], "inline": False})
        self._send(self._alerts, title=title, colour=_COLOUR["error"], fields=fields)

    def bot_started(self, symbols: List[str], interval: int, is_demo: bool) -> None:
        mode_tag = "🟡 DEMO" if is_demo else "🔴 LIVE"
        title = f"🚀 Trading Bot Started  [{mode_tag}]"
        symbol_preview = "  ".join(f"`{s}`" for s in symbols[:15])
        if len(symbols) > 15:
            symbol_preview += f"  + {len(symbols) - 15} more"
        fields = [
            {"name": "Watchlist",  "value": symbol_preview,                                   "inline": False},
            {"name": "Interval",   "value": f"{interval}s",                                   "inline": True},
            {"name": "Started at", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),      "inline": True},
        ]
        self._send(self._alerts, title=title, colour=_COLOUR["info"], fields=fields)

    def bot_stopped(self, total_trades: int, errors: int) -> None:
        title = "🛑 Trading Bot Stopped"
        fields = [
            {"name": "Total trades", "value": str(total_trades),                              "inline": True},
            {"name": "Errors",       "value": str(errors),                                    "inline": True},
            {"name": "Stopped at",   "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),   "inline": True},
        ]
        self._send(self._alerts, title=title, colour=_COLOUR["alert"], fields=fields)

    def daily_limit_reached(self, limit: int, is_demo: bool) -> None:
        mode_tag = "🟡 DEMO" if is_demo else "🔴 LIVE"
        title = f"🚫 Daily Trade Limit Reached  [{mode_tag}]"
        fields = [{"name": "Limit", "value": str(limit), "inline": True}]
        self._send(self._alerts, title=title, colour=_COLOUR["alert"], fields=fields)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send(
        self,
        webhook_url: Optional[str],
        title: str,
        colour: int,
        fields: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None,
    ) -> None:
        if not webhook_url:
            return

        embed: Dict[str, Any] = {
            "title": title,
            "color": colour,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Stock Bot Tracker"},
        }
        if description:
            embed["description"] = description
        if fields:
            embed["fields"] = fields

        try:
            response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
            if response.status_code not in (200, 204):
                logger.warning(f"Discord webhook {response.status_code}: {response.text[:200]}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Discord notification failed: {e}")
