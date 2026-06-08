"""
equity_tracker.py — records portfolio equity over time and projects future profit.

Stores ONE row per calendar day in equity_history.json (the latest value seen
that day overwrites earlier ones), which keeps the file tiny while giving a clean
daily equity curve to extrapolate from.

Projections use a least-squares linear fit of the daily equity curve (avg $/day),
which is robust and won't explode the way compounding a noisy daily return can on
a small sample. Day / month / year are 1 / 21 / 252 trading days ahead.
"""

import json
import os
from datetime import datetime, date
from typing import Any, Dict, List

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "equity_history.json")

# Trading-day horizons for the projections
_DAYS_MONTH = 21
_DAYS_YEAR  = 252


def _load() -> List[Dict[str, Any]]:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(data: List[Dict[str, Any]]) -> None:
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass  # best-effort — never crash the bot over a write failure


def record_snapshot(total_value: float, cash: float = 0.0) -> None:
    """Record today's portfolio equity. Updates today's row if it already exists."""
    try:
        total_value = float(total_value)
    except (TypeError, ValueError):
        return
    if total_value <= 0:
        return

    data  = _load()
    today = date.today().isoformat()
    now   = datetime.now().isoformat(timespec="seconds")
    row   = {"date": today, "value": round(total_value, 2),
             "cash": round(float(cash or 0), 2), "ts": now}

    if data and data[-1].get("date") == today:
        data[-1] = row            # overwrite today's snapshot with the latest
    else:
        data.append(row)          # new day

    _save(data[-400:])            # keep ~13 months of daily history


def compute_projections() -> Dict[str, Any]:
    """
    Project day / month / year profit from the recorded daily equity curve.

    Returns a dict the dashboard can render directly. When there isn't enough
    history yet, returns {"ready": False, ...} so the UI can show a friendly
    "collecting data" state instead of a misleading number.
    """
    data  = [d for d in _load() if d.get("value")]
    n     = len(data)

    if n < 2:
        return {
            "ready": False,
            "days_tracked": n,
            "message": "Collecting data — projections need at least 2 days of history.",
        }

    values = [float(d["value"]) for d in data]
    start, current = values[0], values[-1]

    # ── Least-squares slope of equity vs. day index ($ per trading day) ──────
    xs      = list(range(n))
    mean_x  = sum(xs) / n
    mean_y  = sum(values) / n
    num     = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    den     = sum((xs[i] - mean_x) ** 2 for i in range(n)) or 1.0
    slope   = num / den                                   # avg profit per day ($)

    daily_pct    = (slope / current * 100) if current else 0.0
    total_profit = current - start
    total_pct    = ((current / start - 1) * 100) if start else 0.0

    def prof(days: int) -> float:   return round(slope * days, 2)
    def val(days: int)  -> float:   return round(current + slope * days, 2)

    # Confidence scales with how much history we have to fit against
    confidence = "high" if n >= 20 else "medium" if n >= 7 else "low"

    return {
        "ready":            True,
        "days_tracked":     n,
        "start_value":      round(start, 2),
        "current_value":    round(current, 2),
        "total_profit":     round(total_profit, 2),
        "total_profit_pct": round(total_pct, 2),
        "avg_daily_profit": round(slope, 2),
        "avg_daily_pct":    round(daily_pct, 3),
        "proj_day":         prof(1),          "proj_day_value":   val(1),
        "proj_month":       prof(_DAYS_MONTH),"proj_month_value": val(_DAYS_MONTH),
        "proj_year":        prof(_DAYS_YEAR), "proj_year_value":  val(_DAYS_YEAR),
        "confidence":       confidence,
        "history":          [{"d": d["date"], "v": float(d["value"])} for d in data][-60:],
    }


if __name__ == "__main__":
    # Quick manual check / pretty-print of current projections
    print(json.dumps(compute_projections(), indent=2))
