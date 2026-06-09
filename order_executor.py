import json
import math
import os
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from trading212_client import Trading212Client, OrderSide, OrderType
from config import Config

logger = logging.getLogger(__name__)


def _us_market_open() -> bool:
    """Return True if US equity markets are currently open (Mon–Fri 9:30–16:00 ET).

    Uses zoneinfo (Python 3.9+ stdlib, Windows needs 'tzdata' pip package).
    Falls back to a UTC-based manual calculation if zoneinfo is unavailable.
    """
    try:
        from zoneinfo import ZoneInfo
        et = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        # Fallback: derive Eastern Time from UTC without third-party libs
        from datetime import timedelta as _td
        utc = datetime.utcnow()
        y = utc.year
        mar1 = datetime(y, 3, 1)
        dst_start = mar1 + _td(days=(6 - mar1.weekday()) % 7 + 7)   # 2nd Sunday of March
        nov1 = datetime(y, 11, 1)
        dst_end   = nov1 + _td(days=(6 - nov1.weekday()) % 7)        # 1st Sunday of November
        h = -4 if dst_start.date() <= utc.date() < dst_end.date() else -5
        et = utc + _td(hours=h)
    if et.weekday() >= 5:          # Saturday / Sunday
        return False
    mins = et.hour * 60 + et.minute
    return 9 * 60 + 30 <= mins < 16 * 60   # 09:30–16:00 ET

