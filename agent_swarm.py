"""
Discovery agent swarm — four cooperating "AI agents" that find and vet new
stocks for the explore tier of the watchlist, plus a SQLite activity log that a
future AI controller can query.

Pipeline (each step hands off to the next):
  1. Scout       — batch-scans the whole universe for fresh high-activity names
                   (momentum + volume) → shortlist.
  2. Analyst     — deeper technical screen (RSI / MACD / volume) on the shortlist
                   → graded, ranked candidates.
  3. Risk Officer— runs the pre-trade swing filters (market regime, earnings,
                   relative strength, setup quality) → approves / rejects w/ reasons.
  4. Curator     — manages the 50 explore slots: a single bounded LLM judgment
                   picks the best approved names to add, evicting the weakest
                   non-pinned slots to make room. Logs every add / eviction.

Heavy work (scanning hundreds of symbols) is fast & deterministic; the LLM is
used only for the Curator's final judgment, so the swarm scales to a 300+ universe.

Dependencies are injected (screener, watchlist, a market-context function) so this
module never imports auto_trader — avoiding a circular import.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from config import Config

logger = logging.getLogger(__name__)

SCOUT, ANALYST, RISK, CURATOR = "Scout", "Analyst", "Risk Officer", "Curator"
AGENTS = [SCOUT, ANALYST, RISK, CURATOR]
AGENT_ROLES = {
    SCOUT:   "Scans the universe for fresh high-activity candidates (momentum + volume)",
    ANALYST: "Deep technical screen (RSI / MACD / volume) and grading",
    RISK:    "Pre-trade filters: market regime, earnings, relative strength, setup quality",
    CURATOR: "Manages the explore slots — adds the best vetted names, evicts the weakest",
}


# ──────────────────────────────────────────────────────────────────────────
# SQLite activity log
# ──────────────────────────────────────────────────────────────────────────
class AgentLogger:
    """Append-only event log + current-state table in SQLite (queryable later)."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or getattr(Config, "AGENT_DB_PATH", "agent_activity.db")
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._conn() as c:
                c.execute(
                    "CREATE TABLE IF NOT EXISTS agent_events ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, cycle INTEGER, "
                    "agent TEXT, action TEXT, status TEXT, symbols TEXT, detail TEXT, reason TEXT)"
                )
                c.execute(
                    "CREATE TABLE IF NOT EXISTS agent_state ("
                    "agent TEXT PRIMARY KEY, status TEXT, current_task TEXT, "
                    "last_action TEXT, processed INTEGER, updated TEXT)"
                )
        except Exception as e:
            logger.warning(f"AgentLogger: could not init db: {e}")

    def log(self, agent: str, action: str, symbols=None, detail: str = "",
            reason: str = "", status: str = "ok", cycle: Optional[int] = None) -> None:
        if isinstance(symbols, (list, tuple, set)):
            syms = ",".join(str(s) for s in symbols)
        else:
            syms = str(symbols or "")
        try:
            with self._conn() as c:
                c.execute(
                    "INSERT INTO agent_events(ts,cycle,agent,action,status,symbols,detail,reason) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (datetime.utcnow().isoformat(), cycle, agent, action, status, syms, detail, reason),
                )
        except Exception as e:
            logger.warning(f"AgentLogger.log failed: {e}")

    def set_state(self, agent: str, status: str, current_task: str = "",
                  last_action: str = "", processed: int = 0) -> None:
        try:
            with self._conn() as c:
                c.execute(
                    "INSERT INTO agent_state(agent,status,current_task,last_action,processed,updated) "
                    "VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT(agent) DO UPDATE SET status=excluded.status, "
                    "current_task=excluded.current_task, last_action=excluded.last_action, "
                    "processed=excluded.processed, updated=excluded.updated",
                    (agent, status, current_task, last_action, processed, datetime.utcnow().isoformat()),
                )
        except Exception as e:
            logger.warning(f"AgentLogger.set_state failed: {e}")

    def recent(self, limit: int = 100) -> List[dict]:
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT ts,cycle,agent,action,status,symbols,detail,reason "
                    "FROM agent_events ORDER BY id DESC LIMIT ?", (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"AgentLogger.recent failed: {e}")
            return []

    def states(self) -> List[dict]:
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT agent,status,current_task,last_action,processed,updated FROM agent_state"
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"AgentLogger.states failed: {e}")
            return []


def _grade(score: float) -> str:
    return "A" if score >= 6 else "B" if score >= 4 else "C" if score >= 2 else "D"


