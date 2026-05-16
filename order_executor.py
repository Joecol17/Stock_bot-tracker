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
    ) -> ExecutionResult:
        """
        Execute a trade from a DecisionEngine output dict.

        decision structure from make_decision():
          { "model": ..., "raw_text": ..., "decision": {"action": "BUY", ...} }
        """
        try:
            action = self._extract_action(decision)

            if action == "BUY":
                result = self._execute_buy(symbol, quantity)
            elif action == "SELL":
                result = self._execute_sell(symbol, quantity)
            elif action == "HOLD":
                result = ExecutionResult(
                    success=True, symbol=symbol, action="HOLD",
                    quantity=0, message="Holding position as per decision",
                )
            else:
                result = ExecutionResult(
                    success=False, symbol=symbol, action=action,
                    quantity=quantity, message=f"Unknown action: {action}",
                    error=f"Unknown action: {action}",
                )

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

        for symbol, tracking in list(self._tracked_positions.items()):
            if symbol not in current_prices:
                # Position closed externally — stop tracking it
                del self._tracked_positions[symbol]
                continue

            price = current_prices[symbol]
            hit = None
            if price <= tracking["stop_loss"]:
                hit = "STOP_LOSS"
            elif price >= tracking["take_profit"]:
                hit = "TAKE_PROFIT"

            if hit:
                result = self._execute_sell(symbol, tracking["quantity"])
                result.action = hit
                entry = tracking["entry_price"]
                pct = round((price - entry) / entry * 100, 2)
                result.message = (
                    f"{hit}: sold {tracking['quantity']} {symbol} at ${price:.4f} "
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

    def _execute_buy(self, symbol: str, quantity: float) -> ExecutionResult:
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

            # Fetch fill price and register SL/TP tracking
            self._register_position(symbol, quantity)

            return ExecutionResult(
                success=True, symbol=symbol, action="BUY", quantity=quantity,
                message=f"BUY order placed: {quantity} shares of {symbol}",
                order_id=order_id,
            )

        except Exception as e:
            return ExecutionResult(
                success=False, symbol=symbol, action="BUY", quantity=quantity,
                message=f"BUY order failed: {e}", error=str(e),
            )

    def _register_position(self, symbol: str, quantity: float) -> None:
        """Record entry price and SL/TP levels for a newly bought position."""
        time.sleep(1)  # brief wait for the order to settle before fetching position
        try:
            positions = self.client.get_positions()
            pos = next((p for p in positions if p.instrument_code == symbol), None)
            entry = pos.average_price if pos else None
        except Exception:
            entry = None

        if not entry or entry <= 0:
            return  # can't track without a valid entry price

        self._tracked_positions[symbol] = {
            "entry_price": entry,
            "stop_loss": round(entry * (1 - Config.STOP_LOSS_PCT), 4),
            "take_profit": round(entry * (1 + Config.TAKE_PROFIT_PCT), 4),
            "quantity": quantity,
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

            response = self.client.place_order(
                symbol=symbol, quantity=quantity,
                side=OrderSide.SELL, order_type=OrderType.MARKET,
            )
            order_id = str(response.get("id") or response.get("orderId") or "")
            return ExecutionResult(
                success=True, symbol=symbol, action="SELL", quantity=quantity,
                message=f"SELL order placed: {quantity} shares of {symbol}",
                order_id=order_id,
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
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": result.symbol,
            "action": result.action,
            "quantity": result.quantity,
            "success": result.success,
            "message": result.message,
            "order_id": result.order_id,
            "error": result.error,
        }
        self.trade_history.append(record)
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.trade_history, f, indent=2)
        except Exception:
            pass  # Persistence is best-effort; don't crash the bot over a write failure
