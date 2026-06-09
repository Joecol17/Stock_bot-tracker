"""
Automated trading loop - continuously monitors and trades based on market analysis.
Uses Ollama for decision-making and Trading 212 API for execution.
"""

import json
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from trading_system import TradingSystem
from watchlist import WatchlistManager, Screener
from discovery import StockDiscovery
from notifier import DiscordNotifier
from swing_filters import run_all_filters, get_market_regime
from equity_tracker import record_snapshot
from agent_swarm import Swarm, AgentLogger
from journal import DayJournal
from config import Config


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


def _safe_float(series, idx: int = -1) -> Optional[float]:
    """Return a rounded float from a pandas Series, or None if NaN/missing."""
    try:
        val = float(series.iloc[idx])
        return round(val, 4) if not (val != val) else None  # NaN check
    except Exception:
        return None


def get_market_context(symbol: str) -> Dict[str, Any]:
    """
    Fetch 1-year of DAILY bars and build a swing-trading context dict.

    Key additions vs the old hourly approach:
      - Daily bars (1y/1d) — swing trades are held for days, not minutes
      - SMA 200 for long-term trend
      - ATR(14) on daily bars — used for position sizing & stop placement
      - 52-week range position (where is price in its yearly range?)
      - Support / resistance from 50-day high/low (more meaningful on daily)
      - Volume vs 20-day average (not just vs overall mean)
    """
    try:
        import yfinance as yf
        import ta

        ticker = yf.Ticker(symbol)
        # 1 year of daily bars — enough for SMA200, ATR, long-term support/resistance
        hist = ticker.history(period="1y", interval="1d")
        info = ticker.fast_info

        if hist.empty or len(hist) < 30:
            raise ValueError(f"Insufficient daily data for {symbol}")

        close  = hist["Close"]
        high   = hist["High"]
        low    = hist["Low"]
        volume = hist["Volume"]

        current_price = float(close.iloc[-1])
        prev_close    = float(close.iloc[-2]) if len(close) > 1 else current_price
        change_pct    = round((current_price - prev_close) / prev_close * 100, 2) if prev_close else 0

        # ── Trend (5-day daily close direction) ──────────────────────────────
        closes_5 = close.tail(5).tolist()
        if closes_5[-1] > closes_5[0] * 1.02:
            trend = "uptrend"
        elif closes_5[-1] < closes_5[0] * 0.98:
            trend = "downtrend"
        else:
            trend = "neutral"

        # ── Volume vs 20-day average ─────────────────────────────────────────
        avg_vol20 = float(volume.tail(20).mean())
        last_vol  = float(volume.iloc[-1])
        if avg_vol20 > 0:
            vol_ratio = last_vol / avg_vol20
            if vol_ratio > 1.5:
                vol_label = "high"
            elif vol_ratio < 0.6:
                vol_label = "low"
            else:
                vol_label = "normal"
        else:
            vol_label = "normal"
            vol_ratio = 1.0

        # ── Support / resistance from 50-day range ───────────────────────────
        h50 = float(high.tail(50).max())
        l50 = float(low.tail(50).min())

        # ── 52-week range ────────────────────────────────────────────────────
        h52w = getattr(info, "year_high", None) or float(high.max())
        l52w = getattr(info, "year_low",  None) or float(low.min())
        range_pct_52w = None
        if h52w and l52w and h52w > l52w:
            range_pct_52w = round((current_price - l52w) / (h52w - l52w) * 100, 1)

        # ── Technical indicators (all on daily bars) ─────────────────────────
        rsi = _safe_float(ta.momentum.RSIIndicator(close, window=14).rsi())

        macd_obj    = ta.trend.MACD(close, window_fast=12, window_slow=26, window_sign=9)
        macd_line   = _safe_float(macd_obj.macd())
        macd_signal = _safe_float(macd_obj.macd_signal())
        macd_hist   = _safe_float(macd_obj.macd_diff())

        # Prev-day MACD histogram to detect direction change
        macd_hist_prev = _safe_float(macd_obj.macd_diff(), idx=-2)
        macd_hist_rising = None
        if macd_hist is not None and macd_hist_prev is not None:
            macd_hist_rising = macd_hist > macd_hist_prev

        sma20  = _safe_float(ta.trend.SMAIndicator(close, window=20).sma_indicator())
        sma50  = _safe_float(ta.trend.SMAIndicator(close, window=50).sma_indicator())
        sma200 = _safe_float(ta.trend.SMAIndicator(close, window=200).sma_indicator()) if len(close) >= 200 else None

        # ATR(14) on daily — the heartbeat of swing position sizing
        atr14 = _safe_float(ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range())

        bb     = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        bb_upper = _safe_float(bb.bollinger_hband())
        bb_lower = _safe_float(bb.bollinger_lband())
        bb_mid   = _safe_float(bb.bollinger_mavg())
        bb_width = round((bb_upper - bb_lower) / bb_mid * 100, 2) if bb_upper and bb_lower and bb_mid else None

        # ── Derived signals ──────────────────────────────────────────────────
        bb_position = None
        if bb_upper and bb_lower and bb_upper != bb_lower:
            bb_position = round((current_price - bb_lower) / (bb_upper - bb_lower), 4)

        price_vs_sma20  = round((current_price / sma20  - 1) * 100, 2) if sma20  else None
        price_vs_sma50  = round((current_price / sma50  - 1) * 100, 2) if sma50  else None
        price_vs_sma200 = round((current_price / sma200 - 1) * 100, 2) if sma200 else None

        macd_crossover = None
        if macd_line is not None and macd_signal is not None:
            macd_crossover = "bullish" if macd_line > macd_signal else "bearish" if macd_line < macd_signal else "neutral"

        # Suggested ATR-based stop/target prices (for LLM context + sizing)
        suggested_stop   = round(current_price - (atr14 * Config.ATR_STOP_MULTIPLIER), 4) if atr14 else None
        suggested_target = round(current_price + (atr14 * Config.ATR_STOP_MULTIPLIER * Config.MIN_RISK_REWARD), 4) if atr14 else None

        return {
            # Core price data
            "symbol":         symbol,
            "price":          round(current_price, 4),
            "prev_close":     round(prev_close, 4),
            "change_pct":     change_pct,
            "trend":          trend,
            "timeframe":      "daily",

            # Volume
            "volume":         vol_label,
            "volume_ratio":   round(vol_ratio, 2),

            # Range context
            "support_level":    round(l50, 4),
            "resistance_level": round(h50, 4),
            "52w_high":         round(h52w, 4) if h52w else None,
            "52w_low":          round(l52w, 4) if l52w else None,
            "52w_range_pct":    range_pct_52w,  # 0=at yearly low, 100=at yearly high

            # Moving averages
            "sma_20":           sma20,
            "sma_50":           sma50,
            "sma_200":          sma200,
            "price_vs_sma20_pct":  price_vs_sma20,
            "price_vs_sma50_pct":  price_vs_sma50,
            "price_vs_sma200_pct": price_vs_sma200,

            # Momentum
            "rsi_14":          rsi,
            "macd_line":       macd_line,
            "macd_signal":     macd_signal,
            "macd_histogram":  macd_hist,
            "macd_hist_rising": macd_hist_rising,
            "macd_crossover":  macd_crossover,

            # Volatility
            "atr_14":          atr14,
            "bb_upper":        bb_upper,
            "bb_mid":          bb_mid,
            "bb_lower":        bb_lower,
            "bb_position":     bb_position,
            "bb_width_pct":    bb_width,

            # Swing trade price targets (ATR-based)
            "suggested_stop_price":   suggested_stop,
            "suggested_target_price": suggested_target,
            "atr_stop_multiplier":    Config.ATR_STOP_MULTIPLIER,
            "min_risk_reward":        Config.MIN_RISK_REWARD,
        }

    except Exception as e:
        logger.warning(f"Could not fetch market data for {symbol}: {e}")
        return {
            "symbol":     symbol,
            "price":      0,
            "trend":      "neutral",
            "volume":     "normal",
            "timeframe":  "daily",
            "data_error": str(e),
        }


