"""
Stock discovery system.

Scans a broad universe of liquid stocks and surfaces the highest-activity
candidates to auto-populate the watchlist. Uses a two-pass approach:

  Pass 1 (fast) — batch download 5d/1h data for the full universe,
                  score by price momentum and volume spike only.
  Pass 2 (full) — run the Screener (RSI + MACD) on the top 30 from pass 1,
                  return the top N by combined score.

The universe defaults to ~150 liquid US stocks across sectors. It can be
refreshed from Wikipedia's S&P 500 list and is cached in universe.json.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

UNIVERSE_CACHE_FILE = "universe.json"

# Built-in fallback universe — liquid stocks across major sectors
BUILTIN_UNIVERSE = [
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "AMZN", "TSLA",
    "AMD", "INTC", "QCOM", "AVGO", "TXN", "MU", "AMAT", "LRCX",
    "KLAC", "MRVL", "NXPI", "ADI", "SNPS", "CDNS", "FTNT", "PANW",
    "CRM", "ORCL", "SAP", "INTU", "ADBE", "NOW", "WDAY", "SNOW",
    "PLTR", "NET", "DDOG", "ZS", "CRWD", "OKTA", "MDB", "TEAM",
    # Consumer
    "NFLX", "DIS", "CMCSA", "CHTR", "WBD", "SPOT",
    "AMZN", "HD", "LOW", "TGT", "WMT", "COST", "MCD", "SBUX",
    "NKE", "LULU", "TJX", "ROST", "YUM", "CMG",
    # Finance
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW",
    "AXP", "V", "MA", "PYPL", "COF", "USB", "PNC",
    "BX", "KKR", "APO", "ARES",
    # Healthcare
    "JNJ", "UNH", "LLY", "PFE", "MRK", "ABBV", "TMO", "ABT",
    "DHR", "MDT", "SYK", "BSX", "ISRG", "EW", "IDXX",
    "REGN", "VRTX", "BIIB", "GILD", "AMGN",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX",
    "VLO", "OXY", "HAL", "BKR",
    # Industrials / Materials
    "CAT", "DE", "HON", "GE", "RTX", "LMT", "NOC", "BA",
    "UPS", "FDX", "CSX", "NSC", "GD", "MMM", "EMR", "ETN",
    "FCX", "NEM", "NUE", "ALB",
    # ETFs (high liquidity, useful signals)
    "SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "XLV", "XLI",
]

# Deduplicate while preserving order
_seen: set = set()
BUILTIN_UNIVERSE = [s for s in BUILTIN_UNIVERSE if not (s in _seen or _seen.add(s))]


class StockUniverse:
    """Manages the set of stocks to scan. Cached in universe.json."""

    def __init__(self, cache_path: str = UNIVERSE_CACHE_FILE) -> None:
        self.cache_path = cache_path
        self._symbols: List[str] = self._load()

    def _load(self) -> List[str]:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    return [str(s).upper().strip() for s in data if s]
            except Exception as e:
                logger.warning(f"Could not load universe cache: {e}")
        return list(BUILTIN_UNIVERSE)

    def _save(self) -> None:
        try:
            with open(self.cache_path, "w") as f:
                json.dump(self._symbols, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save universe cache: {e}")

    def symbols(self) -> List[str]:
        return list(self._symbols)

    def refresh_from_sp500(self) -> int:
        """
        Fetch the current S&P 500 list from Wikipedia and update the cache.
        Requires pandas + lxml (pip install lxml).
        Returns the number of symbols in the updated universe.
        """
        try:
            import pandas as pd
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            df = pd.read_html(url, attrs={"id": "constituents"})[0]
            symbols = df["Symbol"].str.replace(".", "-", regex=False).str.upper().tolist()
            self._symbols = symbols
            self._save()
            logger.info(f"Universe refreshed from Wikipedia: {len(symbols)} symbols")
            return len(symbols)
        except Exception as e:
            logger.warning(f"Could not refresh S&P 500 universe: {e}. Using cached/built-in list.")
            return len(self._symbols)


class StockDiscovery:
    """
    Two-pass discovery engine.

    Pass 1: batch yfinance download → fast score (price momentum + volume).
    Pass 2: full Screener (RSI + MACD) on top 30 from pass 1.
    Returns the top_n symbols with the highest combined score.
    """

    def __init__(self, universe: Optional[StockUniverse] = None) -> None:
        self.universe = universe or StockUniverse()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_opportunities(
        self,
        top_n: int = 10,
        exclude: Optional[List[str]] = None,
    ) -> List[Tuple[str, float]]:
        """
        Scan the full universe and return the top_n symbols sorted by score,
        as (symbol, score) tuples.  Symbols in `exclude` are skipped.
        """
        exclude_set = set(s.upper() for s in (exclude or []))
        candidates = [s for s in self.universe.symbols() if s not in exclude_set]

        if not candidates:
            return []

        logger.info(f"Discovery: scanning {len(candidates)} symbols (pass 1)...")
        pass1_scores = self._pass1_fast(candidates)

        # Take top 30 for full analysis
        top30 = sorted(pass1_scores, key=lambda t: t[1], reverse=True)[:30]
        top30_symbols = [s for s, _ in top30]

        logger.info(f"Discovery: running full screener on {len(top30_symbols)} candidates (pass 2)...")
        from watchlist import Screener
        screener = Screener()
        final_scores: List[Tuple[str, float]] = []
        for symbol in top30_symbols:
            p1 = dict(pass1_scores).get(symbol, 0)
            p2 = screener.score_symbol(symbol)
            combined = p1 + p2
            final_scores.append((symbol, combined))
            logger.debug(f"  {symbol}: pass1={p1:.1f} pass2={p2:.1f} total={combined:.1f}")

        final_scores.sort(key=lambda t: t[1], reverse=True)
        result = final_scores[:top_n]
        logger.info(
            f"Discovery complete. Top picks: "
            + ", ".join(f"{s}({sc:.0f})" for s, sc in result)
        )
        return result

    def auto_populate_watchlist(
        self,
        watchlist,  # WatchlistManager
        top_n: int = 10,
        max_watchlist_size: int = 20,
    ) -> List[str]:
        """
        Discover top_n opportunities and add any not already on the watchlist.
        Respects max_watchlist_size — won't add beyond that limit.
        Returns list of newly added symbols.
        """
        current = set(watchlist.list_symbols())
        available_slots = max(0, max_watchlist_size - len(current))
        if available_slots == 0:
            logger.info("Discovery: watchlist is at max size, skipping auto-add")
            return []

        opportunities = self.find_opportunities(top_n=top_n + len(current), exclude=list(current))
        added: List[str] = []
        for symbol, score in opportunities:
            if len(added) >= available_slots:
                break
            if watchlist.add(symbol):
                added.append(symbol)
                logger.info(f"Discovery: added {symbol} to watchlist (score={score:.1f})")

        return added

    # ------------------------------------------------------------------
    # Pass 1 — fast batch scan
    # ------------------------------------------------------------------

    def _pass1_fast(self, symbols: List[str]) -> List[Tuple[str, float]]:
        """
        Batch-download 2 days of hourly data for all symbols at once.
        Score by: abs(change_pct) and volume ratio. Returns (symbol, score) list.
        """
        try:
            import yfinance as yf

            # Batch download — much faster than individual Ticker calls
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
            logger.warning(f"Batch download failed: {e}")
            return [(s, 0.0) for s in symbols]

        scores: List[Tuple[str, float]] = []
        for symbol in symbols:
            try:
                # Multi-ticker download nests data under ticker key
                if len(symbols) == 1:
                    close = raw["Close"].dropna()
                    volume = raw["Volume"].dropna()
                else:
                    close = raw[symbol]["Close"].dropna()
                    volume = raw[symbol]["Volume"].dropna()

                if len(close) < 2:
                    scores.append((symbol, 0.0))
                    continue

                curr = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                change_pct = abs((curr - prev) / prev * 100) if prev else 0

                avg_vol = float(volume.mean())
                last_vol = float(volume.iloc[-1])
                vol_ratio = (last_vol / avg_vol) if avg_vol > 0 else 1.0

                score = change_pct * 0.5 + max(0.0, (vol_ratio - 1.0)) * 2.0
                scores.append((symbol, round(score, 4)))

            except Exception:
                scores.append((symbol, 0.0))

        return scores
