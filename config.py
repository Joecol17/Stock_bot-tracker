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
    MAX_DAILY_TRADES: int    = int(os.getenv("MAX_DAILY_TRADES", "5"))      # fewer, higher-quality swings
    MIN_ACCOUNT_VALUE: float = float(os.getenv("MIN_ACCOUNT_VALUE", "100"))
    # Percentage-based stops (fallback if ATR-based can't be calculated)
    STOP_LOSS_PCT: float     = float(os.getenv("STOP_LOSS_PCT", "0.06"))    # 6% — swing-appropriate
    TAKE_PROFIT_PCT: float   = float(os.getenv("TAKE_PROFIT_PCT", "0.12"))  # 12% — 2:1 R:R minimum

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