_CONTROL_FILE = "bot_control.json"
_QUEUE_FILE   = "symbol_queue.json"   # per-symbol cycle status (read by dashboard)
_PREFS_FILE   = "symbol_prefs.json"   # per-symbol enabled/disabled (written by dashboard)


class AutoTradingBot:
    """Automated trading bot using Ollama decisions and live market data."""

    def __init__(
        self,
        trading_system: TradingSystem,
        watchlist: WatchlistManager,
        interval_seconds: int = 300,
    ):
        self.system = trading_system
        self.watchlist = watchlist
        self.screener = Screener()
        self.discovery = StockDiscovery()
        self.notifier = DiscordNotifier(
            fallback=Config.DISCORD_WEBHOOK_URL,
            trades=Config.DISCORD_WEBHOOK_TRADES,
            risk=Config.DISCORD_WEBHOOK_RISK,
            portfolio=Config.DISCORD_WEBHOOK_PORTFOLIO,
            discovery=Config.DISCORD_WEBHOOK_DISCOVERY,
            alerts=Config.DISCORD_WEBHOOK_ALERTS,
        )
        # Discovery agent swarm — Scout/Analyst/Risk Officer/Curator manage the
        # explore tier of the watchlist and log their activity to SQLite.
        self.agent_log = AgentLogger()
        self.swarm = Swarm(
            watchlist=self.watchlist,
            screener=self.screener,
            market_context_fn=get_market_context,
            activity_logger=self.agent_log,
            notifier=self.notifier,
        )
        # Records every cycle (incl. HOLD/filtered decisions) for the nightly controller.
        self.journal = DayJournal()
        self._last_nightly_day = None   # date string of the last nightly analysis run
        self.interval = interval_seconds
        self.is_running = False
        self.trade_count = 0
        self.error_count = 0
        self._cycle_count = 0
        # Guards the JSON status files (symbol_queue/bot_state) when the decide
        # phase runs symbols in parallel threads.
        self._io_lock = threading.Lock()
        self._started_at = datetime.now().isoformat()
        # Ensure a clean control file at startup
        self._write_control({"paused": False, "run_cycle_now": False})
        self._write_state(0, "idle")

    def _write_state(self, step: int, step_name: str, current_symbol: str = "",
                     status: str = None) -> None:
        """Write bot state to bot_state.json for the dashboard to read.

        status — override the auto-derived status. Recognised values:
          "running"  actively running a cycle
          "idle"     in-hours, waiting for next scheduled slot
          "standby"  outside trading hours, sleeping until next window
          "paused"   user paused via dashboard
        """
        try:
            started = datetime.fromisoformat(self._started_at)
            uptime  = int((datetime.now() - started).total_seconds())
            in_window = self._is_trading_time()
            next_slot = self._next_slot_dt()
            if status is None:
                if self.is_running and step > 0:
                    status = "running"
                elif self.is_running:
                    status = "idle" if in_window else "standby"
                else:
                    status = "stopped"
            state = {
                "status":          status,
                "cycle":           self._cycle_count,
                "step":            step,
                "step_name":       step_name,
                "current_symbol":  current_symbol,
                "started_at":      self._started_at,
                "last_updated":    datetime.now().isoformat(),
                "uptime_seconds":  uptime,
                "trade_count":     self.trade_count,
                "error_count":     self.error_count,
                # Schedule info
                "in_trading_window": in_window,
                "next_run":          next_slot.strftime("%H:%M"),
                "next_run_iso":      next_slot.isoformat(),
                "schedule_enabled":  Config.TRADING_SCHEDULE_ENABLED,
                "trading_hours":     f"{Config.TRADING_START_HOUR:02d}:00–{Config.TRADING_END_HOUR:02d}:00 Mon–Fri",
                "cycles_per_hour":   Config.TRADING_CYCLES_PER_HOUR,
            }
            with open("bot_state.json", "w") as f:
                json.dump(state, f)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Symbol queue (per-cycle status visible in dashboard watchlist)
    # ------------------------------------------------------------------

    def _init_queue(self, symbols: List[str]) -> None:
        """Initialise every symbol as 'queued' at the start of a cycle."""
        queue: Dict[str, Any] = {}
        # Preserve disabled flag from prefs
        prefs = self._read_prefs()
        for sym in symbols:
            if not prefs.get(sym, {}).get("enabled", True):
                queue[sym] = {"status": "disabled", "updated": datetime.now().isoformat()}
            else:
                queue[sym] = {"status": "queued",   "updated": datetime.now().isoformat()}
        try:
            with open(_QUEUE_FILE, "w") as f:
                json.dump({"cycle": self._cycle_count, "symbols": queue,
                           "updated": datetime.now().isoformat()}, f)
        except Exception:
            pass

    def _set_sym_status(self, symbol: str, status: str, detail: str = "") -> None:
        """
        Update one symbol's status in symbol_queue.json.

        Status values:
          queued        → scheduled for this cycle, not started yet
          filtering     → running swing filters
          filtered_out  → didn't pass filters
          thinking      → Ollama is running right now
          hold          → Ollama said HOLD
          traded        → order executed (BUY or SELL)
          skipped       → no price data / earnings block / other skip
          error         → exception during analysis
          disabled      → turned off by user from the dashboard
          not_queued    → watchlist symbol not selected by screener this cycle
        """
        # Locked: the decide phase may update many symbols from parallel threads,
        # and this is a read-modify-write of the whole queue file.
        with self._io_lock:
            try:
                with open(_QUEUE_FILE, "r") as f:
                    data = json.load(f)
            except Exception:
                data = {"cycle": self._cycle_count, "symbols": {}, "updated": ""}

            data["symbols"][symbol] = {
                "status":  status,
                "detail":  detail,
                "updated": datetime.now().isoformat(),
            }
            data["updated"] = datetime.now().isoformat()
            try:
                with open(_QUEUE_FILE, "w") as f:
                    json.dump(data, f)
            except Exception:
                pass

    def _read_prefs(self) -> Dict[str, Any]:
        """Read symbol_prefs.json. Returns {} if missing."""
        try:
            with open(_PREFS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _is_symbol_enabled(self, symbol: str) -> bool:
        """Return False if the user disabled this symbol from the dashboard."""
        prefs = self._read_prefs()
        return prefs.get(symbol, {}).get("enabled", True)

    # ------------------------------------------------------------------
    # Night-shift analysis (daily dossier + AI controller) — runs after
    # market close, in a background thread, so it never slows a cycle.
    # ------------------------------------------------------------------
    def _maybe_run_nightly(self) -> None:
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if self._last_nightly_day == today:
                return
            if now.hour < getattr(Config, "NIGHTLY_ANALYSIS_HOUR", 22):
                return
            if self._is_trading_time():
                return
            self._last_nightly_day = today
            threading.Thread(target=self._run_nightly, args=(today,), daemon=True).start()
            logger.info("Night-shift analysis started (daily dossier + AI controller)")
        except Exception as e:
            logger.warning(f"Nightly scheduling check failed: {e}")

    def _run_nightly(self, day: str) -> None:
        try:
            from daily_report import generate_daily_report
            from controller import run_controller
            generate_daily_report(day)
            rec = run_controller(day)   # advisory unless CONTROLLER_AUTO_APPLY=true
            logger.info(
                f"Night-shift done — {len(rec.get('feature_ideas', []))} feature ideas, "
                f"{len(rec.get('improvements', []))} improvements, "
                f"{len(rec.get('param_proposals', []))} param proposals, "
                f"applied={rec.get('applied')}"
            )
        except Exception as e:
            logger.error(f"Night-shift analysis failed: {e}")

    # ------------------------------------------------------------------
    # Bot control helpers (dashboard → bot_control.json → here)
    # ------------------------------------------------------------------

    def _read_control(self) -> Dict[str, Any]:
        """Read the control file written by the dashboard."""
        try:
            with open(_CONTROL_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"paused": False, "run_cycle_now": False}

    def _write_control(self, updates: Dict[str, Any]) -> None:
        """Merge updates into the control file."""
        ctrl = self._read_control()
        ctrl.update(updates)
        try:
            with open(_CONTROL_FILE, "w") as f:
                json.dump(ctrl, f)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Trading schedule (Mon–Fri, configurable hours, N cycles/hour)
    # ------------------------------------------------------------------

    def _is_trading_time(self) -> bool:
        """True if right now is Mon–Fri between TRADING_START_HOUR and TRADING_END_HOUR."""
        if not Config.TRADING_SCHEDULE_ENABLED:
            return True
        now = datetime.now()
        if now.weekday() >= 5:          # Saturday=5, Sunday=6
            return False
        return Config.TRADING_START_HOUR <= now.hour < Config.TRADING_END_HOUR

    def _next_slot_dt(self) -> datetime:
        """
        Return the next datetime we should run a cycle.

        During trading hours   → next N-minute boundary within today's window.
        After end of day       → 12pm (midday) next trading day.
        Weekend                → 12pm (midday) Monday.
        """
        if not Config.TRADING_SCHEDULE_ENABLED:
            return datetime.now() + timedelta(seconds=Config.BOT_CYCLE_INTERVAL)

        # During the market-open focus window, scan far more often (e.g. every 5 min).
        cycles_per_hour = (Config.FOCUS_CYCLES_PER_HOUR
                           if Config.in_focus_period() else Config.TRADING_CYCLES_PER_HOUR)
        slot_mins = max(1, 60 // max(1, cycles_per_hour))   # e.g. 20 min normal, 5 min focus
        start_h   = Config.TRADING_START_HOUR
        end_h     = Config.TRADING_END_HOUR
        now       = datetime.now()

        # ── next slot within today ──────────────────────────────────────────
        elapsed  = now.minute % slot_mins
        wait     = slot_mins - elapsed if elapsed else slot_mins
        candidate = (now + timedelta(minutes=wait)).replace(second=0, microsecond=0)

        # Is the candidate still within today's window and a weekday?
        if (candidate.weekday() < 5
                and start_h <= candidate.hour < end_h):
            return candidate

        # ── otherwise, the next opening slot ────────────────────────────────
        # If it's still before today's open on a weekday, the next slot is
        # *today's* open — not tomorrow's. (The old code always added a day,
        # so a bot started before the window would idle until the next day.)
        opening_today = now.replace(hour=start_h, minute=0, second=0, microsecond=0)
        if now < opening_today and now.weekday() < 5:
            return opening_today
        # Past today's window (or weekend) → next weekday's open.
        next_day = opening_today + timedelta(days=1)
        while next_day.weekday() >= 5:          # skip Sat/Sun
            next_day += timedelta(days=1)
        return next_day

    def _secs_until_next_slot(self) -> int:
        """Seconds from now until the next scheduled slot (minimum 5 s)."""
        delta = (self._next_slot_dt() - datetime.now()).total_seconds()
        return max(5, int(delta))

    def _is_paused(self) -> bool:
        return bool(self._read_control().get("paused", False))

    def _interruptible_sleep(self, seconds: int) -> bool:
        """Sleep for up to `seconds` but exit early if run_cycle_now is set.

        Returns True  if interrupted by a manual 'Run Cycle' trigger.
        Returns False if the full timeout elapsed.
        """
        deadline = time.time() + seconds
        while self.is_running and time.time() < deadline:
            time.sleep(1)
            ctrl = self._read_control()
            if ctrl.get("run_cycle_now"):
                logger.info("Run-cycle-now triggered from dashboard")
                self._write_control({"run_cycle_now": False})
                return True   # <-- interrupted
        return False           # <-- timed out normally

    def analyze_symbol(self, symbol: str, regime: Optional[Dict[str, Any]] = None) -> bool:
        """Analyse one symbol end-to-end (decide then execute). Returns True if traded."""
        prepared = self._decide_symbol(symbol, regime)
        if not prepared:
            return False
        return self._execute_symbol(prepared)

    def _decide_symbol(self, symbol: str, regime: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """READ-ONLY stage (safe to run in parallel threads): fetch context, run
        the swing filters, and get the LLM decision. Returns a prepared dict
        {symbol, context, decision} to execute, or None to skip this symbol.

        Flow: context -> filters (>= MIN_FILTER_SCORE) -> LLM decision.
        No orders are placed here — see _execute_symbol for the cash-mutating step.
        """
        try:
            logger.info(f"--- {symbol} ---")

            if not self._is_symbol_enabled(symbol):
                logger.info(f"  {symbol}: disabled by user — skipping")
                self._set_sym_status(symbol, "disabled")
                return None

            # Already holding it? Don't churn it — trailing stop manages the exit.
            if Config.HOLD_THROUGH_LLM and symbol in self.system.get_tracked_positions():
                logger.info(f"  {symbol}: holding — managed by trailing stop, skipping LLM")
                self._set_sym_status(symbol, "hold", "holding — trailing stop active")
                return None

            self._set_sym_status(symbol, "filtering")
            context = get_market_context(symbol)

            if context.get("price", 0) == 0:
                logger.warning(f"  {symbol}: no price data — skipping")
                self._set_sym_status(symbol, "skipped", "no price data")
                return None

            # ── pre-trade swing filters ────────────────────────────────────
            filter_result = run_all_filters(
                symbol=symbol,
                context=context,
                benchmark=Config.MARKET_REGIME_SYMBOL,
                earnings_buffer_days=Config.EARNINGS_BUFFER_DAYS,
                min_rs=Config.MIN_RELATIVE_STRENGTH,
                strict_regime=Config.REGIME_STRICT,
            )

            f_score  = filter_result["filter_score"]
            f_regime = filter_result["filters"].get("regime", {})
            f_earn   = filter_result["filters"].get("earnings", {})
            f_rs     = filter_result["filters"].get("relative_strength", {})
            f_setup  = filter_result["filters"].get("setup", {})
            skip_reason = filter_result.get("skip_reason")

            logger.info(
                f"  Filters: regime={f_regime.get('regime','?')} "
                f"earn_ok={f_earn.get('pass','?')} "
                f"RS={f_rs.get('relative_strength','?')} "
                f"setup={f_setup.get('setup_score','?')}/100 "
                f"=> score {f_score}/4"
            )

            if skip_reason:
                logger.info(f"  SKIP: {skip_reason}")
                self._set_sym_status(symbol, "filtered_out", skip_reason)
                return None

            if f_score < Config.MIN_FILTER_SCORE:
                msg = f"only {f_score}/4 filters passed (min {Config.MIN_FILTER_SCORE})"
                logger.info(f"  SKIP: {msg} — not a quality setup")
                self._set_sym_status(symbol, "filtered_out", msg)
                return None

            context["pre_trade_filters"] = {
                "filter_score":     f_score,
                "filter_max":       4,
                "regime":           f_regime.get("regime", "unknown"),
                "setup_grade":      f_setup.get("setup_grade", "?"),
                "setup_score":      f_setup.get("setup_score", 0),
                "relative_strength": f_rs.get("relative_strength"),
                "days_to_earnings": f_earn.get("days_to_earnings"),
            }

            # ── LLM decision (the slow part — parallelised across symbols) ──
            self._set_sym_status(symbol, "thinking")
            decision = self.system.decide(symbol, context)
            return {"symbol": symbol, "context": context, "decision": decision}

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            self._set_sym_status(symbol, "error", str(e))
            with self._io_lock:
                self.error_count += 1
            try:
                self.notifier.error(str(e), context=f"Symbol: {symbol}")
            except Exception:
                pass
            return None

    def _execute_symbol(self, prepared: Dict[str, Any]) -> bool:
        """SERIAL stage (cash-aware, single-threaded): size and place the order for
        a prepared decision, then log / notify. Returns True if a trade executed.

        free_funds is re-fetched here so each order in the cycle sees the cash that
        prior orders already spent.
        """
        symbol  = prepared["symbol"]
        context = prepared["context"]
        decision = prepared["decision"]
        try:
            self._write_state(5, "Execute order", symbol)
            acct = self.system.get_account_status()
            result = self.system.execute_prepared(
                symbol=symbol,
                context=context,
                decision=decision,
                account_value=acct.get("portfolio_value", 0),
                free_funds=acct.get("free_funds", acct.get("cash", 0)),
            )

            exec_result = result["execution"]
            action = exec_result["action"]

            decision_inner = result.get("decision", {}).get("decision", {})
            reasoning_text = decision_inner.get("reasoning") if isinstance(decision_inner, dict) else None
            setup_type     = decision_inner.get("setup_type", "unknown") if isinstance(decision_inner, dict) else "unknown"
            exp_hold       = decision_inner.get("expected_hold_days") if isinstance(decision_inner, dict) else None

            if exec_result["success"] and action in ("BUY", "SELL"):
                logger.info(
                    f"  {symbol}: {action} "
                    f"[{setup_type}] hold~{exp_hold}d "
                    f"conf={exec_result.get('confidence', 0):.0%} "
                    f"— {exec_result['message']}"
                )
                traded_detail = f"{action} — {exec_result['message']}"
                if reasoning_text:
                    traded_detail += f"  ·  why: {reasoning_text}"
                self._set_sym_status(symbol, "traded", traded_detail)
                self.trade_count += 1
                self.notifier.trade_executed(
                    symbol=symbol,
                    action=action,
                    quantity=exec_result["quantity"],
                    price=context.get("price"),
                    order_id=exec_result.get("order_id"),
                    reasoning=reasoning_text,
                    is_demo=self.system.is_demo,
                )
                return True
            elif exec_result["success"]:
                logger.info(f"  {symbol}: HOLD — {exec_result['message']}")
                hold_detail = exec_result["message"]
                if reasoning_text:
                    hold_detail += f"  ·  why: {reasoning_text}"
                self._set_sym_status(symbol, "hold", hold_detail)
                return False
            else:
                logger.warning(f"  {symbol}: blocked — {exec_result['message']}")
                self._set_sym_status(symbol, "hold", exec_result["message"])
                return False

        except Exception as e:
            logger.error(f"Error executing {symbol}: {e}")
            self._set_sym_status(symbol, "error", str(e))
            with self._io_lock:
                self.error_count += 1
            return False

    def run_cycle(self) -> int:
        """Run one analysis pass over all symbols. Returns number of trades executed."""
        logger.info("=" * 60)
        logger.info(f"Cycle started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Pick up any settings changed on the dashboard since the last cycle.
        # The Setup/Risk pages write .env; this applies them live (no restart).
        try:
            changed = Config.reload()
            if changed:
                summary = ", ".join(f"{k} {o}->{n}" for k, (o, n) in changed.items())
                logger.info(f"Config reloaded from .env — {summary}")
        except Exception as e:
            logger.warning(f"Config reload failed: {e}")

        # Check stop-loss / take-profit before analysing new signals
        self._write_state(1, "Risk exits")
        exits = self.system.check_risk_exits()
        for exit_result in exits:
            logger.info(f"  [RISK EXIT] {exit_result.message}")
            self.trade_count += 1
            # Figures are carried on the result (the tracked position has already
            # been removed by the time we get here, so don't re-read it).
            self.notifier.risk_exit(
                symbol=exit_result.symbol,
                exit_type=exit_result.action,
                entry_price=getattr(exit_result, "entry_price", 0.0),
                exit_price=getattr(exit_result, "exit_price", 0.0),
                pnl_pct=getattr(exit_result, "pnl_pct", 0.0),
                is_demo=self.system.is_demo,
            )

        # Periodically run the discovery agent swarm to refresh the explore tier
        self._cycle_count += 1
        if self._cycle_count % Config.DISCOVERY_INTERVAL_CYCLES == 1:
            logger.info("Running discovery agent swarm (Scout -> Analyst -> Risk -> Curator)...")
            try:
                summary = self.swarm.run(cycle=self._cycle_count)
                if summary.get("added"):
                    logger.info(f"Swarm added to explore tier: {', '.join(summary['added'])}")
                if summary.get("evicted"):
                    logger.info(f"Swarm rotated out: {', '.join(summary['evicted'])}")
            except Exception as e:
                logger.warning(f"Discovery swarm failed: {e}")

        # Fetch market regime once for the whole cycle (cached 1h in swing_filters)
        regime = get_market_regime(Config.MARKET_REGIME_SYMBOL)
        regime_label = regime.get("regime", "unknown")
        logger.info(
            f"Market regime: {regime_label.upper()} "
            f"({Config.MARKET_REGIME_SYMBOL} @ ${regime.get('price','?')} "
            f"vs SMA50 ${regime.get('sma50','?')} / SMA200 ${regime.get('sma200','?')})"
        )

        # Screen the watchlist down to the most active symbols this cycle
        self._write_state(2, "Screener")
        tracked = list(self.system.get_tracked_positions().keys())
        all_symbols = self.watchlist.list_symbols()
        focus = Config.in_focus_period()
        if focus:
            logger.info("🔥 FOCUS PERIOD — overdrive: faster scans, more symbols, larger sizing")
        max_syms = Config.FOCUS_SYMBOLS_PER_CYCLE if focus else Config.MAX_SYMBOLS_PER_CYCLE
        symbols = self.screener.top_symbols(
            all_symbols,
            n=max_syms,
            always_include=tracked,
        )
        logger.info(f"Symbols this cycle: {', '.join(symbols)}")

        # Initialise per-symbol queue so the dashboard can show status
        self._init_queue(all_symbols)
        # Mark symbols the screener cut this cycle as not_queued
        for sym in all_symbols:
            if sym not in symbols and self._is_symbol_enabled(sym):
                self._set_sym_status(sym, "not_queued", "screener ranked out")

        trades_this_cycle = len(exits)
        workers = max(1, getattr(Config, "LLM_MAX_WORKERS", 1))
        if workers > 1 and len(symbols) > 1:
            # Phase A — DECIDE in parallel. Fetch context + filters + LLM decision
            # for every symbol concurrently (the LLM is the bottleneck and this
            # stage places no orders, so it's safe to thread).
            self._write_state(4, "Ollama decide", f"{len(symbols)} symbols · {workers}x parallel")
            prepared: List[Dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for p in pool.map(lambda s: self._decide_symbol(s, regime), symbols):
                    if p:
                        prepared.append(p)
            # Phase B — EXECUTE serially. Order placement is cash-aware and must
            # stay single-threaded; free_funds is re-fetched per order.
            for p in prepared:
                if self._execute_symbol(p):
                    trades_this_cycle += 1
                time.sleep(1)
        else:
            for symbol in symbols:
                self._write_state(3, "Fetch context", symbol)
                if self.analyze_symbol(symbol, regime=regime):
                    trades_this_cycle += 1
                time.sleep(2)  # small gap between symbols

        account = self.system.get_account_status()
        if "error" not in account:
            cash = account.get('cash', 0)
            portfolio = account.get('portfolio_value', 0)
            logger.info(f"Cash: ${cash:.2f}  |  Portfolio: ${portfolio:.2f}")
            # Record today's equity snapshot for the profit-projection engine.
            try:
                record_snapshot(portfolio, cash)
            except Exception:
                pass
            self.notifier.cycle_summary(
                cycle=self._cycle_count,
                trades_this_cycle=trades_this_cycle,
                total_trades=self.trade_count,
                cash=cash,
                portfolio_value=portfolio,
                errors=self.error_count,
                is_demo=self.system.is_demo,
            )

        # Persist the full cycle (incl. HOLD / filtered decisions) for night analysis.
        try:
            self.journal.record_cycle(
                cycle=self._cycle_count,
                regime=regime_label,
                account=account if isinstance(account, dict) and "error" not in account else {},
                selected=symbols,
                trades=trades_this_cycle,
                errors=self.error_count,
                in_focus=focus,
                n_screened=len(all_symbols),
            )
        except Exception as e:
            logger.warning(f"Journal record failed: {e}")

        self._write_state(0, "idle")
        logger.info(
            f"Cycle done. This cycle: {trades_this_cycle} trades | "
            f"Total: {self.trade_count} | Errors: {self.error_count}"
        )
        return trades_this_cycle

    def run(self, max_cycles: int = 0) -> None:
        """Run the bot continuously. Set max_cycles=0 for unlimited."""
        if not self.watchlist.list_symbols():
            logger.error("No symbols configured.")
            return

        self.is_running = True
        cycle_count = 0

        logger.info("Starting Trading Bot")
        logger.info(f"Mode: {'DEMO' if self.system.is_demo else 'LIVE'}")

        # Re-adopt any positions still open at the broker from a previous run so
        # their stop-loss / trailing-stop keep being managed after a restart.
        try:
            self.system.executor.sync_with_broker()
        except Exception as e:
            logger.warning(f"Position re-sync failed: {e}")
        if Config.TRADING_SCHEDULE_ENABLED:
            slot = 60 // Config.TRADING_CYCLES_PER_HOUR
            logger.info(
                f"Schedule: Mon-Fri  {Config.TRADING_START_HOUR:02d}:00 - "
                f"{Config.TRADING_END_HOUR:02d}:00  "
                f"every {slot} min ({Config.TRADING_CYCLES_PER_HOUR}x/hour)"
            )
        else:
            logger.info(f"Interval: {self.interval}s (schedule disabled)")

        self.notifier.bot_started(
            symbols=self.watchlist.list_symbols(),
            interval=self.interval,
            is_demo=self.system.is_demo,
        )

        try:
            while self.is_running:
                # ── pause support ──────────────────────────────────────────
                while self._is_paused() and self.is_running:
                    self._write_state(0, "idle", status="paused")
                    time.sleep(2)
                if not self.is_running:
                    break

                # ── standby / trading-hours gate ───────────────────────────
                if not self._is_trading_time():
                    next_dt   = self._next_slot_dt()
                    wait_secs = self._secs_until_next_slot()
                    next_str  = next_dt.strftime("%a %d %b %H:%M")
                    logger.info(
                        f"Standby — next scheduled slot {next_str} "
                        f"({wait_secs // 3600}h {(wait_secs % 3600) // 60}m) | "
                        f"'Run Cycle' button will trigger immediately"
                    )
                    self._write_state(0, "standby", status="standby")
                    # Off-cycle night-shift: file the daily dossier + run the AI
                    # controller once per day after market close (background thread).
                    self._maybe_run_nightly()
                    # Cap the standby sleep so we wake to check the nightly hour
                    # (and re-evaluate trading hours) at most ~30 min later.
                    triggered = self._interruptible_sleep(min(wait_secs, 1800))
                    if not triggered:
                        # Normal timeout — loop back to re-check trading hours
                        continue
                    # Manual trigger outside hours — bypass schedule and run now
                    logger.info("Manual Run Cycle — executing outside scheduled hours")

                # ── daily-trade limit (0 = unlimited / disabled) ───────────
                if Config.MAX_DAILY_TRADES > 0 and self.trade_count >= Config.MAX_DAILY_TRADES:
                    logger.warning(
                        f"Daily trade limit ({Config.MAX_DAILY_TRADES}) reached. "
                        f"Waiting for next session."
                    )
                    self.notifier.daily_limit_reached(Config.MAX_DAILY_TRADES, self.system.is_demo)
                    self._interruptible_sleep(self._secs_until_next_slot())
                    self.trade_count = 0  # reset daily counter for new day
                    continue

                cycle_count += 1
                if max_cycles > 0 and cycle_count > max_cycles:
                    logger.info(f"Reached max cycles ({max_cycles}). Stopping.")
                    break

                try:
                    self.run_cycle()
                except Exception as e:
                    logger.error(f"Cycle error: {e}")
                    self.error_count += 1
                    self.notifier.error(str(e), context=f"Cycle {self._cycle_count}")

                # ── wait until next scheduled slot ─────────────────────────
                # If we're still in trading hours, wait for the next 20-min slot.
                # If we ran a manual cycle outside hours, loop back to standby.
                if self._is_trading_time():
                    wait_secs = self._secs_until_next_slot()
                    next_time = self._next_slot_dt().strftime("%H:%M")
                    logger.info(f"Next cycle at {next_time} ({wait_secs}s)  |  Trades today: {self.trade_count}")
                    self._write_state(0, "idle", status="idle")
                    self._interruptible_sleep(wait_secs)
                else:
                    logger.info("Manual cycle complete — returning to standby")
                    # loop continues → standby gate will sleep until next window

        except KeyboardInterrupt:
            logger.info("Bot stopped by user (Ctrl+C)")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the bot and log final stats."""
        self.is_running = False
        logger.info("=" * 60)
        logger.info(f"Trading Bot Stopped | Total Trades: {self.trade_count} | Errors: {self.error_count}")
        logger.info("=" * 60)
        self.notifier.bot_stopped(self.trade_count, self.error_count)


def main():
    if not Config.TRADING212_API_KEY:
        logger.error("TRADING212_API_KEY environment variable is required!")
        logger.error('Set it: $env:TRADING212_API_KEY = "your_api_key"')
        return

    try:
        logger.info("Initializing Trading System...")
        system = TradingSystem(
            api_key=Config.TRADING212_API_KEY,
            api_secret=Config.TRADING212_API_SECRET,
            ollama_model=Config.OLLAMA_MODEL,
            is_demo=Config.TRADING212_DEMO_MODE,
        )
        logger.info("Trading System initialized")

        account = system.get_account_status()
        if "error" not in account:
            logger.info(f"Cash: ${account.get('cash', 0):.2f}  |  Portfolio: ${account.get('portfolio_value', 0):.2f}")

        watchlist = WatchlistManager(Config.WATCHLIST_FILE)
        logger.info(f"Watchlist: {', '.join(watchlist.list_symbols())}")

        bot = AutoTradingBot(
            trading_system=system,
            watchlist=watchlist,
            interval_seconds=Config.BOT_CYCLE_INTERVAL,  # default 24 h
        )

        bot.run(max_cycles=0)  # unlimited — run daily

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
