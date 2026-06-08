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
    MAX_WATCHLIST_SIZE: int        = int(os.getenv("MAX_WATCHLIST_SIZE", "20"))

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
