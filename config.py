import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration for the trading system"""

    # Trading 212 API
    TRADING212_API_KEY: Optional[str] = os.getenv("TRADING212_API_KEY")
    TRADING212_API_SECRET: Optional[str] = os.getenv("TRADING212_API_SECRET")
    TRADING212_DEMO_MODE: bool = os.getenv("TRADING212_DEMO_MODE", "true").lower() == "true"

    # Ollama Model
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama2")
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
    OLLAMA_MAX_TOKENS: int = int(os.getenv("OLLAMA_MAX_TOKENS", "256"))

    # ── Legacy fallback (used if risk-based sizing can't calculate) ──────────
    DEFAULT_TRADE_QUANTITY: float = float(os.getenv("DEFAULT_TRADE_QUANTITY", "1"))

    # ── Risk management ───────────────────────────────────────────────────────
    MAX_DAILY_TRADES: int    = int(os.getenv("MAX_DAILY_TRADES", "0"))      # 0 = unlimited (no daily cap)
    MIN_ACCOUNT_VALUE: float = float(os.getenv("MIN_ACCOUNT_VALUE", "100"))
    # Percentage-based stops (fallback if ATR-based can't be calculated)
    STOP_LOSS_PCT: float     = float(os.getenv("STOP_LOSS_PCT", "0.06"))    # 6% — swing-appropriate
    TAKE_PROFIT_PCT: float   = float(os.getenv("TAKE_PROFIT_PCT", "0.12"))  # 12% — 2:1 R:R minimum

    # ── "Wait for maximum result" — trailing stop + no churn ─────────────────
    # Instead of dumping a winner at a fixed +12%, trail a stop behind it so it
    # can run as far as it wants and only exits on a pullback from its high.
    TRAILING_STOP_ENABLED:   bool  = os.getenv("TRAILING_STOP_ENABLED", "true").lower() == "true"
    TRAILING_ACTIVATION_PCT: float = float(os.getenv("TRAILING_ACTIVATION_PCT", "0.04"))  # start trailing once +4%
    TRAILING_STOP_PCT:       float = float(os.getenv("TRAILING_STOP_PCT", "0.05"))         # exit on 5% pullback from high
    # Once a position is held, stop letting the LLM re-evaluate/sell it every
    # cycle — let the stop / trailing-stop / take-profit manage the exit instead.
    HOLD_THROUGH_LLM:        bool  = os.getenv("HOLD_THROUGH_LLM", "true").lower() == "true"

    # ── Swing trading: position sizing ───────────────────────────────────────
    RISK_PER_TRADE_PCT: float  = float(os.getenv("RISK_PER_TRADE_PCT", "0.01"))   # 1% of portfolio per trade
    ATR_STOP_MULTIPLIER: float = float(os.getenv("ATR_STOP_MULTIPLIER", "1.5"))   # stop = entry − 1.5×ATR
    MIN_RISK_REWARD: float     = float(os.getenv("MIN_RISK_REWARD", "2.0"))       # skip if target < 2× risk
    MAX_POSITION_PCT: float    = float(os.getenv("MAX_POSITION_PCT", "0.10"))     # single position ≤ 10% of portfolio
    MAX_HOLD_DAYS: int         = int(os.getenv("MAX_HOLD_DAYS", "10"))            # flag trade for review after N days

    # ── Swing trading: pre-trade filters ─────────────────────────────────────
    MARKET_REGIME_SYMBOL: str  = os.getenv("MARKET_REGIME_SYMBOL", "SPY")        # benchmark for regime check
    EARNINGS_BUFFER_DAYS: int  = int(os.getenv("EARNINGS_BUFFER_DAYS", "5"))     # skip if earnings within N days
    MIN_RELATIVE_STRENGTH: float = float(os.getenv("MIN_RELATIVE_STRENGTH", "0.95"))  # RS vs SPY (1.0 = parity)
    MIN_FILTER_SCORE: int      = int(os.getenv("MIN_FILTER_SCORE", "2"))          # min passing filters to proceed
    REGIME_STRICT: bool        = os.getenv("REGIME_STRICT", "false").lower() == "true"  # block ALL buys in bear if true

    # ── Swing trading: cycle cadence ─────────────────────────────────────────
    BOT_CYCLE_INTERVAL: int = int(os.getenv("BOT_CYCLE_INTERVAL", "86400"))      # legacy fallback (ignored when schedule is on)

    # ── Trading schedule ──────────────────────────────────────────────────────
    # Mon–Fri, TRADING_START_HOUR to TRADING_END_HOUR (local time, 24-h clock)
    # TRADING_CYCLES_PER_HOUR cycles per hour (e.g. 3 = every 20 min)
    TRADING_SCHEDULE_ENABLED: bool = os.getenv("TRADING_SCHEDULE_ENABLED", "true").lower() == "true"
    TRADING_START_HOUR:  int = int(os.getenv("TRADING_START_HOUR",  "12"))
    TRADING_END_HOUR:    int = int(os.getenv("TRADING_END_HOUR",   "22"))
    TRADING_CYCLES_PER_HOUR: int = int(os.getenv("TRADING_CYCLES_PER_HOUR", "3"))

    # ── Focus period (US market-open burst → overdrive) ───────────────────────
    # The first ~75 min after the US open (2:30pm BST = 9:30am ET) is the highest
    # volume / volatility window. During it the bot scans faster, screens more
    # symbols, and sizes positions slightly larger to capture the best setups.
    FOCUS_PERIOD_ENABLED:    bool = os.getenv("FOCUS_PERIOD_ENABLED", "true").lower() == "true"
    FOCUS_START_HOUR:        int  = int(os.getenv("FOCUS_START_HOUR", "14"))   # 2:30pm local
    FOCUS_START_MIN:         int  = int(os.getenv("FOCUS_START_MIN",  "30"))
    FOCUS_END_HOUR:          int  = int(os.getenv("FOCUS_END_HOUR",   "15"))   # 3:45pm local
    FOCUS_END_MIN:           int  = int(os.getenv("FOCUS_END_MIN",    "45"))
    FOCUS_CYCLES_PER_HOUR:   int  = int(os.getenv("FOCUS_CYCLES_PER_HOUR",   "12"))  # every 5 min
    FOCUS_SYMBOLS_PER_CYCLE: int  = int(os.getenv("FOCUS_SYMBOLS_PER_CYCLE", "40"))  # screen the whole watchlist
    FOCUS_RISK_PER_TRADE_PCT: float = float(os.getenv("FOCUS_RISK_PER_TRADE_PCT", "0.015"))  # 1.5% vs 1% normal

    # ── Remote / headless operation ───────────────────────────────────────────
    BOT_AUTO_SHUTDOWN: bool     = os.getenv("BOT_AUTO_SHUTDOWN", "false").lower() == "true"
    # Remote dashboard auth — set all three together to enable the login screen
    DASHBOARD_USERNAME: Optional[str] = os.getenv("DASHBOARD_USERNAME")
    DASHBOARD_PASSWORD: Optional[str] = os.getenv("DASHBOARD_PASSWORD")
    DASHBOARD_SECRET:   Optional[str] = os.getenv("DASHBOARD_SECRET")   # becomes the bearer token after login

    # ── Watchlist / Screener ──────────────────────────────────────────────────
    WATCHLIST_FILE: str        = os.getenv("WATCHLIST_FILE", "watchlist.json")
    MAX_SYMBOLS_PER_CYCLE: int = int(os.getenv("MAX_SYMBOLS_PER_CYCLE", "5"))

    # ── Notifications — one webhook per channel ───────────────────────────────
    DISCORD_WEBHOOK_URL: Optional[str]       = os.getenv("DISCORD_WEBHOOK_URL")
    DISCORD_WEBHOOK_TRADES: Optional[str]    = os.getenv("DISCORD_WEBHOOK_TRADES")
    DISCORD_WEBHOOK_RISK: Optional[str]      = os.getenv("DISCORD_WEBHOOK_RISK")
    DISCORD_WEBHOOK_PORTFOLIO: Optional[str] = os.getenv("DISCORD_WEBHOOK_PORTFOLIO")
    DISCORD_WEBHOOK_DISCOVERY: Optional[str] = os.getenv("DISCORD_WEBHOOK_DISCOVERY")
    DISCORD_WEBHOOK_ALERTS: Optional[str]    = os.getenv("DISCORD_WEBHOOK_ALERTS")

    # ── Discovery ─────────────────────────────────────────────────────────────
    DISCOVERY_INTERVAL_CYCLES: int = int(os.getenv("DISCOVERY_INTERVAL_CYCLES", "7"))  # weekly discovery
    DISCOVERY_TOP_N: int           = int(os.getenv("DISCOVERY_TOP_N", "10"))
    MAX_WATCHLIST_SIZE: int        = int(os.getenv("MAX_WATCHLIST_SIZE", "250"))

    # ── Core / Explore watchlist model ────────────────────────────────────────
    # 200 permanently-tracked "core" symbols + up to 50 dynamic "explore" slots
    # that the discovery swarm fills with its best fresh finds.
    CORE_WATCHLIST_SIZE: int = int(os.getenv("CORE_WATCHLIST_SIZE", "200"))
    EXPLORE_SLOTS: int       = int(os.getenv("EXPLORE_SLOTS", "50"))

    # ── Discovery agent swarm ─────────────────────────────────────────────────
    AGENT_DB_PATH: str = os.getenv("AGENT_DB_PATH", "agent_activity.db")

    # ── LLM concurrency (parallel decisions) ──────────────────────────────────
    # The RTX 4060 (8GB) fits ~4 concurrent llama3.2 (1.9GB) requests. Decisions
    # for the bounded candidate set are dispatched via a thread pool; order
    # execution stays serial. OLLAMA_NUM_PARALLEL must match in the launcher.
    LLM_MAX_WORKERS: int     = int(os.getenv("LLM_MAX_WORKERS", "4"))
    OLLAMA_NUM_PARALLEL: int = int(os.getenv("OLLAMA_NUM_PARALLEL", "4"))

    # ── Night-shift AI controller (runs after market close, off the cycle) ────
    # Captures all daily data to journal.db, files a daily dossier, and a nightly
    # controller reviews performance + the codebase (READ-ONLY) to suggest
    # features/improvements and clamped parameter changes. Advisory by default.
    JOURNAL_DB_PATH: str       = os.getenv("JOURNAL_DB_PATH", "journal.db")
    REPORTS_DIR: str           = os.getenv("REPORTS_DIR", "reports")
    NIGHTLY_ANALYSIS_HOUR: int = int(os.getenv("NIGHTLY_ANALYSIS_HOUR", "22"))   # local hour, after 21:00 close
    CONTROLLER_MODEL: str      = os.getenv("CONTROLLER_MODEL", "0xroyce/plutus:latest")
    CONTROLLER_AUTO_APPLY: bool = os.getenv("CONTROLLER_AUTO_APPLY", "false").lower() == "true"
    CONTROLLER_LOOKBACK_DAYS: int = int(os.getenv("CONTROLLER_LOOKBACK_DAYS", "14"))

    @classmethod
    def in_focus_period(cls) -> bool:
        """True if right now is inside the Mon–Fri market-open focus window."""
        if not cls.FOCUS_PERIOD_ENABLED:
            return False
        from datetime import datetime
        now = datetime.now()
        if now.weekday() >= 5:          # weekend
            return False
        start = now.replace(hour=cls.FOCUS_START_HOUR, minute=cls.FOCUS_START_MIN,
                            second=0, microsecond=0)
        end   = now.replace(hour=cls.FOCUS_END_HOUR,   minute=cls.FOCUS_END_MIN,
                            second=0, microsecond=0)
        return start <= now < end

    @classmethod
    def validate(cls) -> bool:
        if not cls.TRADING212_API_KEY:
            print("Warning: TRADING212_API_KEY not set.")
            return False
        return True

    # Keys the dashboard Setup/Risk pages can edit — kept in sync with
    # dashboard.py's _EDITABLE_KEYS so they can be reloaded live.
    _RELOADABLE = (
        "OLLAMA_MODEL", "OLLAMA_TEMPERATURE", "OLLAMA_MAX_TOKENS",
        "TRADING212_DEMO_MODE", "MIN_ACCOUNT_VALUE",
        "STOP_LOSS_PCT", "TAKE_PROFIT_PCT", "RISK_PER_TRADE_PCT",
        "ATR_STOP_MULTIPLIER", "MIN_RISK_REWARD", "MAX_POSITION_PCT", "MAX_HOLD_DAYS",
        "EARNINGS_BUFFER_DAYS", "MIN_RELATIVE_STRENGTH", "MIN_FILTER_SCORE",
        "REGIME_STRICT", "MARKET_REGIME_SYMBOL", "BOT_CYCLE_INTERVAL",
        "MAX_SYMBOLS_PER_CYCLE", "DISCOVERY_INTERVAL_CYCLES",
        "DISCOVERY_TOP_N", "MAX_WATCHLIST_SIZE",
        "CORE_WATCHLIST_SIZE", "EXPLORE_SLOTS", "LLM_MAX_WORKERS",
    )

    @classmethod
    def reload(cls) -> dict:
        """Re-read the user-editable settings from .env at runtime.

        Lets changes saved on the dashboard Setup/Risk pages take effect on the
        next bot cycle without a full restart. Returns a dict of {key: (old, new)}
        for any values that actually changed (empty if nothing changed).
        """
        before = {k: getattr(cls, k) for k in cls._RELOADABLE}
        load_dotenv(override=True)
        g = os.getenv
        # Model
        cls.OLLAMA_MODEL        = g("OLLAMA_MODEL", "llama2")
        cls.OLLAMA_TEMPERATURE  = float(g("OLLAMA_TEMPERATURE", "0.2"))
        cls.OLLAMA_MAX_TOKENS   = int(g("OLLAMA_MAX_TOKENS", "256"))
        # Broker
        cls.TRADING212_DEMO_MODE = g("TRADING212_DEMO_MODE", "true").lower() == "true"
        # Core risk
        cls.MIN_ACCOUNT_VALUE   = float(g("MIN_ACCOUNT_VALUE", "100"))
        cls.STOP_LOSS_PCT       = float(g("STOP_LOSS_PCT", "0.06"))
        cls.TAKE_PROFIT_PCT     = float(g("TAKE_PROFIT_PCT", "0.12"))
        # Swing position sizing
        cls.RISK_PER_TRADE_PCT  = float(g("RISK_PER_TRADE_PCT", "0.01"))
        cls.ATR_STOP_MULTIPLIER = float(g("ATR_STOP_MULTIPLIER", "1.5"))
        cls.MIN_RISK_REWARD     = float(g("MIN_RISK_REWARD", "2.0"))
        cls.MAX_POSITION_PCT    = float(g("MAX_POSITION_PCT", "0.10"))
        cls.MAX_HOLD_DAYS       = int(g("MAX_HOLD_DAYS", "10"))
        # Swing filters
        cls.EARNINGS_BUFFER_DAYS  = int(g("EARNINGS_BUFFER_DAYS", "5"))
        cls.MIN_RELATIVE_STRENGTH = float(g("MIN_RELATIVE_STRENGTH", "0.95"))
        cls.MIN_FILTER_SCORE      = int(g("MIN_FILTER_SCORE", "2"))
        cls.REGIME_STRICT         = g("REGIME_STRICT", "false").lower() == "true"
        cls.MARKET_REGIME_SYMBOL  = g("MARKET_REGIME_SYMBOL", "SPY")
        # Cycle
        cls.BOT_CYCLE_INTERVAL    = int(g("BOT_CYCLE_INTERVAL", "86400"))
        # Screener / discovery
        cls.MAX_SYMBOLS_PER_CYCLE     = int(g("MAX_SYMBOLS_PER_CYCLE", "5"))
        cls.DISCOVERY_INTERVAL_CYCLES = int(g("DISCOVERY_INTERVAL_CYCLES", "7"))
        cls.DISCOVERY_TOP_N           = int(g("DISCOVERY_TOP_N", "10"))
        cls.MAX_WATCHLIST_SIZE        = int(g("MAX_WATCHLIST_SIZE", "250"))
        # Core / explore + LLM concurrency
        cls.CORE_WATCHLIST_SIZE       = int(g("CORE_WATCHLIST_SIZE", "200"))
        cls.EXPLORE_SLOTS             = int(g("EXPLORE_SLOTS", "50"))
        cls.LLM_MAX_WORKERS           = int(g("LLM_MAX_WORKERS", "4"))
        after = {k: getattr(cls, k) for k in cls._RELOADABLE}
        return {k: (before[k], after[k]) for k in cls._RELOADABLE if before[k] != after[k]}

    @classmethod
    def print_config(cls) -> None:
        print("Swing Trading Bot — Configuration:")
        print(f"  Mode:               {'DEMO' if cls.TRADING212_DEMO_MODE else 'LIVE'}")
        print(f"  Model:              {cls.OLLAMA_MODEL}  t={cls.OLLAMA_TEMPERATURE}")
        print(f"  Cycle interval:     {cls.BOT_CYCLE_INTERVAL}s ({cls.BOT_CYCLE_INTERVAL//3600}h)")
        print(f"  Risk per trade:     {cls.RISK_PER_TRADE_PCT*100:.1f}% of portfolio")
        print(f"  ATR stop mult:      {cls.ATR_STOP_MULTIPLIER}×  |  Min R:R: {cls.MIN_RISK_REWARD}:1")
        print(f"  Max hold days:      {cls.MAX_HOLD_DAYS}")
        print(f"  Earnings buffer:    {cls.EARNINGS_BUFFER_DAYS} days")
        print(f"  Min filter score:   {cls.MIN_FILTER_SCORE}/4")
        print(f"  Regime (strict):    {cls.REGIME_STRICT}")
