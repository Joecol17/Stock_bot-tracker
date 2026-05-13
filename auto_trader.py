"""
Automated trading loop - continuously monitors and trades based on market analysis.
Uses Ollama for decision-making and Trading 212 API for execution.
"""

import time
import logging
from datetime import datetime
from typing import List, Dict, Any
from trading_system import TradingSystem
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


def get_market_context(symbol: str) -> Dict[str, Any]:
    """Fetch live market context for a symbol using yfinance."""
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", interval="1h")
        info = ticker.fast_info

        if hist.empty:
            raise ValueError(f"No price data returned for {symbol}")

        current_price = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price

        # Trend from last 5 hourly closes
        closes = hist["Close"].tail(5).tolist()
        if len(closes) >= 2:
            if closes[-1] > closes[0] * 1.01:
                trend = "uptrend"
            elif closes[-1] < closes[0] * 0.99:
                trend = "downtrend"
            else:
                trend = "neutral"
        else:
            trend = "neutral"

        # Volume compared to recent average
        avg_volume = float(hist["Volume"].mean())
        last_volume = float(hist["Volume"].iloc[-1])
        if avg_volume > 0:
            if last_volume > avg_volume * 1.5:
                volume = "high"
            elif last_volume < avg_volume * 0.5:
                volume = "low"
            else:
                volume = "normal"
        else:
            volume = "normal"

        # Support / resistance from recent 20-bar range
        recent_high = float(hist["High"].tail(20).max())
        recent_low = float(hist["Low"].tail(20).min())

        change_pct = round((current_price - prev_close) / prev_close * 100, 2) if prev_close else 0

        return {
            "symbol": symbol,
            "price": round(current_price, 4),
            "prev_close": round(prev_close, 4),
            "change_pct": change_pct,
            "trend": trend,
            "volume": volume,
            "support_level": round(recent_low, 4),
            "resistance_level": round(recent_high, 4),
            "52w_high": getattr(info, "year_high", None),
            "52w_low": getattr(info, "year_low", None),
            "market_cap": getattr(info, "market_cap", None),
            "risk_tolerance": "medium",
        }

    except Exception as e:
        logger.warning(f"Could not fetch market data for {symbol}: {e}")
        return {
            "symbol": symbol,
            "price": 0,
            "trend": "neutral",
            "volume": "normal",
            "risk_tolerance": "medium",
            "data_error": str(e),
        }


class AutoTradingBot:
    """Automated trading bot using Ollama decisions and live market data."""

    def __init__(
        self,
        trading_system: TradingSystem,
        symbols: List[str],
        interval_seconds: int = 300,
    ):
        self.system = trading_system
        self.symbols = symbols
        self.interval = interval_seconds
        self.is_running = False
        self.trade_count = 0
        self.error_count = 0

    def analyze_symbol(self, symbol: str) -> bool:
        """Analyse one symbol and execute a trade if appropriate. Returns True if a trade ran."""
        try:
            logger.info(f"Analyzing {symbol}...")
            context = get_market_context(symbol)

            if context.get("price", 0) == 0:
                logger.warning(f"Skipping {symbol}: no live price data available")
                return False

            result = self.system.analyze_and_trade(
                symbol=symbol,
                context=context,
                quantity=Config.DEFAULT_TRADE_QUANTITY,
            )

            exec_result = result['execution']
            if exec_result['success']:
                logger.info(f"  {symbol}: {exec_result['action']} - {exec_result['message']}")
                self.trade_count += 1
                return True
            else:
                logger.warning(f"  {symbol}: {exec_result['message']}")
                return False

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            self.error_count += 1
            return False

    def run_cycle(self) -> int:
        """Run one analysis pass over all symbols. Returns number of trades executed."""
        logger.info("=" * 60)
        logger.info(f"Cycle started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")

        trades_this_cycle = 0
        for symbol in self.symbols:
            if self.analyze_symbol(symbol):
                trades_this_cycle += 1
            time.sleep(1)  # small gap to avoid API rate limits

        account = self.system.get_account_status()
        if "error" not in account:
            logger.info(f"Cash: ${account.get('cash', 0):.2f}  |  Portfolio: ${account.get('portfolio_value', 0):.2f}")

        logger.info(
            f"Cycle done. This cycle: {trades_this_cycle} trades | "
            f"Total: {self.trade_count} | Errors: {self.error_count}"
        )
        return trades_this_cycle

    def run(self, max_cycles: int = 0) -> None:
        """Run the bot continuously. Set max_cycles=0 for unlimited."""
        if not self.symbols:
            logger.error("No symbols configured.")
            return

        self.is_running = True
        cycle_count = 0

        logger.info("Starting Trading Bot")
        logger.info(f"Mode: {'DEMO' if self.system.is_demo else 'LIVE'}")
        logger.info(f"Interval: {self.interval}s  |  Max cycles: {max_cycles if max_cycles > 0 else 'unlimited'}")

        try:
            while self.is_running:
                cycle_count += 1

                if max_cycles > 0 and cycle_count > max_cycles:
                    logger.info(f"Reached max cycles ({max_cycles}). Stopping.")
                    break

                if self.trade_count >= Config.MAX_DAILY_TRADES:
                    logger.warning(f"Daily trade limit ({Config.MAX_DAILY_TRADES}) reached. Stopping.")
                    break

                try:
                    self.run_cycle()
                except Exception as e:
                    logger.error(f"Cycle error: {e}")
                    self.error_count += 1

                logger.info(f"Waiting {self.interval}s until next cycle...")
                time.sleep(self.interval)

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


def main():
    if not Config.TRADING212_API_KEY or not Config.TRADING212_API_SECRET:
        logger.error("TRADING212_API_KEY and TRADING212_API_SECRET are both required!")
        logger.error("Set them in your .env file.")
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

        symbols = ["AAPL", "GOOGL", "MSFT"]  # customise as needed

        bot = AutoTradingBot(
            trading_system=system,
            symbols=symbols,
            interval_seconds=300,
        )

        bot.run(max_cycles=10)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