# ──────────────────────────────────────────────────────────────────────────
# The swarm
# ──────────────────────────────────────────────────────────────────────────
class Swarm:
    """Orchestrates the four discovery agents over the watchlist's explore tier."""

    def __init__(
        self,
        watchlist,                                  # WatchlistManager
        screener,                                   # Screener
        market_context_fn: Callable[[str], Dict[str, Any]],
        universe_fn: Optional[Callable[[], List[str]]] = None,
        activity_logger: Optional[AgentLogger] = None,
        notifier=None,
        shortlist_size: int = 30,
        vet_size: int = 15,
    ) -> None:
        self.wl = watchlist
        self.screener = screener
        self.market_context_fn = market_context_fn
        self.universe_fn = universe_fn or self._default_universe
        self.log = activity_logger or AgentLogger()
        self.notifier = notifier
        self.shortlist_size = shortlist_size
        self.vet_size = vet_size
        for a in AGENTS:
            self.log.set_state(a, "idle", "waiting for next discovery scan")

    @staticmethod
    def _default_universe() -> List[str]:
        try:
            from discovery import StockUniverse
            return StockUniverse().symbols()
        except Exception:
            return []

    # ── orchestration ──────────────────────────────────────────────────────
    def run(self, cycle: Optional[int] = None) -> Dict[str, Any]:
        """Run the full discovery pipeline once. Returns a summary dict."""
        already = set(self.wl.list_symbols())
        shortlist = self._scout(cycle, exclude=already)
        ranked = self._analyst(cycle, shortlist)
        approved = self._risk_officer(cycle, ranked)
        added, evicted = self._curator(cycle, approved)
        for a in AGENTS:
            # leave each agent's "current_task" as idle between scans
            pass
        return {"shortlist": shortlist, "approved": [s for s, _ in approved],
                "added": added, "evicted": evicted}

    # ── 1. Scout ─────────────────────────────────────────────────────────────
    def _scout(self, cycle, exclude: set) -> List[str]:
        self.log.set_state(SCOUT, "working", "scanning the universe for fresh activity")
        universe = [s for s in self.universe_fn() if s.upper() not in exclude]
        if not universe:
            self.log.set_state(SCOUT, "idle", "nothing to scan", "no fresh universe", 0)
            return []
        scores = self.screener.score_many(universe)   # one batched download
        ranked = sorted(universe, key=lambda s: scores.get(s, 0.0), reverse=True)
        shortlist = [s for s in ranked if scores.get(s, 0.0) > 0][: self.shortlist_size]
        top = ", ".join(f"{s}({scores.get(s,0):.0f})" for s in shortlist[:8])
        self.log.log(SCOUT, "scan", symbols=shortlist, cycle=cycle,
                     detail=f"scanned {len(universe)} symbols",
                     reason=f"surfaced {len(shortlist)} by momentum/volume: {top}")
        self.log.set_state(SCOUT, "idle",
                           "waiting for next discovery scan",
                           f"surfaced {len(shortlist)} of {len(universe)}", len(universe))
        return shortlist

    # ── 2. Analyst ───────────────────────────────────────────────────────────
    def _analyst(self, cycle, shortlist: List[str]) -> List[tuple]:
        self.log.set_state(ANALYST, "working", f"grading {len(shortlist)} candidates")
        if not shortlist:
            self.log.set_state(ANALYST, "idle", "no candidates to grade", "nothing from Scout", 0)
            return []
        scores = self.screener.score_many(shortlist)
        ranked = sorted(
            [(s, scores.get(s, 0.0)) for s in shortlist],
            key=lambda t: t[1], reverse=True,
        )[: self.vet_size]
        graded = ", ".join(f"{s}:{_grade(sc)}({sc:.0f})" for s, sc in ranked[:8])
        self.log.log(ANALYST, "grade", symbols=[s for s, _ in ranked], cycle=cycle,
                     detail=f"graded {len(ranked)} candidates",
                     reason=f"top by technicals: {graded}")
        self.log.set_state(ANALYST, "idle", "waiting for next discovery scan",
                           f"graded {len(ranked)} candidates", len(shortlist))
        return ranked

    # ── 3. Risk Officer ──────────────────────────────────────────────────────
    def _risk_officer(self, cycle, ranked: List[tuple]) -> List[tuple]:
        self.log.set_state(RISK, "working", f"vetting {len(ranked)} candidates")
        if not ranked:
            self.log.set_state(RISK, "idle", "no candidates to vet", "nothing from Analyst", 0)
            return []
        from swing_filters import run_all_filters
        approved: List[tuple] = []
        rejected = 0
        for symbol, score in ranked:
            try:
                ctx = self.market_context_fn(symbol)
                if not ctx:
                    rejected += 1
                    continue
                fr = run_all_filters(
                    symbol=symbol, context=ctx,
                    benchmark=Config.MARKET_REGIME_SYMBOL,
                    earnings_buffer_days=Config.EARNINGS_BUFFER_DAYS,
                    min_rs=Config.MIN_RELATIVE_STRENGTH,
                    strict_regime=Config.REGIME_STRICT,
                )
                f_score = fr.get("filter_score", 0)
                if fr.get("skip_reason"):
                    rejected += 1
                    self.log.log(RISK, "reject", symbols=[symbol], cycle=cycle,
                                 status="rejected", detail=f"filters {f_score}/4",
                                 reason=fr["skip_reason"])
                elif f_score >= Config.MIN_FILTER_SCORE:
                    approved.append((symbol, score + f_score))
                    self.log.log(RISK, "approve", symbols=[symbol], cycle=cycle,
                                 detail=f"filters {f_score}/4",
                                 reason=f"passed regime/earnings/RS/setup ({f_score}/4)")
                else:
                    rejected += 1
                    self.log.log(RISK, "reject", symbols=[symbol], cycle=cycle,
                                 status="rejected", detail=f"filters {f_score}/4",
                                 reason=f"only {f_score}/4 filters passed (min {Config.MIN_FILTER_SCORE})")
            except Exception as e:
                rejected += 1
                logger.debug(f"Risk Officer error on {symbol}: {e}")
        approved.sort(key=lambda t: t[1], reverse=True)
        self.log.set_state(RISK, "idle", "waiting for next discovery scan",
                           f"approved {len(approved)}, rejected {rejected}", len(ranked))
        return approved

    # ── 4. Curator ───────────────────────────────────────────────────────────
    def _curator(self, cycle, approved: List[tuple]) -> tuple:
        self.log.set_state(CURATOR, "working", f"reviewing {len(approved)} approved names")
        added: List[str] = []
        evicted: List[str] = []
        if not approved:
            self.log.set_state(CURATOR, "idle", "waiting for next discovery scan",
                               "no approved candidates", 0)
            return added, evicted

        free = self.wl.explore_slots_free()
        want = min(len(approved), max(free, 0) or len(approved))

        # Make room if needed by evicting the weakest non-pinned explore slots,
        # but only for candidates clearly stronger than what we'd drop.
        if free < len(approved):
            evictable = sorted(
                [e for e in self.wl.explore_meta() if not e.get("pinned")],
                key=lambda e: (e.get("score") or 0),
            )
            need = min(len(approved), Config.EXPLORE_SLOTS) - free
            for e in evictable[: max(0, need)]:
                best_new = approved[0][1] if approved else 0
                if (e.get("score") or 0) < best_new:
                    if self.wl.evict_explore(e["symbol"], reason="rotated out for stronger candidate"):
                        evicted.append(e["symbol"])
                        self.log.log(CURATOR, "evict", symbols=[e["symbol"]], cycle=cycle,
                                     status="evicted",
                                     reason=f"weakest slot (score {e.get('score')}) rotated for a stronger pick")

        slots = self.wl.explore_slots_free()
        picks = self._llm_pick(approved, slots, cycle)

        for symbol, score in picks:
            reason = f"discovery pick (combined score {score:.0f}) — passed all swarm stages"
            if self.wl.add_explore(symbol, score=score, reason=reason, cycle=cycle):
                added.append(symbol)
                self.log.log(CURATOR, "add", symbols=[symbol], cycle=cycle,
                             detail=f"score {score:.0f}", reason=reason)

        if added and self.notifier:
            try:
                self.notifier.discovery_update(added, len(self.wl.list_symbols()))
            except Exception:
                pass

        self.log.set_state(CURATOR, "idle", "waiting for next discovery scan",
                           f"added {len(added)}, evicted {len(evicted)}", len(approved))
        return added, evicted

    # ── Curator's single bounded LLM judgment ────────────────────────────────
    def _llm_pick(self, approved: List[tuple], slots: int, cycle) -> List[tuple]:
        """Ask the model to pick the best names to add (one call). Falls back to
        the top by score if the LLM is unavailable or returns nothing usable."""
        if slots <= 0 or not approved:
            return []
        top = approved[: min(len(approved), max(slots * 2, slots))]
        fallback = approved[:slots]
        try:
            from decision_system import OllamaClient
            client = OllamaClient(
                model_name=Config.OLLAMA_MODEL,
                temperature=Config.OLLAMA_TEMPERATURE,
                max_tokens=Config.OLLAMA_MAX_TOKENS,
            )
            listing = "\n".join(f"  {s} (score {sc:.0f})" for s, sc in top)
            prompt = (
                "You are the portfolio Curator for a swing-trading bot. From the vetted "
                f"candidate stocks below, choose up to {slots} you'd add to the active "
                "watchlist right now. Prefer diversification and the strongest setups.\n\n"
                f"Candidates (already passed momentum, technical and risk filters):\n{listing}\n\n"
                'Respond ONLY with JSON: {"picks": ["TICKER", ...]}'
            )
            res = client.query(prompt)
            picks_syms = []
            if res and not res.error and isinstance(res.parsed, dict):
                raw = res.parsed.get("picks") or []
                if isinstance(raw, list):
                    valid = {s for s, _ in top}
                    picks_syms = [str(x).upper().strip() for x in raw if str(x).upper().strip() in valid]
            if picks_syms:
                score_map = dict(top)
                chosen = [(s, score_map[s]) for s in picks_syms][:slots]
                self.log.log(CURATOR, "judge", symbols=[s for s, _ in chosen], cycle=cycle,
                             detail="LLM curation", reason="model selected these from the vetted set")
                return chosen
        except Exception as e:
            logger.debug(f"Curator LLM pick failed, using score ranking: {e}")
        self.log.log(CURATOR, "judge", symbols=[s for s, _ in fallback], cycle=cycle,
                     detail="score ranking", reason="LLM unavailable — picked top by combined score")
        return fallback
