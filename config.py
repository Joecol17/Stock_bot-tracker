import os
from typing import Optional


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
