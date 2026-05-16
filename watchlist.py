"""
Watchlist management and symbol screener.

WatchlistManager: persist a list of ticker symbols to/from a JSON file.
Screener: quickly score all watchlist symbols and return the top N most
          active ones per cycle, avoiding full 60-day data fetches for
          every symbol on every run.
"""

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "AMD", "NFLX", "JPM"]


class WatchlistManager:
    """Load, save, and manage a list of ticker symbols."""

    def __init__(self, path: str = "watchlist.json") -> None:
        self.path = path
        self.symbols: List[str] = self._load()

    def _load(self) -> List[str]:
        if not os.path.exists(self.path):
            return list(DEFAULT_SYMBOLS)
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(s).upper().strip() for s in data if s]
        except Exception as e:
            logger.warning(f"Could not load watchlist from {self.path}: {e}")
        return list(DEFAULT_SYMBOLS)

    def save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump(self.symbols, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save watchlist: {e}")

    def add(self, symbol: str) -> bool:
        symbol = symbol.upper().strip()
        if symbol in self.symbols:
            return False
        self.symbols.append(symbol)
        self.save()
        return True

    def remove(self, symbol: str) -> bool:
        symbol = symbol.upper().strip()
        if symbol not in self.symbols:
            return False
        self.symbols.remove(symbol)
        self.save()
        return True

    def list_symbols(self) -> List[str]:
        return list(self.symbols)


class Screener:
    """
    Lightweight screener — fetches 5 days of hourly data per symbol and
    scores each one for 'activity'. Only top-scoring symbols proceed to
    full analysis, keeping API calls and Ollama usage lean.

    Scoring rubric (higher = more interesting):
      +3  volume spike (last bar > 1.5x average)
      +2  MACD line crossed signal line in last 3 bars
      +2  RSI(14) below 35 (oversold) or above 65 (overbought)
      +1  absolute price change > 1% since previous close
      +1  RSI(14) below 45 or above 55 (approaching extremes)
    """

    def score_symbol(self, symbol: str) -> float:
        """Return an activity score for symbol. Returns 0.0 on any error."""
        try:
            import yfinance as yf
            import ta

            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d", interval="1h")
            if hist.empty or len(hist) < 15:
                return 0.0

            close = hist["Close"]
            volume = hist["Volume"]
            score = 0.0

            # Volume spike
            avg_vol = float(volume.mean())
            last_vol = float(volume.iloc[-1])
            if avg_vol > 0 and last_vol > avg_vol * 1.5:
                score += 3

            # Price momentum
            prev = float(close.iloc[-2]) if len(close) > 1 else float(close.iloc[-1])
            curr = float(close.iloc[-1])
            change_pct = abs((curr - prev) / prev * 100) if prev else 0
            if change_pct > 1.0:
                score += 1

            # RSI
            rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi().dropna()
            if len(rsi_series) > 0:
                rsi = float(rsi_series.iloc[-1])
                if rsi < 35 or rsi > 65:
                    score += 2
                elif rsi < 45 or rsi > 55:
                    score += 1

            # MACD crossover in last 3 bars
            if len(close) >= 30:
                macd_obj = ta.trend.MACD(close, window_fast=12, window_slow=26, window_sign=9)
                macd_line = macd_obj.macd().dropna()
                signal_line = macd_obj.macd_signal().dropna()
                if len(macd_line) >= 3 and len(signal_line) >= 3:
                    for i in [-3, -2, -1]:
                        prev_diff = float(macd_line.iloc[i - 1]) - float(signal_line.iloc[i - 1])
                        curr_diff = float(macd_line.iloc[i]) - float(signal_line.iloc[i])
                        if prev_diff * curr_diff < 0:  # sign change = crossover
                            score += 2
                            break

            return score

        except Exception as e:
            logger.debug(f"Screener error for {symbol}: {e}")
            return 0.0

    def top_symbols(
        self,
        symbols: List[str],
        n: int = 5,
        always_include: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Score all symbols and return the top n by activity score.
        Symbols in always_include (e.g. open tracked positions) are
        guaranteed to appear regardless of score.
        """
        always = set(s.upper() for s in (always_include or []))
        candidates = [s for s in symbols if s.upper() not in always]

        scores: Dict[str, float] = {}
        for symbol in candidates:
            scores[symbol] = self.score_symbol(symbol)
            logger.debug(f"  Screener: {symbol} score={scores[symbol]:.1f}")

        ranked = sorted(candidates, key=lambda s: scores[s], reverse=True)

        # Fill slots: always_include first, then top scorers up to n
        result = list(always.intersection(symbols))
        remaining_slots = max(0, n - len(result))
        result += ranked[:remaining_slots]

        logger.info(
            f"Screener: {len(symbols)} symbols -> {len(result)} selected "
            f"(scores: {', '.join(f'{s}={scores.get(s, 0):.0f}' for s in result)})"
        )
        return result