HISTORY_FILE = "trade_history.json"
TRACKED_FILE = "tracked_positions.json"   # persists SL/TP/trailing across restarts


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
        # symbol -> {entry_price, stop_loss, take_profit, quantity,
        #            highest_price, trailing_active, entry_date}
        self._tracked_positions: Dict[str, Dict[str, float]] = self._load_tracked()

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
        free_funds: Optional[float] = None,
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

            # ── Risk-based quantity sizing (fractional shares) ──────────────
            undersized_msg = None
            if action == "BUY" and account_value > 0 and stop_price and entry_price > stop_price:
                # Bigger positions during the market-open focus window.
                risk_pct = (Config.FOCUS_RISK_PER_TRADE_PCT
                            if Config.in_focus_period() else Config.RISK_PER_TRADE_PCT)
                risk_dollars   = account_value * risk_pct
                per_share_risk = entry_price - stop_price
                sized_qty      = risk_dollars / per_share_risk
                # Cap at MAX_POSITION_PCT of total portfolio value.
                sized_qty = min(sized_qty, (account_value * Config.MAX_POSITION_PCT) / entry_price)
                # Never order more than free cash can afford (1% buffer for slippage/fees).
                if free_funds is not None and free_funds > 0:
                    sized_qty = min(sized_qty, (free_funds * 0.99) / entry_price)
                # Round DOWN to 0.01-share granularity so we never exceed the budget.
                quantity = math.floor(max(0.0, sized_qty) * 100) / 100
                # Below T212's ~$1 fractional minimum → can't place a real order.
                if quantity * entry_price < 1.0:
                    undersized_msg = (
                        f"HOLD — position too small to place "
                        f"({quantity:.2f} sh ≈ ${quantity * entry_price:.2f}; "
                        f"need ≥ $1 notional / more free cash)"
                    )
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
            # Enforce the minimum risk:reward on new entries. The system is only
            # meant to take setups whose target is at least MIN_RISK_REWARD × the
            # risk; if the stop/target geometry doesn't clear that bar, hold
            # instead of entering. (Previously MIN_RISK_REWARD was used to *suggest*
            # an ATR target but never actually gated the trade.)
            if action == "BUY" and undersized_msg:
                result = ExecutionResult(
                    success=True, symbol=symbol, action="HOLD", quantity=0,
                    message=undersized_msg,
                )
            elif (action == "BUY" and risk_reward is not None
                    and risk_reward < Config.MIN_RISK_REWARD):
                result = ExecutionResult(
                    success=True, symbol=symbol, action="HOLD", quantity=0,
                    message=(f"HOLD — R:R {risk_reward:.2f} below minimum "
                             f"{Config.MIN_RISK_REWARD:.1f} "
                             f"(entry ${entry_price} / stop ${stop_price} / target ${target_price})"),
                )
            elif action == "BUY":
                result = self._execute_buy(symbol, quantity, stop_price, target_price, entry_price)
            elif action == "SELL" and symbol not in self._tracked_positions:
                # We don't hold/manage this symbol, so there's nothing to sell.
                # (Exits on held positions are handled mechanically by
                # check_and_execute_exits, not by an LLM SELL.) Treat as a HOLD
                # no-op instead of logging a doomed "insufficient position" order.
                result = ExecutionResult(
                    success=True, symbol=symbol, action="HOLD", quantity=0,
                    message="HOLD — no tracked position to sell",
                )
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
                        "average_price": p.average_price,
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

        # T212 returns instrument_code as "NFLX_US_EQ" — build both a T212-key and
        # a short-name-key map so we can look up whichever the caller stored.
        current_prices = {p.instrument_code: p.current_price for p in positions}
        results: List[ExecutionResult] = []

        today = datetime.utcnow().date()

        for symbol, tracking in list(self._tracked_positions.items()):
            t212_ticker = self.client._resolve_ticker(symbol)
            if t212_ticker not in current_prices:
                # Position closed externally / no longer held — stop tracking it.
                del self._tracked_positions[symbol]
                self._save_tracked()
                continue

            price = current_prices[t212_ticker]
            entry = tracking["entry_price"]
            hit   = None
            dirty = False

            # ── Trailing stop: let winners run to maximum result ──────────────
            # Track the high-water mark, then once we're up enough, trail a stop
            # behind the high instead of capping the gain at a fixed take-profit.
            if price > tracking.get("highest_price", entry):
                tracking["highest_price"] = price
                dirty = True

            if Config.TRAILING_STOP_ENABLED:
                if (not tracking.get("trailing_active")
                        and price >= entry * (1 + Config.TRAILING_ACTIVATION_PCT)):
                    tracking["trailing_active"] = True
                    dirty = True
                    logger.info(
                        f"  {symbol}: trailing stop ACTIVATED "
                        f"(+{Config.TRAILING_ACTIVATION_PCT:.0%}) — letting it run"
                    )

            if tracking.get("trailing_active"):
                # Trailing stop sits TRAILING_STOP_PCT below the high, but never
                # below the original hard stop — and, once trailing is active,
                # never below the entry price either, so a position that has run
                # +TRAILING_ACTIVATION_PCT can't come back to a loss. Take-profit
                # is disabled so the winner can still run as far as it wants.
                trail_stop = round(tracking["highest_price"] * (1 - Config.TRAILING_STOP_PCT), 4)
                effective_stop = max(trail_stop, tracking["stop_loss"], entry)
                if price <= effective_stop:
                    hit = "TRAIL_STOP"
            else:
                # Pre-activation: classic fixed stop-loss / take-profit.
                if price <= tracking["stop_loss"]:
                    hit = "STOP_LOSS"
                elif price >= tracking["take_profit"]:
                    hit = "TAKE_PROFIT"

            if dirty and not hit:
                self._save_tracked()

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
                # If the sell was blocked because markets are closed, keep tracking
                # so we retry on the next cycle when markets open.
                if getattr(result, "error", None) == "market_closed":
                    logger.info(
                        f"  {symbol}: {hit} triggered but market closed — "
                        "will retry next cycle"
                    )
                    continue
                if not result.success:
                    # Real failure (e.g. the position was closed externally) — do
                    # NOT fabricate a fill or log a phantom price-0 exit. Just stop
                    # tracking so we don't keep chasing a position we can't sell.
                    logger.warning(
                        f"  {symbol}: {hit} exit failed — {result.message}; untracking"
                    )
                    del self._tracked_positions[symbol]
                    self._save_tracked()
                    continue
                result.action = hit
                entry = tracking["entry_price"]
                pct   = round((price - entry) / entry * 100, 2)
                # Carry the figures on the result so callers don't have to scrape
                # them out of the message (and so they survive the tracked-position
                # delete that happens just below).
                result.entry_price = entry
                result.exit_price  = price
                result.pnl_pct     = pct
                if not result.price:
                    result.price = price   # ensure the exit fill price is recorded
                result.message = (
                    f"{hit}: sold {tracking['quantity']} {symbol} @ ${price:.4f} "
                    f"(entry ${entry:.4f}, {pct:+.2f}%)"
                )
                self._save_history(result)
                results.append(result)
                del self._tracked_positions[symbol]
                self._save_tracked()

        return results

    def get_tracked_positions(self) -> Dict[str, Dict[str, float]]:
        """Return a copy of the current SL/TP tracking state."""
        return dict(self._tracked_positions)

    def sync_with_broker(self) -> None:
        """
        Rebuild tracking for any live T212 holding we're not already tracking.

        The bot restarts every day when the PC powers on, which would otherwise
        wipe all stop-loss / trailing state held in memory. This re-adopts any
        position still open at the broker so it keeps being managed (using
        percentage-based stops seeded from the average entry price).
        """
        try:
            positions = self.client.get_positions()
        except Exception as e:
            logger.warning(f"sync_with_broker: could not fetch positions ({e})")
            return

        tracked_t212 = {self.client._resolve_ticker(s) for s in self._tracked_positions}
        adopted = 0
        for p in positions:
            if p.instrument_code in tracked_t212:
                continue
            if p.quantity <= 0 or p.average_price <= 0:
                continue
            short = self._short_name(p.instrument_code)
            entry = float(p.average_price)
            cur   = float(p.current_price or entry)
            self._tracked_positions[short] = {
                "entry_price":     entry,
                "stop_loss":       round(entry * (1 - Config.STOP_LOSS_PCT), 4),
                "take_profit":     round(entry * (1 + Config.TAKE_PROFIT_PCT), 4),
                "quantity":        float(p.quantity),
                "entry_date":      datetime.utcnow().strftime("%Y-%m-%d"),
                "highest_price":   max(entry, cur),
                "trailing_active": cur >= entry * (1 + Config.TRAILING_ACTIVATION_PCT),
            }
            adopted += 1
            logger.info(f"  Re-adopted {short}: entry ${entry:.2f}, qty {p.quantity}")
        if adopted:
            self._save_tracked()
            logger.info(f"sync_with_broker: now managing {len(self._tracked_positions)} position(s)")

    @staticmethod
    def _short_name(instrument_code: str) -> str:
        """'NFLX_US_EQ' -> 'NFLX'.  Pass-through if already short."""
        return instrument_code.split("_", 1)[0] if "_" in instrument_code else instrument_code

    def _load_tracked(self) -> Dict[str, Dict[str, float]]:
        if not os.path.exists(TRACKED_FILE):
            return {}
        try:
            with open(TRACKED_FILE, "r") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_tracked(self) -> None:
        try:
            with open(TRACKED_FILE, "w") as f:
                json.dump(self._tracked_positions, f, indent=2)
        except Exception:
            pass  # best-effort; never crash the bot over a write failure

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
        entry_price: float = 0.0,
    ) -> ExecutionResult:
        try:
            # T212 market-order endpoint returns 404 outside US market hours.
            if not _us_market_open():
                logger.info(f"  {symbol}: market closed — BUY not placed (re-evaluated when the market opens)")
                return ExecutionResult(
                    success=False, symbol=symbol, action="BUY", quantity=quantity,
                    message="Market closed — order not placed (US market hours: 9:30–16:00 ET)",
                    error="market_closed",
                )

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

            self._register_position(symbol, quantity, stop_price, target_price,
                                    expected_entry=entry_price)
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
        expected_entry: float = 0.0,
    ) -> None:
        """Record entry price, SL/TP levels, and entry date for a newly bought position.

        Retries the position lookup a few times so a slow fill still gets its
        stop/target attached. If the fill genuinely can't be confirmed, falls back
        to the expected entry price so the position is never left unmanaged.
        """
        t212_ticker = self.client._resolve_ticker(symbol)
        entry = None
        for _ in range(3):
            time.sleep(1)
            try:
                positions = self.client.get_positions()
                # T212 returns instrument_code as "NFLX_US_EQ" not "NFLX".
                pos = next((p for p in positions if p.instrument_code == t212_ticker), None)
                if pos and float(pos.average_price) > 0:
                    entry = float(pos.average_price)
                    break
            except Exception:
                pass

        if not entry or entry <= 0:
            # Couldn't confirm the fill — track using the expected entry so the
            # stop/target still protect the position instead of it going naked.
            entry = float(expected_entry or 0)
            if entry > 0:
                logger.warning(
                    f"  {symbol}: fill not confirmed — tracking SL/TP from expected "
                    f"entry ${entry:.4f}"
                )

        if not entry or entry <= 0:
            logger.warning(f"  {symbol}: no entry price available — position left untracked")
            return

        sl = stop_price  or round(entry * (1 - Config.STOP_LOSS_PCT), 4)
        tp = target_price or round(entry * (1 + Config.TAKE_PROFIT_PCT), 4)

        self._tracked_positions[symbol] = {
            "entry_price":     entry,
            "stop_loss":       sl,
            "take_profit":     tp,
            "quantity":        quantity,
            "entry_date":      datetime.utcnow().strftime("%Y-%m-%d"),
            "highest_price":   entry,    # high-water mark for the trailing stop
            "trailing_active": False,    # flips True once price clears the activation threshold
        }
        self._save_tracked()

    def _execute_sell(self, symbol: str, quantity: float) -> ExecutionResult:
        try:
            # T212 market-order endpoint returns 404 outside US market hours.
            if not _us_market_open():
                logger.info(f"  {symbol}: market closed — SELL will retry next cycle")
                return ExecutionResult(
                    success=False, symbol=symbol, action="SELL", quantity=quantity,
                    message="Market closed — order not placed (US market hours: 9:30–16:00 ET)",
                    error="market_closed",
                )

            positions = self.client.get_positions()
            # T212 returns instrument_code as "NFLX_US_EQ" not "NFLX" — resolve first.
            t212_ticker = self.client._resolve_ticker(symbol)
            position = next((p for p in positions if p.instrument_code == t212_ticker), None)

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
        if getattr(result, "error", None) == "market_closed":
            return  # Market-closed blocks are expected — don't fill history with them

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
