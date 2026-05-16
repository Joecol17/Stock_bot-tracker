"""
Backtesting engine.

Replays historical daily data through the same decision logic the live bot uses,
without touching the Trading 212 API.

Two modes:
  AI mode (use_ai=True)   — real Ollama calls. Authentic but slow (~2-3s/bar).
  Rule mode (use_ai=False) — fast RSI/MACD rules. Good for parameter sweeps.

Rule-based logic:
  BUY  when RSI < 35  OR  MACD bullish crossover (and not already long)
  SELL when RSI > 65  OR  MACD bearish crossover (and long)
  HOLD otherwise
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

WARMUP_BARS = 55  # bars discarded at start so all indicators are valid


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BacktestTrade:
    symbol: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: float
    exit_reason: str   # SELL / STOP_LOSS / TAKE_PROFIT / END_OF_PERIOD
    pnl: float
    pnl_pct: float


@dataclass
class BacktestResult:
    symbol: str
    period: str
    initial_capital: float
    final_value: float
    total_return_pct: float
    trades: List[BacktestTrade]
    win_count: int
    loss_count: int
    win_rate_pct: float
    max_drawdown_pct: float
    bars_tested: int

    def print_summary(self) -> None:
        print("\n" + "=" * 65)
        print(f"  BACKTEST RESULTS — {self.symbol}  ({self.period})")
        print("=" * 65)
        print(f"  Initial capital : ${self.initial_capital:,.2f}")
        print(f"  Final value     : ${self.final_value:,.2f}")
        ret_sign = "+" if self.total_return_pct >= 0 else ""
        print(f"  Total return    : {ret_sign}{self.total_return_pct:.2f}%")
        print(f"  Max drawdown    : {self.max_drawdown_pct:.2f}%")
        print(f"  Trades          : {len(self.trades)}  "
              f"(W:{self.win_count} L:{self.loss_count}  "
              f"win rate {self.win_rate_pct:.0f}%)")
        print(f"  Bars tested     : {self.bars_tested}")
        if self.trades:
            print("\n  --- Trade log ---")
            print(f"  {'Date':<12} {'Action':<14} {'Entry':>8} {'Exit':>8} {'P/L':>8}")
            print("  " + "-" * 56)
            for t in self.trades:
                sign = "+" if t.pnl >= 0 else ""
                print(
                    f"  {t.entry_date:<12} {t.exit_reason:<14} "
                    f"${t.entry_price:>7.2f} ${t.exit_price:>7.2f} "
                    f"{sign}{t.pnl_pct:.2f}%"
                )
        print("=" * 65 + "\n")


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class BacktestEngine:

    def __init__(
        self,
        decision_engine=None,   # DecisionEngine instance (required for AI mode)
        stop_loss_pct: float = 0.03,
        take_profit_pct: float = 0.05,
    ) -> None:
        self.decision_engine = decision_engine
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(
        self,
        symbol: str,
        period: str = "6mo",
        initial_capital: float = 10_000.0,
        quantity: float = 1.0,
        use_ai: bool = False,
    ) -> BacktestResult:
        """
        Run a backtest for one symbol.

        Args:
            symbol:          Ticker symbol, e.g. "AAPL"
            period:          yfinance period string: "3mo", "6mo", "1y", "2y"
            initial_capital: Starting cash in account currency
            quantity:        Fixed shares per trade
            use_ai:          True = Ollama decisions, False = rule-based (fast)
        """
        hist = self._fetch(symbol, period)
        if hist is None or len(hist) <= WARMUP_BARS:
            raise ValueError(
                f"Not enough data for {symbol} (period={period}). "
                "Try a longer period or check the symbol."
            )

        cash = initial_capital
        position: Optional[_Position] = None
        trades: List[BacktestTrade] = []
        portfolio_values: List[float] = []

        test_bars = hist.iloc[WARMUP_BARS:]
        total = len(test_bars)

        for idx in range(total):
            global_idx = WARMUP_BARS + idx
            row = hist.iloc[global_idx]
            date_str = str(row.name.date())
            close = float(row["Close"])
            high = float(row["High"])
            low = float(row["Low"])

            # Check SL/TP on open position using intraday high/low
            if position:
                exit_reason, exit_price = self._check_sl_tp(position, high, low, close)
                if exit_reason:
                    trade, cash = self._close_position(
                        position, exit_price, date_str, exit_reason, cash
                    )
                    trades.append(trade)
                    position = None

            # Get decision for this bar (one call covers both buy and sell logic)
            context = self._build_context(symbol, hist, global_idx)
            action = self._get_action(context, symbol, use_ai)

            if position is None and action == "BUY":
                cost = close * quantity
                if cash >= cost:
                    cash -= cost
                    position = _Position(
                        symbol=symbol,
                        entry_price=close,
                        entry_date=date_str,
                        quantity=quantity,
                        stop_loss=round(close * (1 - self.stop_loss_pct), 4),
                        take_profit=round(close * (1 + self.take_profit_pct), 4),
                    )
            elif position is not None and action == "SELL":
                trade, cash = self._close_position(
                    position, close, date_str, "SELL", cash
                )
                trades.append(trade)
                position = None

            # Portfolio value snapshot
            pos_value = position.quantity * close if position else 0.0
            portfolio_values.append(cash + pos_value)

            if (idx + 1) % 20 == 0:
                logger.info(f"  {symbol}: {idx + 1}/{total} bars processed...")

        # Close any open position at end of period
        if position:
            final_close = float(hist.iloc[-1]["Close"])
            final_date = str(hist.iloc[-1].name.date())
            trade, cash = self._close_position(
                position, final_close, final_date, "END_OF_PERIOD", cash
            )
            trades.append(trade)

        final_value = portfolio_values[-1] if portfolio_values else initial_capital
        total_return = (final_value - initial_capital) / initial_capital * 100

        winning = [t for t in trades if t.pnl > 0]
        losing  = [t for t in trades if t.pnl <= 0]
        win_rate = len(winning) / len(trades) * 100 if trades else 0.0
        max_dd = self._max_drawdown(portfolio_values, initial_capital)

        return BacktestResult(
            symbol=symbol,
            period=period,
            initial_capital=initial_capital,
            final_value=round(final_value, 2),
            total_return_pct=round(total_return, 2),
            trades=trades,
            win_count=len(winning),
            loss_count=len(losing),
            win_rate_pct=round(win_rate, 1),
            max_drawdown_pct=round(max_dd, 2),
            bars_tested=total,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch(self, symbol: str, period: str):
        try:
            import yfinance as yf
            # Download extra warmup data so indicators are valid from bar 0
            ticker = yf.Ticker(symbol)
            # Map period to a longer one that includes warmup
            extended = {"3mo": "6mo", "6mo": "1y", "1y": "2y", "2y": "5y"}.get(period, "1y")
            hist = ticker.history(period=extended, interval="1d", auto_adjust=True)
            if hist.empty:
                return None
            return hist
        except Exception as e:
            logger.error(f"Could not fetch data for {symbol}: {e}")
            return None

    def _build_context(self, symbol: str, hist, idx: int) -> Dict[str, Any]:
        """Build the same context dict as get_market_context, but from a hist slice."""
        try:
            import ta

            slice_ = hist.iloc[: idx + 1]
            close = slice_["Close"]
            high = slice_["High"]
            low = slice_["Low"]
            volume = slice_["Volume"]

            curr = float(close.iloc[-1])
            prev = float(close.iloc[-2]) if len(close) > 1 else curr
            change_pct = round((curr - prev) / prev * 100, 2) if prev else 0

            closes_5 = close.tail(5).tolist()
            if len(closes_5) >= 2:
                if closes_5[-1] > closes_5[0] * 1.01:
                    trend = "uptrend"
                elif closes_5[-1] < closes_5[0] * 0.99:
                    trend = "downtrend"
                else:
                    trend = "neutral"
            else:
                trend = "neutral"

            avg_vol = float(volume.mean())
            last_vol = float(volume.iloc[-1])
            if avg_vol > 0:
                vol_label = "high" if last_vol > avg_vol * 1.5 else ("low" if last_vol < avg_vol * 0.5 else "normal")
            else:
                vol_label = "normal"

            def _f(series, i=-1):
                try:
                    v = float(series.iloc[i])
                    return round(v, 4) if v == v else None
                except Exception:
                    return None

            rsi = _f(ta.momentum.RSIIndicator(close, window=14).rsi())
            macd_obj = ta.trend.MACD(close, window_fast=12, window_slow=26, window_sign=9)
            macd_line = _f(macd_obj.macd())
            macd_signal = _f(macd_obj.macd_signal())
            macd_hist = _f(macd_obj.macd_diff())
            sma20 = _f(ta.trend.SMAIndicator(close, window=20).sma_indicator())
            sma50 = _f(ta.trend.SMAIndicator(close, window=50).sma_indicator())
            bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
            bb_upper = _f(bb.bollinger_hband())
            bb_lower = _f(bb.bollinger_lband())

            crossover = None
            if macd_line is not None and macd_signal is not None:
                crossover = "bullish" if macd_line > macd_signal else ("bearish" if macd_line < macd_signal else "neutral")

            bb_pos = None
            if bb_upper and bb_lower and bb_upper != bb_lower:
                bb_pos = round((curr - bb_lower) / (bb_upper - bb_lower), 4)

            return {
                "symbol": symbol,
                "price": round(curr, 4),
                "prev_close": round(prev, 4),
                "change_pct": change_pct,
                "trend": trend,
                "volume": vol_label,
                "support_level": round(float(low.tail(20).min()), 4),
                "resistance_level": round(float(high.tail(20).max()), 4),
                "risk_tolerance": "medium",
                "rsi_14": rsi,
                "macd_line": macd_line,
                "macd_signal": macd_signal,
                "macd_histogram": macd_hist,
                "macd_crossover": crossover,
                "sma_20": sma20,
                "sma_50": sma50,
                "price_vs_sma20_pct": round((curr / sma20 - 1) * 100, 2) if sma20 else None,
                "price_vs_sma50_pct": round((curr / sma50 - 1) * 100, 2) if sma50 else None,
                "bb_upper": bb_upper,
                "bb_lower": bb_lower,
                "bb_position": bb_pos,
            }
        except Exception as e:
            logger.debug(f"Context build error at idx {idx}: {e}")
            return {"symbol": symbol, "price": float(hist.iloc[idx]["Close"]), "risk_tolerance": "medium"}

    def _get_action(self, context: Dict[str, Any], symbol: str, use_ai: bool) -> str:
        if use_ai:
            if self.decision_engine is None:
                raise ValueError("decision_engine is required for AI mode.")
            try:
                question = f"Should the system buy, sell, or hold {symbol}?"
                result = self.decision_engine.make_decision(context, question)
                inner = result.get("decision", {})
                if isinstance(inner, dict):
                    action = inner.get("action", "HOLD").upper()
                    if action in ("BUY", "SELL", "HOLD"):
                        return action
                return "HOLD"
            except Exception as e:
                logger.warning(f"AI decision error: {e}. Defaulting to HOLD.")
                return "HOLD"

        # Rule-based fallback
        return self._rule_decision(context)

    @staticmethod
    def _rule_decision(context: Dict[str, Any]) -> str:
        rsi = context.get("rsi_14")
        crossover = context.get("macd_crossover")
        bb_pos = context.get("bb_position")

        buy_signals = 0
        sell_signals = 0

        if rsi is not None:
            if rsi < 35:
                buy_signals += 2
            elif rsi < 45:
                buy_signals += 1
            elif rsi > 65:
                sell_signals += 2
            elif rsi > 55:
                sell_signals += 1

        if crossover == "bullish":
            buy_signals += 2
        elif crossover == "bearish":
            sell_signals += 2

        if bb_pos is not None:
            if bb_pos < 0.2:
                buy_signals += 1
            elif bb_pos > 0.8:
                sell_signals += 1

        if buy_signals >= 3:
            return "BUY"
        if sell_signals >= 3:
            return "SELL"
        return "HOLD"

    def _check_sl_tp(
        self, pos: "_Position", high: float, low: float, close: float
    ) -> Tuple[Optional[str], float]:
        if low <= pos.stop_loss:
            return "STOP_LOSS", min(pos.stop_loss, close)
        if high >= pos.take_profit:
            return "TAKE_PROFIT", max(pos.take_profit, close)
        return None, close

    @staticmethod
    def _close_position(
        pos: "_Position", price: float, date: str, reason: str, cash: float
    ) -> Tuple[BacktestTrade, float]:
        proceeds = price * pos.quantity
        cash += proceeds
        pnl = proceeds - pos.entry_price * pos.quantity
        pnl_pct = (price - pos.entry_price) / pos.entry_price * 100
        trade = BacktestTrade(
            symbol=pos.symbol,
            entry_date=pos.entry_date,
            exit_date=date,
            entry_price=pos.entry_price,
            exit_price=price,
            quantity=pos.quantity,
            exit_reason=reason,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
        )
        return trade, cash

    @staticmethod
    def _max_drawdown(values: List[float], initial: float) -> float:
        if not values:
            return 0.0
        peak = initial
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return max_dd


@dataclass
class _Position:
    symbol: str
    entry_price: float
    entry_date: str
    quantity: float
    stop_loss: float
    take_profit: float
