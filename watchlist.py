"""
Watchlist management and symbol screener.

WatchlistManager: a TWO-TIER watchlist —
  • core    — a large, permanently-tracked set (default 200 symbols) that the
              bot always screens. Stored in core_watchlist.json.
  • explore — up to EXPLORE_SLOTS (default 50) dynamic slots the discovery
              swarm fills with its best fresh finds and rotates over time.
              Stored in explore_watchlist.json with {symbol, score, reason,
              added_cycle, added_ts, pinned}.
  list_symbols() returns the union (core ∪ explore) — what the bot screens.
  watchlist.json is kept in sync with the union for any legacy reader.

Screener: scores symbols for 'activity'. score_many() batch-downloads the whole
  list in ONE threaded yfinance call (scales to hundreds of symbols); score_symbol()
  remains for single on-demand analysis.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from config import Config

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "AMD", "NFLX", "JPM"]

CORE_FILE = "core_watchlist.json"
EXPLORE_FILE = "explore_watchlist.json"


class WatchlistManager:
    """Two-tier watchlist: a permanent core set + dynamic explore slots."""

    def __init__(
        self,
        path: str = "watchlist.json",
        core_path: str = CORE_FILE,
        explore_path: str = EXPLORE_FILE,
    ) -> None:
        self.path = path
        self.core_path = core_path
        self.explore_path = explore_path
        self._core: List[str] = self._load_core()
        self._explore: List[dict] = self._load_explore()
        # Note: watchlist.json (the legacy union file) is only rewritten on
        # mutations, not on construction — the dashboard builds a fresh manager
        # per request, so writing here would thrash the file and race the bot.

    # ── back-compat: .symbols reads the union ────────────────────────────────
    @property
    def symbols(self) -> List[str]:
        return self.list_symbols()

    # ── core tier ────────────────────────────────────────────────────────────
    def _load_core(self) -> List[str]:
        if os.path.exists(self.core_path):
            try:
                with open(self.core_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    return [str(s).upper().strip() for s in data if s]
            except Exception as e:
                logger.warning(f"Could not load core watchlist: {e}")
        core = self._seed_core()
        self._save_core(core)
        logger.info(f"Seeded core watchlist with {len(core)} symbols")
        return core

    def _seed_core(self) -> List[str]:
        """Build the initial core: any existing watchlist.json first (so current
        symbols + open positions stay), then pad from the discovery universe."""
        size = max(1, getattr(Config, "CORE_WATCHLIST_SIZE", 200))
        seed: List[str] = []
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    old = json.load(f)
                if isinstance(old, list):
                    seed += [str(s).upper().strip() for s in old if s]
            except Exception:
                pass
        try:
            from discovery import StockUniverse, BUILTIN_UNIVERSE
            # Universe cache first, then the built-in list as a pad so a stale/small
            # universe.json can't leave the core short of CORE_WATCHLIST_SIZE.
            seed += StockUniverse().symbols()
            seed += BUILTIN_UNIVERSE
        except Exception as e:
            logger.warning(f"Core seed: could not load universe ({e}); using defaults")
            seed += list(DEFAULT_SYMBOLS)

        out: List[str] = []
        seen = set()
        for s in seed:
            s = str(s).upper().strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
            if len(out) >= size:
                break
        return out

    def _save_core(self, core: Optional[List[str]] = None) -> None:
        try:
            with open(self.core_path, "w") as f:
                json.dump(core if core is not None else self._core, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save core watchlist: {e}")

    # ── explore tier ─────────────────────────────────────────────────────────
    def _load_explore(self) -> List[dict]:
        if os.path.exists(self.explore_path):
            try:
                with open(self.explore_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    cleaned = []
                    for e in data:
                        if isinstance(e, dict) and e.get("symbol"):
                            e["symbol"] = str(e["symbol"]).upper().strip()
                            cleaned.append(e)
                        elif isinstance(e, str):
                            cleaned.append({"symbol": e.upper().strip(), "reason": "", "pinned": False})
                    return cleaned
            except Exception as e:
                logger.warning(f"Could not load explore watchlist: {e}")
        return []

    def _save_explore(self) -> None:
        try:
            with open(self.explore_path, "w") as f:
                json.dump(self._explore, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save explore watchlist: {e}")

    # ── queries ──────────────────────────────────────────────────────────────
    def core_symbols(self) -> List[str]:
        return list(self._core)

    def explore_symbols(self) -> List[str]:
        return [e["symbol"] for e in self._explore]

    def explore_meta(self) -> List[dict]:
        return [dict(e) for e in self._explore]

    def list_symbols(self) -> List[str]:
        seen = set()
        out: List[str] = []
        for s in self._core + self.explore_symbols():
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def is_core(self, symbol: str) -> bool:
        return symbol.upper().strip() in set(self._core)

    def explore_slots_free(self) -> int:
        return max(0, getattr(Config, "EXPLORE_SLOTS", 50) - len(self._explore))

    # ── mutations ──────────────────────────────────────────────────────────
    def add(self, symbol: str) -> bool:
        """Manual add (dashboard) → a pinned explore slot (won't be auto-evicted)."""
        return self.add_explore(symbol, reason="manual add", pinned=True)

    def add_explore(
        self,
        symbol: str,
        score: Optional[float] = None,
        reason: str = "",
        cycle: Optional[int] = None,
        pinned: bool = False,
    ) -> bool:
        symbol = symbol.upper().strip()
        if not symbol:
            return False
        if symbol in set(self._core) or symbol in self.explore_symbols():
            return False
        if len(self._explore) >= getattr(Config, "EXPLORE_SLOTS", 50):
            return False  # full — caller (Curator) must evict first
        self._explore.append({
            "symbol": symbol,
            "score": round(float(score), 2) if score is not None else None,
            "reason": reason or "",
            "added_cycle": cycle,
            "added_ts": datetime.utcnow().isoformat(),
            "pinned": bool(pinned),
        })
        self._save_explore()
        self._sync_legacy()
        return True

    def evict_explore(self, symbol: str, reason: str = "") -> bool:
        symbol = symbol.upper().strip()
        before = len(self._explore)
        self._explore = [e for e in self._explore if e["symbol"] != symbol]
        if len(self._explore) < before:
            self._save_explore()
            self._sync_legacy()
            return True
        return False

    def remove(self, symbol: str) -> bool:
        """Manual remove (dashboard): explore first, then core."""
        symbol = symbol.upper().strip()
        if self.evict_explore(symbol, reason="manual remove"):
            return True
        if symbol in set(self._core):
            self._core = [s for s in self._core if s != symbol]
            self._save_core()
            self._sync_legacy()
            return True
        return False

    def save(self) -> None:
        self._save_core()
        self._save_explore()
        self._sync_legacy()

    def _sync_legacy(self) -> None:
        """Keep watchlist.json == the union, so any legacy reader still works."""
        try:
            with open(self.path, "w") as f:
                json.dump(self.list_symbols(), f, indent=2)
        except Exception:
            pass


class Screener:
    """
    Lightweight activity screener.

    score_many() batch-downloads ALL symbols in one threaded yfinance call and
    scores each — this scales to hundreds of symbols (vs one HTTP call each).
    score_symbol() keeps the single-symbol path for on-demand analysis.

    Scoring rubric (higher = more interesting):
      +3  volume spike (last bar > 1.5x average)
      +2  MACD line crossed signal line in last 3 bars
      +2  RSI(14) below 35 (oversold) or above 65 (overbought)
      +1  absolute price change > 1% since previous bar
      +1  RSI(14) below 45 or above 55 (approaching extremes)
    """

    @staticmethod
    def _score_frame(close, volume) -> float:
        """Score from a single symbol's close/volume series. 0.0 on short data."""
        import ta
        if close is None or volume is None or len(close) < 15:
            return 0.0
        score = 0.0
        avg_vol = float(volume.mean())
        last_vol = float(volume.iloc[-1])
        if avg_vol > 0 and last_vol > avg_vol * 1.5:
            score += 3
        prev = float(close.iloc[-2]) if len(close) > 1 else float(close.iloc[-1])
        curr = float(close.iloc[-1])
        change_pct = abs((curr - prev) / prev * 100) if prev else 0
        if change_pct > 1.0:
            score += 1
        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi().dropna()
        if len(rsi_series) > 0:
            rsi = float(rsi_series.iloc[-1])
            if rsi < 35 or rsi > 65:
                score += 2
            elif rsi < 45 or rsi > 55:
                score += 1
        if len(close) >= 30:
            macd_obj = ta.trend.MACD(close, window_fast=12, window_slow=26, window_sign=9)
            macd_line = macd_obj.macd().dropna()
            signal_line = macd_obj.macd_signal().dropna()
            if len(macd_line) >= 3 and len(signal_line) >= 3:
                for i in [-3, -2, -1]:
                    prev_diff = float(macd_line.iloc[i - 1]) - float(signal_line.iloc[i - 1])
                    curr_diff = float(macd_line.iloc[i]) - float(signal_line.iloc[i])
                    if prev_diff * curr_diff < 0:
                        score += 2
                        break
        return score

    def score_symbol(self, symbol: str) -> float:
        """Activity score for a single symbol (one HTTP call). 0.0 on error."""
        try:
            import yfinance as yf
            hist = yf.Ticker(symbol).history(period="5d", interval="1h")
            if hist.empty:
                return 0.0
            return self._score_frame(hist["Close"], hist["Volume"])
        except Exception as e:
            logger.debug(f"Screener error for {symbol}: {e}")
            return 0.0

    def score_many(self, symbols: List[str]) -> Dict[str, float]:
        """Batch-download all symbols in ONE threaded call and score each.

        Returns {symbol: score}. Scales to hundreds of symbols — this is what
        makes a 200+ watchlist practical. Falls back to 0.0 on per-symbol errors.
        """
        scores: Dict[str, float] = {s: 0.0 for s in symbols}
        if not symbols:
            return scores
        try:
            import yfinance as yf
            raw = yf.download(
                tickers=" ".join(symbols),
                period="5d",
                interval="1h",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
        except Exception as e:
            logger.warning(f"Screener batch download failed: {e}")
            return scores

        single = len(symbols) == 1
        for symbol in symbols:
            try:
                if single:
                    close = raw["Close"].dropna()
                    volume = raw["Volume"].dropna()
                else:
                    df = raw[symbol]
                    close = df["Close"].dropna()
                    volume = df["Volume"].dropna()
                scores[symbol] = round(self._score_frame(close, volume), 2)
            except Exception:
                scores[symbol] = 0.0
        return scores

    def top_symbols(
        self,
        symbols: List[str],
        n: int = 5,
        always_include: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Score all symbols (batched) and return the top n by activity.
        Symbols in always_include (e.g. open tracked positions) are guaranteed
        to appear regardless of score.
        """
        always = set(s.upper() for s in (always_include or []))
        candidates = [s for s in symbols if s.upper() not in always]

        scores = self.score_many(candidates)
        ranked = sorted(candidates, key=lambda s: scores.get(s, 0.0), reverse=True)

        # always_include first (only those actually in the list), then top scorers
        result = [s for s in symbols if s.upper() in always]
        remaining_slots = max(0, n - len(result))
        result += ranked[:remaining_slots]

        top_preview = ", ".join(f"{s}={scores.get(s, 0):.0f}" for s in result[:12])
        logger.info(
            f"Screener: {len(symbols)} symbols -> {len(result)} selected "
            f"(top: {top_preview}{' …' if len(result) > 12 else ''})"
        )
        return result
