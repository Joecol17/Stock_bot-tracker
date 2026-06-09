"""
Daily dossier generator — rolls a whole day's data from every source into one
filed document (reports/daily_YYYY-MM-DD.md + .json) that a human can skim and
the nightly AI controller can study for patterns.

Sources: journal.db (cycles + decisions), trade_history.json, equity_history.json,
tracked_positions.json, agent_activity.db (the discovery swarm).

Runnable standalone:  python daily_report.py [YYYY-MM-DD]
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import Config
from journal import DayJournal

logger = logging.getLogger(__name__)


def _load_json(path: str, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def _agent_events_for_day(db_path: str, day: str) -> List[dict]:
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT agent, action, symbols, reason, ts FROM agent_events "
            "WHERE ts LIKE ? ORDER BY id", (day + "%",),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def collect_day(day: Optional[str] = None, journal: Optional[DayJournal] = None) -> Dict[str, Any]:
    """Gather a structured summary of one day from all data sources."""
    day = day or datetime.now().strftime("%Y-%m-%d")
    j = journal or DayJournal()

    cycles = j.day_cycles(day)
    actions = j.day_action_counts(day)
    reasons = j.day_top_reasons(day)

    trades = [t for t in _load_json("trade_history.json", [])
              if str(t.get("timestamp", "")).startswith(day)]
    positions = _load_json("tracked_positions.json", {})
    agent_events = _agent_events_for_day(getattr(Config, "AGENT_DB_PATH", "agent_activity.db"), day)

    pv = [c["portfolio_value"] for c in cycles if c.get("portfolio_value")]
    equity_open = pv[0] if pv else None
    equity_close = pv[-1] if pv else None
    equity_delta = (equity_close - equity_open) if (pv and equity_open is not None) else None
    cash_close = cycles[-1]["cash"] if cycles else None
    free_close = cycles[-1]["free_funds"] if cycles else None

    buys = [t for t in trades if t.get("action") == "BUY"]
    sells = [t for t in trades if t.get("action") in ("SELL", "STOP_LOSS", "TAKE_PROFIT")]
    confs = [t.get("confidence", 0) for t in trades if t.get("confidence")]
    avg_conf = round(sum(confs) / len(confs), 2) if confs else None

    swarm_adds = [e for e in agent_events if e["action"] == "add"]
    swarm_evicts = [e for e in agent_events if e["action"] == "evict"]

    return {
        "day": day,
        "cycles": len(cycles),
        "regimes": sorted({c.get("regime", "?") for c in cycles}),
        "equity_open": equity_open,
        "equity_close": equity_close,
        "equity_delta": equity_delta,
        "cash_close": cash_close,
        "free_close": free_close,
        "n_trades": len(trades),
        "n_buys": len(buys),
        "n_sells": len(sells),
        "avg_confidence": avg_conf,
        "action_counts": actions,
        "top_block_reasons": reasons,
        "open_positions": len(positions),
        "swarm_added": [e["symbols"] for e in swarm_adds],
        "swarm_evicted": [e["symbols"] for e in swarm_evicts],
        "n_agent_events": len(agent_events),
        "trades": [
            {"t": t.get("timestamp", "")[11:19], "action": t.get("action"),
             "symbol": t.get("symbol"), "qty": t.get("quantity"),
             "price": t.get("price"), "conf": t.get("confidence"),
             "why": t.get("reasoning", t.get("message", ""))}
            for t in trades
        ],
    }


def _render_markdown(d: Dict[str, Any]) -> str:
    def money(x):
        return "—" if x is None else f"${x:,.2f}"

    L = []
    L.append(f"# Daily Trading Dossier — {d['day']}\n")
    L.append(f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} · mode {Config.TRADING212_DEMO_MODE and 'DEMO' or 'LIVE'}_\n")

    L.append("## Account")
    delta = d["equity_delta"]
    delta_str = "—" if delta is None else (("+" if delta >= 0 else "") + f"${delta:,.2f}")
    L.append(f"- Equity: {money(d['equity_open'])} → **{money(d['equity_close'])}**  ({delta_str})")
    L.append(f"- Free cash (close): {money(d['free_close'])}")
    L.append(f"- Open positions: {d['open_positions']}")
    L.append(f"- Cycles run: {d['cycles']} · regime(s): {', '.join(d['regimes']) or '—'}\n")

    L.append("## Trading")
    L.append(f"- Trades: **{d['n_trades']}**  ({d['n_buys']} buys, {d['n_sells']} sells/exits)")
    L.append(f"- Avg decision confidence: {d['avg_confidence'] if d['avg_confidence'] is not None else '—'}")
    if d["trades"]:
        L.append("\n| time | action | symbol | qty | price | why |")
        L.append("|------|--------|--------|-----|-------|-----|")
        for t in d["trades"][:40]:
            why = (t["why"] or "")[:80].replace("|", "/")
            L.append(f"| {t['t']} | {t['action']} | {t['symbol']} | {t['qty']} | {t['price']} | {why} |")
    L.append("")

    L.append("## Decisions (all symbols, all cycles)")
    if d["action_counts"]:
        L.append("- " + " · ".join(f"{k}: {v}" for k, v in sorted(d["action_counts"].items(), key=lambda x: -x[1])))
    L.append("\n### Most common reasons we did NOT trade")
    if d["top_block_reasons"]:
        for r in d["top_block_reasons"]:
            L.append(f"- ({r['count']}×) {r['reason']}")
    else:
        L.append("- (none recorded)")
    L.append("")

    L.append("## Discovery swarm")
    L.append(f"- Agent events: {d['n_agent_events']}")
    if d["swarm_added"]:
        L.append(f"- Added to explore: {', '.join(d['swarm_added'])}")
    if d["swarm_evicted"]:
        L.append(f"- Rotated out: {', '.join(d['swarm_evicted'])}")
    L.append("")
    return "\n".join(L)


def generate_daily_report(day: Optional[str] = None, journal: Optional[DayJournal] = None) -> Dict[str, Any]:
    """Build + write the dossier (.md and .json). Returns {day, md_path, json_path, summary}."""
    data = collect_day(day, journal)
    day = data["day"]
    reports_dir = getattr(Config, "REPORTS_DIR", "reports")
    os.makedirs(reports_dir, exist_ok=True)

    md_path = os.path.join(reports_dir, f"daily_{day}.md")
    json_path = os.path.join(reports_dir, f"daily_{day}.json")
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(_render_markdown(data))
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Daily dossier written: {md_path}")
    except Exception as e:
        logger.warning(f"Could not write daily dossier: {e}")

    return {"day": day, "md_path": md_path, "json_path": json_path, "summary": data}


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    d = sys.argv[1] if len(sys.argv) > 1 else None
    res = generate_daily_report(d)
    print(json.dumps({k: v for k, v in res.items() if k != "summary"}, indent=2))
    print("\n--- markdown preview ---\n")
    print(_render_markdown(res["summary"])[:1500])
