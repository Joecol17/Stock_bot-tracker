"""
Automated trading loop - continuously monitors and trades based on market analysis.
Uses Ollama for decision-making and Trading 212 API for execution.
"""

import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from trading_system import TradingSystem
from watchlist import WatchlistManager, Screener
from discovery import StockDiscovery
from notifier import DiscordNotifier
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
    """Fetch live market context and technical indicators for a symbol using yfinance."""
    try:
        import yfinance as yf
        import ta

        ticker = yf.Ticker(symbol)
        # 60 days of hourly data — enough for SMA50, MACD(26), RSI(14)
        hist = ticker.history(period="60d", interval="1h")
        info = ticker.fast_info

        if hist.empty:
            raise ValueError(f"No price data returned for {symbol}")

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]

        current_price = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) > 1 else current_price

        # Trend from last 5 hourly closes
        closes = close.tail(5).tolist()
        if len(closes) >= 2:
            if closes[-1] > closes[0] * 1.01:
                trend = "uptrend"
            elif closes[-1] < closes[0] * 0.99:
                trend = "downtrend"
            else:
                trend = "neutral"
        else:
            trend = "neutral"

        # Volume vs recent average
        avg_vol = float(volume.mean())
        last_vol = float(volume.iloc[-1])
        if avg_vol > 0:
            if last_vol > avg_vol * 1.5:
                vol_label = "high"
            elif last_vol < avg_vol * 0.5:
                vol_label = "low"
            else:
                vol_label = "normal"
        else:
            vol_label = "normal"

        # Support / resistance from recent 20-bar range
        recent_high = float(high.tail(20).max())
        recent_low = float(low.tail(20).min())
        change_pct = round((current_price - prev_close) / prev_close * 100, 2) if prev_close else 0

        # --- Technical indicators ---
        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
        rsi = _safe_float(rsi_series)

        macd_obj = ta.trend.MACD(close, window_fast=12, window_slow=26, window_sign=9)
        macd_line = _safe_float(macd_obj.macd())
        macd_signal = _safe_float(macd_obj.macd_signal())
        macd_hist = _safe_float(macd_obj.macd_diff())

        sma20 = _safe_float(ta.trend.SMAIndicator(close, window=20).sma_indicator())
        sma50 = _safe_float(ta.trend.SMAIndicator(close, window=50).sma_indicator())

        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        bb_upper = _safe_float(bb.bollinger_hband())
        bb_lower = _safe_float(bb.bollinger_lband())
        bb_mid = _safe_float(bb.bollinger_mavg())

        # Derived signals to help the LLM
        bb_position = None
        if bb_upper and bb_lower and bb_upper != bb_lower:
            bb_position = round((current_price - bb_lower) / (bb_upper - bb_lower), 4)

        price_vs_sma20 = round((current_price / sma20 - 1) * 100, 2) if sma20 else None
        price_vs_sma50 = round((current_price / sma50 - 1) * 100, 2) if sma50 else None

        macd_crossover = None
        if macd_line is not None and macd_signal is not None:
            if macd_line > macd_signal:
                macd_crossover = "bullish"
            elif macd_line < macd_signal:
                macd_crossover = "bearish"
            else:
                macd_crossover = "neutral"

        return {
            "symbol": symbol,
            "price": round(current_price, 4),
            "prev_close": round(prev_close, 4),
            "change_pct": change_pct,
            "trend": trend,
            "volume": vol_label,
            "support_level": round(recent_low, 4),
            "resistance_level": round(recent_high, 4),
            "52w_high": getattr(info, "year_high", None),
            "52w_low": getattr(info, "year_low", None),
            "market_cap": getattr(info, "market_cap", None),
            "risk_tolerance": "medium",
            # Technical indicators
            "rsi_14": rsi,
            "macd_line": macd_line,
            "macd_signal": macd_signal,
            "macd_histogram": macd_hist,
            "macd_crossover": macd_crossover,
            "sma_20": sma20,
            "sma_50": sma50,
            "price_vs_sma20_pct": price_vs_sma20,
            "price_vs_sma50_pct": price_vs_sma50,
            "bb_upper": bb_upper,
            "bb_mid": bb_mid,
            "bb_lower": bb_lower,
            "bb_position": bb_position,  # 0=at lower band, 1=at upper band
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
        self.interval = interval_seconds
        self.is_running = False
        self.trade_count = 0
        self.error_count = 0
        self._cycle_count = 0

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
            action = exec_result['action']
            if exec_result['success'] and action in ("BUY", "SELL"):
                logger.info(f"  {symbol}: {action} - {exec_result['message']}")
                self.trade_count += 1
                reasoning = result.get('decision', {}).get('decision', {})
                reasoning_text = reasoning.get('reasoning') if isinstance(reasoning, dict) else None
                self.notifier.trade_executed(
                    symbol=symbol,
                    action=action,
                    quantity=exec_result['quantity'],
                    price=context.get('price'),
                    order_id=exec_result.get('order_id'),
                    reasoning=reasoning_text,
                    is_demo=self.system.is_demo,
                )
                return True
            elif exec_result['success']:
                logger.info(f"  {symbol}: {action} - {exec_result['message']}")
                return False
            else:
                logger.warning(f"  {symbol}: {exec_result['message']}")
                return False

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            self.error_count += 1
            self.notifier.error(str(e), context=f"Symbol: {symbol}")
            return False

    def run_cycle(self) -> int:
        """Run one analysis pass over all symbols. Returns number of trades executed."""
        logger.info("=" * 60)
        logger.info(f"Cycle started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Check stop-loss / take-profit before analysing new signals
        exits = self.system.check_risk_exits()
        for exit_result in exits:
            logger.info(f"  [RISK EXIT] {exit_result.message}")
            self.trade_count += 1
            # Parse P/L % from the message for the notification
            try:
                pct_part = exit_result.message.split("(")[-1].rstrip(")")
                pnl_pct = float(pct_part.replace("%", "").replace("+", ""))
            except Exception:
                pnl_pct = 0.0
            tracked = self.system.get_tracked_positions().get(exit_result.symbol, {})
            self.notifier.risk_exit(
                symbol=exit_result.symbol,
                exit_type=exit_result.action,
                entry_price=tracked.get("entry_price", 0),
                exit_price=tracked.get("stop_loss" if exit_result.action == "STOP_LOSS" else "take_profit", 0),
                pnl_pct=pnl_pct,
                is_demo=self.system.is_demo,
            )

        # Periodically discover new stocks and auto-add to watchlist
        self._cycle_count += 1
        if self._cycle_count % Config.DISCOVERY_INTERVAL_CYCLES == 1:
            logger.info("Running stock discovery...")
            added = self.discovery.auto_populate_watchlist(
                self.watchlist,
                top_n=Config.DISCOVERY_TOP_N,
                max_watchlist_size=Config.MAX_WATCHLIST_SIZE,
            )
            if added:
                logger.info(f"Discovery added to watchlist: {', '.join(added)}")
                self.notifier.discovery_update(added, len(self.watchlist.list_symbols()))

        # Screen the watchlist down to the most active symbols this cycle
        tracked = list(self.system.get_tracked_positions().keys())
        symbols = self.screener.top_symbols(
            self.watchlist.list_symbols(),
            n=Config.MAX_SYMBOLS_PER_CYCLE,
            always_include=tracked,
        )
        logger.info(f"Symbols this cycle: {', '.join(symbols)}")

        trades_this_cycle = len(exits)
        for symbol in symbols:
            if self.analyze_symbol(symbol):
                trades_this_cycle += 1
            time.sleep(1)  # small gap to avoid API rate limits

        account = self.system.get_account_status()
        if "error" not in account:
            cash = account.get('cash', 0)
            portfolio = account.get('portfolio_value', 0)
            logger.info(f"Cash: ${cash:.2f}  |  Portfolio: ${portfolio:.2f}")
            self.notifier.cycle_summary(
                cycle=self._cycle_count,
                trades_this_cycle=trades_this_cycle,
                total_trades=self.trade_count,
                cash=cash,
                portfolio_value=portfolio,
                errors=self.error_count,
                is_demo=self.system.is_demo,
            )

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
        logger.info(f"Interval: {self.interval}s  |  Max cycles: {max_cycles if max_cycles > 0 else 'unlimited'}")
        self.notifier.bot_started(
            symbols=self.watchlist.list_symbols(),
            interval=self.interval,
            is_demo=self.system.is_demo,
        )

        try:
            while self.is_running:
                cycle_count += 1

                if max_cycles > 0 and cycle_count > max_cycles:
                    logger.info(f"Reached max cycles ({max_cycles}). Stopping.")
                    break

                if self.trade_count >= Config.MAX_DAILY_TRADES:
                    logger.warning(f"Daily trade limit ({Config.MAX_DAILY_TRADES}) reached. Stopping.")
                    self.notifier.daily_limit_reached(Config.MAX_DAILY_TRADES, self.system.is_demo)
                    break

                try:
                    self.run_cycle()
                except Exception as e:
                    logger.error(f"Cycle error: {e}")
                    self.error_count += 1
                    self.notifier.error(str(e), context=f"Cycle {self._cycle_count}")

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
            interval_seconds=300,
        )

        bot.run(max_cycles=10)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
