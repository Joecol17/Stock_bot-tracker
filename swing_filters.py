"""
swing_filters.py — Pre-trade quality gates for swing trading.

Four independent filters, each returning a pass/fail + metadata dict:
  1. market_regime   — is the broad market in an uptrend?
  2. earnings_clear  — no earnings report within the buffer window?
  3. relative_strength — is this stock outperforming its benchmark?
  4. setup_score     — composite technical quality score (0–100)

Each filter is designed to be defensive: a data failure → neutral / pass
(we do not block a trade just because yfinance timed out).

Usage:
    from swing_filters import run_all_filters
    result = run_all_filters("AAPL", context, Config)
    if result["filter_score"] < Config.MIN_FILTER_SCORE:
        skip()
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Market regime
# ---------------------------------------------------------------------------

_regime_cache: Dict[str, Any] = {}   # symbol → {data, fetched_at}
_REGIME_TTL_SECONDS = 3600           # re-fetch benchmark at most once per hour


def get_market_regime(benchmark: str = "SPY") -> Dict[str, Any]:
    """
    Return current market regime based on benchmark vs its 50- and 200-day SMAs.

    Returns:
      regime     — "bull" | "neutral" | "bear"
      above_sma50, above_sma200, price, sma50, sma200, benchmark
    """
    cached = _regime_cache.get(benchmark)
    if cached:
        age = (datetime.now() - cached["fetched_at"]).total_seconds()
        if age < _REGIME_TTL_SECONDS:
            return cached["data"]

    try:
        import yfinance as yf
        hist = yf.Ticker(benchmark).history(period="1y", interval="1d")
        if hist.empty or len(hist) < 50:
            raise ValueError("Insufficient data")

        close = hist["Close"]
        sma50  = float(close.rolling(50).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else sma50
        price  = float(close.iloc[-1])
        prev   = float(close.iloc[-2]) if len(close) > 1 else price
        day_chg = round((price - prev) / prev * 100, 2)

        above50  = price > sma50
        above200 = price > sma200

        if above50 and above200:
            regime = "bull"
        elif not above50 and not above200:
            regime = "bear"
        else:
            regime = "neutral"

        data = {
            "regime":       regime,
            "benchmark":    benchmark,
            "price":        round(price, 2),
            "day_change_pct": day_chg,
            "sma50":        round(sma50, 2),
            "sma200":       round(sma200, 2),
            "above_sma50":  above50,
            "above_sma200": above200,
            "ok":           True,
        }
    except Exception as e:
        logger.debug(f"Regime check failed for {benchmark}: {e}")
        data = {"regime": "unknown", "benchmark": benchmark, "ok": False, "error": str(e)}

    _regime_cache[benchmark] = {"data": data, "fetched_at": datetime.now()}
    return data


def regime_passes(regime_data: Dict[str, Any], strict: bool = False) -> bool:
    """
    Pass if market is bull or neutral.
    In strict mode, only bull passes (bear and neutral both block).
    On unknown (data error), always passes — don't penalise for connectivity issues.
    """
    r = regime_data.get("regime", "unknown")
    if r == "unknown":
        return True
    if strict:
        return r == "bull"
    return r in ("bull", "neutral")


# ---------------------------------------------------------------------------
# 2. Earnings avoidance
# ---------------------------------------------------------------------------

def days_to_earnings(symbol: str) -> Dict[str, Any]:
    """
    Return days until the next known earnings date.
    Returns skip=False on any data error (don't block when calendar unavailable).
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        cal = ticker.calendar

        if cal is None:
            return {"days_to_earnings": None, "skip": False}

        # calendar can be a DataFrame or a dict depending on yfinance version
        if hasattr(cal, "columns"):
            # DataFrame format
            for col in ("Earnings Date", "Earnings High", "Earnings Low"):
                if col in cal.columns:
                    dates = cal[col].dropna().tolist()
                    break
            else:
                dates = []
        elif isinstance(cal, dict):
            dates = cal.get("Earnings Date", [])
            if not isinstance(dates, list):
                dates = [dates]
        else:
            dates = []

        today = datetime.now().date()
        future = []
        for d in dates:
            try:
                dd = d.date() if hasattr(d, "date") else datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
                if dd >= today:
                    future.append(dd)
            except Exception:
                pass

        if not future:
            return {"days_to_earnings": None, "skip": False}

        next_date = min(future)
        days = (next_date - today).days
        return {
            "days_to_earnings":   days,
            "next_earnings_date": str(next_date),
            "skip":               False,  # caller applies buffer threshold
        }

    except Exception as e:
        logger.debug(f"Earnings check failed for {symbol}: {e}")
        return {"days_to_earnings": None, "skip": False}


# ---------------------------------------------------------------------------
# 3. Relative strength
# ---------------------------------------------------------------------------

def get_relative_strength(symbol: str, benchmark: str = "SPY", period_days: int = 20) -> Dict[str, Any]:
    """
    RS ratio = (symbol 20-day return) / (benchmark 20-day return).
    RS > 1.0 → symbol outperforming.  RS < 1.0 → underperforming.
    Returns rs=None on data error — caller treats None as neutral.
    """
    try:
        import yfinance as yf
        fetch_period = f"{period_days + 10}d"
        sym_hist = yf.Ticker(symbol).history(period=fetch_period, interval="1d")
        spy_hist = yf.Ticker(benchmark).history(period=fetch_period, interval="1d")

        if sym_hist.empty or spy_hist.empty or len(sym_hist) < 5:
            raise ValueError("Insufficient data")

        sym_ret = float(sym_hist["Close"].iloc[-1] / sym_hist["Close"].iloc[0]) - 1
        spy_ret = float(spy_hist["Close"].iloc[-1] / spy_hist["Close"].iloc[0]) - 1

        spy_factor = 1 + spy_ret
        rs = round((1 + sym_ret) / spy_factor, 4) if spy_factor != 0 else None

        return {
            "relative_strength":    rs,
            "symbol_return_pct":    round(sym_ret * 100, 2),
            "benchmark_return_pct": round(spy_ret * 100, 2),
            "outperforming":        (rs > 1.0) if rs is not None else None,
            "period_days":          period_days,
            "benchmark":            benchmark,
            "ok":                   True,
        }
    except Exception as e:
        logger.debug(f"Relative strength check failed for {symbol}: {e}")
        return {"relative_strength": None, "outperforming": None, "ok": False}


# ---------------------------------------------------------------------------
# 4. Technical setup score (0–100)
# ---------------------------------------------------------------------------

def score_setup(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score the technical setup quality on a 0–100 scale.
    Based purely on the market context dict produced by get_market_context().

    Scoring components (each 0–25):
      A. Trend alignment    — is price above SMA20, SMA50, SMA200?
      B. Momentum           — RSI zone + MACD direction
      C. Volume confirmation — recent volume vs average
      D. Risk/reward geometry — BB position, price vs support/resistance
    """
    score = 0
    notes = []

    # ── A: Trend alignment (0–25) ────────────────────────────────────────────
    trend_pts = 0
    price = context.get("price", 0) or 0

    if context.get("price_vs_sma20_pct") is not None:
        if context["price_vs_sma20_pct"] > 0:
            trend_pts += 7
            notes.append("above SMA20")
    if context.get("price_vs_sma50_pct") is not None:
        if context["price_vs_sma50_pct"] > 0:
            trend_pts += 8
            notes.append("above SMA50")
    if context.get("price_vs_sma200_pct") is not None:
        if context["price_vs_sma200_pct"] > 0:
            trend_pts += 10
            notes.append("above SMA200")
    score += min(trend_pts, 25)

    # ── B: Momentum (0–25) ──────────────────────────────────────────────────
    mom_pts = 0
    rsi = context.get("rsi_14")
    if rsi is not None:
        if 45 <= rsi <= 65:           # healthy momentum zone
            mom_pts += 12
            notes.append(f"RSI {rsi:.0f} healthy")
        elif 30 <= rsi < 45:           # oversold recovery — potential long setup
            mom_pts += 9
            notes.append(f"RSI {rsi:.0f} recovery zone")
        elif rsi < 30:                 # very oversold — risky
            mom_pts += 4
        elif 65 < rsi <= 75:           # approaching overbought
            mom_pts += 6

    macd_cross = context.get("macd_crossover")
    if macd_cross == "bullish":
        mom_pts += 13
        notes.append("MACD bullish cross")
    elif macd_cross == "neutral":
        mom_pts += 5

    score += min(mom_pts, 25)

    # ── C: Volume confirmation (0–25) ────────────────────────────────────────
    vol_label = context.get("volume", "normal")
    if vol_label == "high":
        score += 25
        notes.append("high volume")
    elif vol_label == "normal":
        score += 15
    else:
        score += 5
        notes.append("low volume")

    # ── D: Risk/reward geometry (0–25) ───────────────────────────────────────
    geo_pts = 0
    bb_pos = context.get("bb_position")
    if bb_pos is not None:
        if bb_pos < 0.3:               # near lower band — potential bounce
            geo_pts += 15
            notes.append("near BB lower (bounce setup)")
        elif 0.3 <= bb_pos <= 0.7:     # mid-range — trending
            geo_pts += 10
        # near upper band scores 0

    support = context.get("support_level", 0) or 0
    resistance = context.get("resistance_level", 0) or 0
    if price and support and resistance and resistance > support:
        distance_to_resistance = resistance - price
        full_range = resistance - support
        # Good if price has room to resistance (not already near top)
        if distance_to_resistance / full_range > 0.4:
            geo_pts += 10
            notes.append("room to resistance")

    score += min(geo_pts, 25)

    grade = "A" if score >= 75 else "B" if score >= 55 else "C" if score >= 35 else "D"

    return {
        "setup_score":   score,
        "setup_grade":   grade,
        "score_notes":   notes,
    }


# ---------------------------------------------------------------------------
# Master runner — call this before sending anything to the LLM
# ---------------------------------------------------------------------------

def run_all_filters(
    symbol:    str,
    context:   Dict[str, Any],
    benchmark: str = "SPY",
    earnings_buffer_days: int = 5,
    min_rs:    float = 0.95,
    strict_regime: bool = False,
) -> Dict[str, Any]:
    """
    Run all four filters and return a summary dict including:
      filter_score  — integer 0–4 (number of filters that passed)
      filters       — per-filter detail dicts
      regime        — cached regime dict
      skip_reason   — human-readable string if hard-blocked (earnings)
    """
    results: Dict[str, Any] = {"symbol": symbol, "filters": {}, "skip_reason": None}

    # 1. Market regime
    regime = get_market_regime(benchmark)
    regime_ok = regime_passes(regime, strict=strict_regime)
    results["filters"]["regime"] = {**regime, "pass": regime_ok}
    results["regime"] = regime

    # 2. Earnings avoidance
    earn = days_to_earnings(symbol)
    days_out = earn.get("days_to_earnings")
    earn_ok = days_out is None or days_out > earnings_buffer_days
    if not earn_ok:
        results["skip_reason"] = (
            f"Earnings in {days_out} day(s) on {earn.get('next_earnings_date', '?')} — skipping"
        )
    results["filters"]["earnings"] = {**earn, "pass": earn_ok}

    # 3. Relative strength
    rs_data = get_relative_strength(symbol, benchmark=benchmark)
    rs = rs_data.get("relative_strength")
    rs_ok = rs is None or rs >= min_rs   # None → data unavailable → don't penalise
    results["filters"]["relative_strength"] = {**rs_data, "pass": rs_ok}

    # 4. Technical setup score
    setup = score_setup(context)
    # Pass threshold: grade B or better (score ≥ 55)
    setup_ok = setup["setup_score"] >= 55
    results["filters"]["setup"] = {**setup, "pass": setup_ok}

    passed = sum([regime_ok, earn_ok, rs_ok, setup_ok])
    results["filter_score"] = passed
    results["filter_max"]   = 4
    results["filter_pct"]   = round(passed / 4 * 100)

    return results
