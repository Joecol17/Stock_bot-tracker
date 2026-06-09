"""
DayJournal — a persistent, per-cycle record of everything the bot sees and
decides each day, including the HOLD / filtered-out decisions that
trade_history.json deliberately drops ("why we did NOT trade" is the most
valuable signal for the nightly AI controller to learn from).

Stored in journal.db (SQLite) so the controller — and a future AI — can query
patterns over weeks. Two tables:

  cycles    — one row per analysis cycle: regime, counts, account snapshot.
  decisions — one row per symbol per cycle: final status + reason + action.

Written once at the end of each cycle (off the hot path), so it adds no latency
to the parallel decide phase.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import Config

logger = logging.getLogger(__name__)

# Map the symbol_queue status to a coarse action label for easy aggregation.
_STATUS_ACTION = {
    "hold": "HOLD",
    "filtered_out": "FILTERED",
    "skipped": "SKIP",
    "disabled": "DISABLED",
    "not_queued": "NOT_QUEUED",
    "error": "ERROR",
    "queued": "PENDING",
    "thinking": "PENDING",
    "filtering": "PENDING",
}


class DayJournal:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or getattr(Config, "JOURNAL_DB_PATH", "journal.db")
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._conn() as c:
                c.execute(
                    "CREATE TABLE IF NOT EXISTS cycles ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, day TEXT, cycle INTEGER, "
                    "regime TEXT, n_screened INTEGER, n_selected INTEGER, selected TEXT, "
                    "trades INTEGER, errors INTEGER, cash REAL, portfolio_value REAL, "
                    "free_funds REAL, in_focus INTEGER)"
                )
                c.execute(
                    "CREATE TABLE IF NOT EXISTS decisions ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, day TEXT, cycle INTEGER, "
                    "symbol TEXT, status TEXT, action TEXT, detail TEXT)"
                )
                c.execute("CREATE INDEX IF NOT EXISTS idx_cycles_day ON cycles(day)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_decisions_day ON decisions(day)")
        except Exception as e:
            logger.warning(f"DayJournal: could not init db: {e}")

    @staticmethod
    def _action_for(status: str, detail: str) -> str:
        if status == "traded":
            d = (detail or "").upper()
            if d.startswith("BUY") or " BUY " in d:
                return "BUY"
            if d.startswith("SELL") or " SELL " in d:
                return "SELL"
            return "TRADE"
        return _STATUS_ACTION.get(status, status.upper())

    def record_cycle(
        self,
        cycle: int,
        regime: str,
        account: Dict[str, Any],
        selected: List[str],
        trades: int,
        errors: int,
        in_focus: bool,
        queue_file: str = "symbol_queue.json",
        n_screened: int = 0,
    ) -> None:
        """Persist one cycle. Reads the symbol_queue file to capture the final
        status + reason for every symbol evaluated this cycle."""
        now = datetime.now()
        day = now.strftime("%Y-%m-%d")
        ts = now.isoformat()

        # Pull every symbol's final status/detail from the queue snapshot.
        statuses: Dict[str, Dict[str, str]] = {}
        try:
            with open(queue_file, "r") as f:
                statuses = json.load(f).get("symbols", {})
        except Exception:
            pass

        try:
            with self._conn() as c:
                c.execute(
                    "INSERT INTO cycles(ts,day,cycle,regime,n_screened,n_selected,selected,"
                    "trades,errors,cash,portfolio_value,free_funds,in_focus) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        ts, day, cycle, regime,
                        n_screened or len(statuses), len(selected), ",".join(selected),
                        trades, errors,
                        float(account.get("cash", 0) or 0),
                        float(account.get("portfolio_value", 0) or 0),
                        float(account.get("free_funds", account.get("cash", 0)) or 0),
                        1 if in_focus else 0,
                    ),
                )
                rows = []
                for sym, info in statuses.items():
                    status = info.get("status", "")
                    detail = info.get("detail", "")
                    rows.append((ts, day, cycle, sym, status, self._action_for(status, detail), detail))
                if rows:
                    c.executemany(
                        "INSERT INTO decisions(ts,day,cycle,symbol,status,action,detail) "
                        "VALUES(?,?,?,?,?,?,?)", rows,
                    )
        except Exception as e:
            logger.warning(f"DayJournal.record_cycle failed: {e}")

    # ── queries (for the daily report / controller) ─────────────────────────
    def days(self, limit: int = 30) -> List[str]:
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT DISTINCT day FROM cycles ORDER BY day DESC LIMIT ?", (limit,)
                ).fetchall()
            return [r["day"] for r in rows]
        except Exception:
            return []

    def day_cycles(self, day: str) -> List[dict]:
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT * FROM cycles WHERE day=? ORDER BY cycle", (day,)
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def day_action_counts(self, day: str) -> Dict[str, int]:
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT action, COUNT(*) n FROM decisions WHERE day=? GROUP BY action", (day,)
                ).fetchall()
            return {r["action"]: r["n"] for r in rows}
        except Exception:
            return {}

    def day_top_reasons(self, day: str, limit: int = 12) -> List[dict]:
        """Most common skip/hold reasons that day — surfaces systematic blocks."""
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT detail, COUNT(*) n FROM decisions "
                    "WHERE day=? AND action IN ('HOLD','FILTERED','SKIP') AND detail<>'' "
                    "GROUP BY detail ORDER BY n DESC LIMIT ?", (day, limit),
                ).fetchall()
            return [{"reason": r["detail"], "count": r["n"]} for r in rows]
        except Exception:
            return []
