import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from trading212_client import Trading212Client, OrderSide, OrderType
from config import Config

HISTORY_FILE = "trade_history.json"


@dataclass
class ExecutionResult:
    success: bool
    symbol: str
    action: str
    quantity: float
    message: str
    order_id: Optional[str] = None
    error: Optional[str] = None
    price: float = 0.0       # fill / context price recorded at execution
    confidence: float = 0.0  # LLM confidence (0.0–1.0)


class OrderExecutor:
    """Translates decision engine outputs into Trading 212 orders."""

    def __init__(self, trading_client: Trading212Client):
        self.client = trading_client
        self.trade_history = self._load_history()
        # symbol -> {entry_price, stop_loss, take_profit, quantity}
        self._tracked_positions: Dict[str, Dict[str, float]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_decision(
        self,
        decision: Dict[str, Any],
        symbol: str,
        quantity: float = 1,
        account_value: float = 0,
        context: Dict[str, Any] = None,
    ) -> ExecutionResult:
        """
        Execute a swing trade from a DecisionEngine output dict.

        Adds vs the old version:
          - Reads stop_loss_price / take_profit_price from LLM JSON
          - Falls back to ATR-based stops if LLM doesn't supply prices
          - Calculates quantity from % portfolio risk ÷ per-share risk
          - Persists accountability fields: setup_type, expected_hold_days, R:R
        """
        context = context or {}
        try:
            action = self._extract_action(decision)
            inner  = decision.get("decision", {}) if isinstance(decision.get("decision"), dict) else {}

            # ── Confidence ─────────────────────────────────────────────────
            try:
                confidence = max(0.0, min(1.0, float(inner.get("confidence", 0.0) or 0.0)))
            except (TypeError, ValueError):
                confidence = 0.0

            # ── Stop / target prices from LLM (with ATR fallback) ──────────
            entry_price = float(context.get("price", 0) or 0)
            atr         = float(context.get("atr_14", 0) or 0)

            llm_stop   = inner.get("stop_loss_price")
            llm_target = inner.get("take_profit_price")

            try:
                stop_price = float(llm_stop) if llm_stop else None
            except (TypeError, ValueError):
                stop_price = None

            try:
                target_price = float(llm_target) if llm_target else None
            except (TypeError, ValueError):
                target_price = None

            # ATR-based fallback
            if entry_price > 0 and atr > 0:
                if stop_price is None:
                    stop_price = round(entry_price - atr * Config.ATR_STOP_MULTIPLIER, 4)
                if target_price is None:
                    target_price = round(entry_price + atr * Config.ATR_STOP_MULTIPLIER * Config.MIN_RISK_REWARD, 4)

            # Final fallback: percentage-based
            if stop_price is None and entry_price > 0:
                stop_price = round(entry_price * (1 - Config.STOP_LOSS_PCT), 4)
            if target_price is None and entry_price > 0:
                target_price = round(entry_price * (1 + Config.TAKE_PROFIT_PCT), 4)

            # ── Risk-based quantity sizing ──────────────────────────────────
            if action == "BUY" and account_value > 0 and stop_price and entry_price > stop_price:
                risk_dollars  = account_value * Config.RISK_PER_TRADE_PCT
                per_share_risk = entry_price - stop_price
                sized_qty      = max(1, int(risk_dollars / per_share_risk))
                # Cap at MAX_POSITION_PCT of portfolio
                max_value = account_value * Config.MAX_POSITION_PCT
                max_qty   = max(1, int(max_value / entry_price)) if entry_price > 0 else sized_qty
                quantity  = min(sized_qty, max_qty)
            # else: use the fallback quantity passed in

            # ── Accountability metadata ─────────────────────────────────────
            setup_type        = inner.get("setup_type", "unknown") or "unknown"
            expected_hold_days = None
            try:
                expected_hold_days = int(inner.get("expected_hold_days", 0) or 0) or None
            except (TypeError, ValueError):
                pass
            risk_reward = None
            if stop_price and target_price and entry_price and entry_price > stop_price:
                risk_reward = round((target_price - entry_price) / (entry_price - stop_price), 2)

            reasoning  = inner.get("reasoning", "")
            risk_notes = inner.get("risk_notes", "")

            # ── Execution ──────────────────────────────────────────────────
            if action == "BUY":
                result = self._execute_buy(symbol, quantity, stop_price, target_price)
            elif action == "SELL":
                result = self._execute_sell(symbol, quantity)
            elif action == "HOLD":
                result = ExecutionResult(
                    success=True, symbol=symbol, action="HOLD",
                    quantity=0, message="HOLD — no qualifying setup",
                )
            else:
                result = ExecutionResult(
                    success=False, symbol=symbol, action=action,
                    quantity=quantity, message=f"Unknown action: {action}",
                    error=f"Unknown action: {action}",
                )

            # Attach metadata to result for _save_history
            result.confidence         = confidence
            result.setup_type         = setup_type
            result.expected_hold_days = expected_hold_days
            result.stop_loss_price    = stop_price
            result.take_profit_price  = target_price
            result.risk_reward        = risk_reward
            result.reasoning          = reasoning
            result.risk_notes         = risk_notes
            result.context_snapshot   = {
                k: context.get(k) for k in (
                    "rsi_14", "macd_crossover", "price_vs_sma50_pct",
                    "atr_14", "bb_position", "volume", "trend",
                    "pre_trade_filters",
                ) if context.get(k) is not None
            }

            self._save_history(result)
            return result

        except Exception as e:
            return ExecutionResult(
                success=False, symbol=symbol, action="UNKNOWN",
                quantity=quantity, message=f"Execution failed: {e}", error=str(e),
            )

    def get_account_summary(self) -> Dict[str, Any]:
        try:
            account = self.client.get_account_info()
            positions = self.client.get_positions()
            return {
                "account_id": account.account_id,
                "cash": account.cash,
                "portfolio_value": account.portfolio_value,
                "free_funds": account.free_funds,
                "positions_count": len(positions),
                "positions": [
                    {
                        "symbol": p.instrument_code,
                        "quantity": p.quantity,
                        "current_price": p.current_price,
                        "value": p.value,
                        "profit_loss": p.profit_loss,
                    }
                    for p in positions
                ],
            }
        except Exception as e:
            return {"error": str(e)}

    def get_trade_history(self) -> list:
        return self.trade_history

    def check_and_execute_exits(self) -> List[ExecutionResult]:
        """
        Check all tracked positions against their stop-loss and take-profit levels.
        Executes a market sell for any that have been hit. Returns list of results.
        """
        if not self._tracked_positions:
            return []

        try:
            positions = self.client.get_positions()
        except Exception:
            return []

        current_prices = {p.instrument_code: p.current_price for p in positions}
        results: List[ExecutionResult] = []

        today = datetime.utcnow().date()

        for symbol, tracking in list(self._tracked_positions.items()):
            if symbol not in current_prices:
                del self._tracked_positions[symbol]
                continue

            price = current_prices[symbol]
            hit   = None

            if price <= tracking["stop_loss"]:
                hit = "STOP_LOSS"
            elif price >= tracking["take_profit"]:
                hit = "TAKE_PROFIT"

            # Max-hold-days warning (log only — does not force exit)
            entry_date_str = tracking.get("entry_date")
            if entry_date_str and not hit:
                try:
                    from datetime import date
                    entry_date = date.fromisoformat(entry_date_str)
                    days_held  = (today - entry_date).days
                    if days_held >= Config.MAX_HOLD_DAYS:
                        import logging as _log
                        _log.getLogger(__name__).warning(
                            f"[REVIEW] {symbol} has been held {days_held} days "
                            f"(max {Config.MAX_HOLD_DAYS}). Consider reviewing the position."
                        )
                except Exception:
                    pass

            if hit:
                result = self._execute_sell(symbol, tracking["quantity"])
                result.action = hit
                entry = tracking["entry_price"]
                pct   = round((price - entry) / entry * 100, 2)
                result.message = (
                    f"{hit}: sold {tracking['quantity']} {symbol} @ ${price:.4f} "
                    f"(entry ${entry:.4f}, {pct:+.2f}%)"
                )
                self._save_history(result)
                results.append(result)
                del self._tracked_positions[symbol]

        return results

    def get_tracked_positions(self) -> Dict[str, Dict[str, float]]:
        """Return a copy of the current SL/TP tracking state."""
        return dict(self._tracked_positions)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_action(self, decision: Dict[str, Any]) -> str:
        """
        Extract BUY / SELL / HOLD from the decision dict.

        make_decision() returns:
          { "model": ..., "raw_text": ..., "decision": {"action": "BUY", "reasoning": ..., ...} }

        The inner "decision" value is the parsed JSON from the LLM.
        """
        inner = decision.get("decision", {})

        # Happy path: inner dict has an "action" key (matches our prompt template).
        if isinstance(inner, dict):
            action_val = inner.get("action", "")
            if isinstance(action_val, str) and action_val.upper() in ("BUY", "SELL", "HOLD"):
                return action_val.upper()

            # Check alternate key names some models may use.
            for key in ("recommendation", "signal", "trade", "decision"):
                val = inner.get(key, "")
                if isinstance(val, str):
                    for word in ("BUY", "SELL", "HOLD"):
                        if word in val.upper():
                            return word

        # Fallback: scan the raw LLM text for BUY / SELL / HOLD.
        raw = str(decision.get("raw_text", "")).upper()
        for word in ("BUY", "SELL", "HOLD"):
            if word in raw:
                return word

        return "HOLD"

    def _execute_buy(
        self,
        symbol: str,
        quantity: float,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
    ) -> ExecutionResult:
        try:
            account = self.client.get_account_info()
            if account.free_funds <= 0:
                return ExecutionResult(
                    success=False, symbol=symbol, action="BUY", quantity=quantity,
                    message="Insufficient funds", error="No free funds available",
                )

            response = self.client.place_order(
                symbol=symbol, quantity=quantity,
                side=OrderSide.BUY, order_type=OrderType.MARKET,
            )
            order_id = str(response.get("id") or response.get("orderId") or "")

            self._register_position(symbol, quantity, stop_price, target_price)
            fill_price = self._tracked_positions.get(symbol, {}).get("entry_price", 0.0)

            return ExecutionResult(
                success=True, symbol=symbol, action="BUY", quantity=quantity,
                message=f"BUY {quantity} {symbol} @ ~${fill_price:.2f} | stop ${stop_price} → target ${target_price}",
                order_id=order_id,
                price=fill_price,
            )

        except Exception as e:
            return ExecutionResult(
                success=False, symbol=symbol, action="BUY", quantity=quantity,
                message=f"BUY order failed: {e}", error=str(e),
            )

    def _register_position(
        self,
        symbol: str,
        quantity: float,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
    ) -> None:
        """Record entry price, SL/TP levels, and entry date for a newly bought position."""
        time.sleep(1)
        try:
            positions = self.client.get_positions()
            pos = next((p for p in positions if p.instrument_code == symbol), None)
            entry = float(pos.average_price) if pos else None
        except Exception:
            entry = None

        if not entry or entry <= 0:
            return

        sl = stop_price  or round(entry * (1 - Config.STOP_LOSS_PCT), 4)
        tp = target_price or round(entry * (1 + Config.TAKE_PROFIT_PCT), 4)

        self._tracked_positions[symbol] = {
            "entry_price": entry,
            "stop_loss":   sl,
            "take_profit": tp,
            "quantity":    quantity,
            "entry_date":  datetime.utcnow().strftime("%Y-%m-%d"),
        }

    def _execute_sell(self, symbol: str, quantity: float) -> ExecutionResult:
        try:
            positions = self.client.get_positions()
            position = next((p for p in positions if p.instrument_code == symbol), None)

            available = position.quantity if position else 0
            if not position or available < quantity:
                return ExecutionResult(
                    success=False, symbol=symbol, action="SELL", quantity=quantity,
                    message=f"Insufficient position. Available: {available}",
                    error=f"Only {available} shares available",
                )

            sell_price = float(position.current_price or 0.0) if position else 0.0
            response = self.client.place_order(
                symbol=symbol, quantity=quantity,
                side=OrderSide.SELL, order_type=OrderType.MARKET,
            )
            order_id = str(response.get("id") or response.get("orderId") or "")
            return ExecutionResult(
                success=True, symbol=symbol, action="SELL", quantity=quantity,
                message=f"SELL order placed: {quantity} shares of {symbol}",
                order_id=order_id,
                price=sell_price,
            )

        except Exception as e:
            return ExecutionResult(
                success=False, symbol=symbol, action="SELL", quantity=quantity,
                message=f"SELL order failed: {e}", error=str(e),
            )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_history(self) -> list:
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_history(self, result: ExecutionResult) -> None:
        if result.action == "HOLD":
            return  # Don't clutter the log with holds

        record = {
            # Core
            "timestamp":  datetime.utcnow().isoformat(),
            "symbol":     result.symbol,
            "action":     result.action,
            "quantity":   result.quantity,
            "price":      round(float(result.price or 0.0), 4),
            "success":    result.success,
            "message":    result.message,
            "order_id":   result.order_id,
            "error":      result.error,
            # LLM quality
            "confidence":          round(float(result.confidence or 0.0), 4),
            "reasoning":           getattr(result, "reasoning", ""),
            "risk_notes":          getattr(result, "risk_notes", ""),
            # Swing accountability
            "setup_type":          getattr(result, "setup_type", "unknown"),
            "expected_hold_days":  getattr(result, "expected_hold_days", None),
            "stop_loss_price":     getattr(result, "stop_loss_price", None),
            "take_profit_price":   getattr(result, "take_profit_price", None),
            "risk_reward":         getattr(result, "risk_reward", None),
            # Snapshot of the key signals at entry (for post-trade review)
            "context_snapshot":    getattr(result, "context_snapshot", {}),
        }
        self.trade_history.append(record)
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.trade_history, f, indent=2)
        except Exception:
            pass  # Persistence is best-effort; don't crash the bot over a write failure
