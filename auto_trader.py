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


class AutoTradingBot:
    """Automated trading bot using Ollama decisions."""

    def __init__(
        self,
        trading_system: TradingSystem,
        symbols: List[str],
        interval_seconds: int = 300,
    ):
        """
        Initialize the trading bot.
        
        Args:
            trading_system: Initialized TradingSystem instance
            symbols: List of symbols to monitor (e.g., ["AAPL", "GOOGL"])
            interval_seconds: Seconds between analysis cycles (default 300 = 5 min)
        """
        self.system = trading_system
        self.symbols = symbols
        self.interval = interval_seconds
        self.is_running = False
        self.trade_count = 0
        self.error_count = 0

    def get_market_context(self, symbol: str) -> Dict[str, Any]:
        """
        Get market context for a symbol.
        In a real system, this would fetch live market data.
        For demo, uses sample data.
        """
        # TODO: In production, integrate with a real market data provider
        # like yfinance, Alpha Vantage, etc.
        
        sample_contexts = {
            "AAPL": {
                "symbol": "AAPL",
                "price": 178.23,
                "trend": "uptrend",
                "news_headline": "Apple reports strong services growth",
                "volume": "high",
                "risk_tolerance": "medium",
                "support_level": 170.00,
                "resistance_level": 185.00,
            },
            "GOOGL": {
                "symbol": "GOOGL",
                "price": 142.50,
                "trend": "neutral",
                "news_headline": "Google faces regulatory scrutiny",
                "volume": "normal",
                "risk_tolerance": "medium",
                "support_level": 135.00,
                "resistance_level": 150.00,
            },
            "MSFT": {
                "symbol": "MSFT",
                "price": 380.00,
                "trend": "downtrend",
                "news_headline": "Microsoft AI investment increases competition",
                "volume": "low",
                "risk_tolerance": "medium",
                "support_level": 370.00,
                "resistance_level": 395.00,
            },
        }
        
        return sample_contexts.get(symbol, {
            "symbol": symbol,
            "price": 0,
            "trend": "neutral",
            "news_headline": "No data available",
            "volume": "normal",
            "risk_tolerance": "medium",
        })

    def analyze_symbol(self, symbol: str) -> bool:
        """
        Analyze a single symbol and execute trade if appropriate.
        
        Returns:
            True if trade executed, False otherwise
        """
        try:
            logger.info(f"Analyzing {symbol}...")
            
            # Get market context
            context = self.get_market_context(symbol)
            
            # Execute decision and trade
            result = self.system.analyze_and_trade(
                symbol=symbol,
                context=context,
                quantity=Config.DEFAULT_TRADE_QUANTITY,
            )
            
            # Log result
            exec_result = result['execution']
            if exec_result['success']:
                logger.info(f"✓ {symbol}: {exec_result['action']} - {exec_result['message']}")
                self.trade_count += 1
                return True
            else:
                logger.warning(f"⚠ {symbol}: {exec_result['message']}")
                return False
        
        except Exception as e:
            logger.error(f"✗ Error analyzing {symbol}: {e}")
            self.error_count += 1
            return False

    def run_cycle(self) -> int:
        """
        Execute one analysis cycle for all symbols.
        
        Returns:
            Number of trades executed in this cycle
        """
        logger.info("=" * 60)
        logger.info(f"Starting analysis cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        
        trades_this_cycle = 0
        for symbol in self.symbols:
            if self.analyze_symbol(symbol):
                trades_this_cycle += 1
            
            # Small delay between analyses to avoid rate limiting
            time.sleep(1)
        
        # Log cycle summary
        account = self.system.get_account_status()
        if "error" not in account:
            logger.info(f"Account Balance: ${account.get('cash', 0):.2f}")
            logger.info(f"Portfolio Value: ${account.get('portfolio_value', 0):.2f}")
        
        logger.info(f"Cycle complete. Trades: {trades_this_cycle}, "
                   f"Total: {self.trade_count}, Errors: {self.error_count}")
        
        return trades_this_cycle

    def run(self, max_cycles: int = 0) -> None:
        """
        Run the trading bot continuously.
        
        Args:
            max_cycles: Maximum cycles to run (0 = unlimited)
        """
        if not self.symbols:
            logger.error("No symbols configured. Please provide symbols to trade.")
            return
        
        self.is_running = True
        cycle_count = 0
        
        logger.info(f"Starting Trading Bot")
        logger.info(f"Mode: {'DEMO' if self.system.is_demo else 'LIVE'}")
        logger.info(f"Interval: {self.interval} seconds")
        logger.info(f"Max cycles: {max_cycles if max_cycles > 0 else 'Unlimited'}")
        
        try:
            while self.is_running:
                cycle_count += 1
                
                # Check max cycles limit
                if max_cycles > 0 and cycle_count > max_cycles:
                    logger.info(f"Reached max cycles ({max_cycles}). Stopping.")
                    break
                
                # Check daily trade limit
                if self.trade_count >= Config.MAX_DAILY_TRADES:
                    logger.warning(f"Daily trade limit ({Config.MAX_DAILY_TRADES}) reached. "
                                 f"Stopping for today.")
                    break
                
                # Run analysis cycle
                try:
                    self.run_cycle()
                except Exception as e:
                    logger.error(f"Cycle error: {e}")
                    self.error_count += 1
                
                # Wait for next cycle
                logger.info(f"Waiting {self.interval} seconds until next cycle...")
                time.sleep(self.interval)
        
        except KeyboardInterrupt:
            logger.info("Bot stopped by user (Ctrl+C)")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the trading bot."""
        self.is_running = False
        logger.info("=" * 60)
        logger.info("Trading Bot Stopped")
        logger.info(f"Total Trades: {self.trade_count}")
        logger.info(f"Total Errors: {self.error_count}")
        logger.info("=" * 60)


def main():
    """Main entry point for automated trading."""
    
    # Validate configuration
    if not Config.TRADING212_API_KEY:
        logger.error("TRADING212_API_KEY environment variable is required!")
        logger.error("Set it in Windows PowerShell:")
        logger.error('  $env:TRADING212_API_KEY = "your_api_key"')
        return
    
    try:
        # Initialize trading system
        logger.info("Initializing Trading System...")
        system = TradingSystem(
            api_key=Config.TRADING212_API_KEY,
            ollama_model=Config.OLLAMA_MODEL,
            is_demo=Config.TRADING212_DEMO_MODE,
        )
        logger.info("✓ Trading System initialized")
        
        # Check account
        account = system.get_account_status()
        if "error" not in account:
            logger.info(f"Account Balance: ${account.get('cash', 0):.2f}")
            logger.info(f"Portfolio Value: ${account.get('portfolio_value', 0):.2f}")
        
        # Create and configure bot
        symbols = ["AAPL", "GOOGL", "MSFT"]  # Customize as needed
        
        bot = AutoTradingBot(
            trading_system=system,
            symbols=symbols,
            interval_seconds=300,  # 5 minutes between cycles
        )
        
        # Run bot (limit to 10 cycles for demo)
        logger.info(f"Starting automated trading with symbols: {symbols}")
        bot.run(max_cycles=10)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
