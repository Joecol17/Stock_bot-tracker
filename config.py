import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration for the trading system"""

    # Trading 212 API
    TRADING212_API_KEY: Optional[str] = os.getenv("TRADING212_API_KEY")
    TRADING212_DEMO_MODE: bool = os.getenv("TRADING212_DEMO_MODE", "true").lower() == "true"

    # Ollama Model
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama2")
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
    OLLAMA_MAX_TOKENS: int = int(os.getenv("OLLAMA_MAX_TOKENS", "256"))

    # Trading Parameters
    DEFAULT_TRADE_QUANTITY: float = float(os.getenv("DEFAULT_TRADE_QUANTITY", "1"))
    
    # Risk Management
    MAX_DAILY_TRADES: int = int(os.getenv("MAX_DAILY_TRADES", "10"))
    MIN_ACCOUNT_VALUE: float = float(os.getenv("MIN_ACCOUNT_VALUE", "100"))
    STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "0.03"))    # 3% below entry
    TAKE_PROFIT_PCT: float = float(os.getenv("TAKE_PROFIT_PCT", "0.05"))  # 5% above entry

    # Watchlist / Screener
    WATCHLIST_FILE: str = os.getenv("WATCHLIST_FILE", "watchlist.json")
    MAX_SYMBOLS_PER_CYCLE: int = int(os.getenv("MAX_SYMBOLS_PER_CYCLE", "5"))

    # Notifications — one webhook per channel (fall back to DISCORD_WEBHOOK_URL if not set)
    DISCORD_WEBHOOK_URL: Optional[str] = os.getenv("DISCORD_WEBHOOK_URL")       # fallback / general
    DISCORD_WEBHOOK_TRADES: Optional[str] = os.getenv("DISCORD_WEBHOOK_TRADES")      # #trades
    DISCORD_WEBHOOK_RISK: Optional[str] = os.getenv("DISCORD_WEBHOOK_RISK")          # #risk-exits
    DISCORD_WEBHOOK_PORTFOLIO: Optional[str] = os.getenv("DISCORD_WEBHOOK_PORTFOLIO")  # #portfolio
    DISCORD_WEBHOOK_DISCOVERY: Optional[str] = os.getenv("DISCORD_WEBHOOK_DISCOVERY")  # #discovery
    DISCORD_WEBHOOK_ALERTS: Optional[str] = os.getenv("DISCORD_WEBHOOK_ALERTS")      # #alerts

    # Discovery
    DISCOVERY_INTERVAL_CYCLES: int = int(os.getenv("DISCOVERY_INTERVAL_CYCLES", "6"))  # run every N cycles
    DISCOVERY_TOP_N: int = int(os.getenv("DISCOVERY_TOP_N", "10"))          # candidates to add per run
    MAX_WATCHLIST_SIZE: int = int(os.getenv("MAX_WATCHLIST_SIZE", "20"))     # cap on watchlist length

    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is set."""
        if not cls.TRADING212_API_KEY:
            print("Warning: TRADING212_API_KEY not set. Set it via environment variable.")
            return False
        return True

    @classmethod
    def print_config(cls) -> None:
        """Print current configuration (without API key)."""
        print("Configuration:")
        print(f"  Trading 212 Demo Mode: {cls.TRADING212_DEMO_MODE}")
        print(f"  Ollama Model: {cls.OLLAMA_MODEL}")
        print(f"  Temperature: {cls.OLLAMA_TEMPERATURE}")
        print(f"  Max Tokens: {cls.OLLAMA_MAX_TOKENS}")
        print(f"  Default Trade Quantity: {cls.DEFAULT_TRADE_QUANTITY}")
        print(f"  Max Daily Trades: {cls.MAX_DAILY_TRADES}")
        print(f"  Stop Loss: {cls.STOP_LOSS_PCT * 100:.1f}%")
        print(f"  Take Profit: {cls.TAKE_PROFIT_PCT * 100:.1f}%")
