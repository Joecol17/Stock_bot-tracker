"""
Integrated trading system combining decision engine with order execution.
"""

from typing import Dict, Any, Optional
from decision_system import DecisionEngine, OllamaClient
from trading212_client import Trading212Client, load_api_key_from_env
from order_executor import OrderExecutor, ExecutionResult
from config import Config


class TradingSystem:
    """
    Main trading system that orchestrates:
    1. Market analysis and decision making (Ollama)
    2. Order execution (Trading 212 API)
    3. Trade logging and risk management
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        ollama_model: Optional[str] = None,
        is_demo: bool = True,
    ):
        """
        Initialize the trading system.

        Args:
            api_key: Trading 212 API key (uses env var if not provided)
            api_secret: Trading 212 API secret (uses env var if not provided)
            ollama_model: Ollama model to use for decisions
            is_demo: Use demo/practice account (default: True)
        """
        # Load API key from env if not provided
        if not api_key:
            api_key = load_api_key_from_env()
        if not api_secret:
            api_secret = Config.TRADING212_API_SECRET

        # Initialize components.
        # Wire the configured temperature/max-tokens into the decision client —
        # previously these .env settings were ignored and the client's own
        # defaults were used. A 512-token floor guards against the structured
        # decision JSON being truncated on a low max-tokens setting.
        self.ollama_client = OllamaClient(
            model_name=ollama_model,
            temperature=Config.OLLAMA_TEMPERATURE,
            max_tokens=max(512, Config.OLLAMA_MAX_TOKENS),
        )
        self.decision_engine = DecisionEngine(self.ollama_client)
        self.trading_client = Trading212Client(api_key, api_secret=api_secret, is_demo=is_demo)
        self.executor = OrderExecutor(self.trading_client)
        
        self.is_demo = is_demo
        self.trade_log = []

    def decide(self, symbol: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """LLM decision only — READ-ONLY, no order placement. Safe to run in
        parallel across symbols (the LLM call is the slow part)."""
        question = (
            f"Based on this daily-bar context, should the swing trading system "
            f"BUY, SELL, or HOLD {symbol}? "
            f"If BUY or SELL, provide exact stop_loss_price and take_profit_price."
        )
        return self.decision_engine.make_decision(context, question)

    def execute_prepared(
        self,
        symbol: str,
        context: Dict[str, Any],
        decision: Dict[str, Any],
        quantity: float = 1,
        account_value: float = 0,
        free_funds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Place the order for an already-made decision. MUTATES cash/positions —
        must be called serially (single-threaded) so position sizing stays
        cash-aware. Pass FRESH free_funds (re-fetched at execution time)."""
        execution = self.executor.execute_decision(
            decision,
            symbol,
            quantity,
            account_value=account_value,
            context=context,
            free_funds=free_funds,
        )

        trade_record = {
            "symbol":   symbol,
            "decision": decision,
            "execution": {
                "success":    execution.success,
                "action":     execution.action,
                "quantity":   execution.quantity,
                "message":    execution.message,
                "order_id":   execution.order_id,
                "error":      execution.error,
                "confidence": execution.confidence,
                "price":      execution.price,
            },
        }
        self.trade_log.append(trade_record)

        return {
            "symbol":    symbol,
            "context":   context,
            "decision":  decision,
            "execution": trade_record["execution"],
        }

    def analyze_and_trade(
        self,
        symbol: str,
        context: Dict[str, Any],
        quantity: float = 1,
        account_value: float = 0,
        free_funds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Decide then execute in one call (back-compat / single-symbol use)."""
        decision = self.decide(symbol, context)
        return self.execute_prepared(
            symbol, context, decision,
            quantity=quantity, account_value=account_value, free_funds=free_funds,
        )

    def get_account_status(self) -> Dict[str, Any]:
        """Get current account status and positions."""
        return self.executor.get_account_summary()

    def get_trade_history(self) -> list:
        """Get history of all executed trades."""
        return self.trade_log

    def get_open_positions(self) -> list:
        """Get all open positions."""
        positions = self.trading_client.get_positions()
        return [
            {
                "symbol": p.instrument_code,
                "quantity": p.quantity,
                "average_price": p.average_price,
                "current_price": p.current_price,
                "value": p.value,
                "profit_loss": p.profit_loss,
            }
            for p in positions
        ]

    def get_open_orders(self) -> list:
        """Get all open orders."""
        orders = self.trading_client.get_orders()
        return [
            {
                "order_id": o.order_id,
                "symbol": o.instrument_code,
                "side": o.side,
                "quantity": o.quantity,
                "price": o.price,
                "status": o.status,
            }
            for o in orders
        ]

    def check_risk_exits(self) -> list:
        """Check all tracked positions for stop-loss / take-profit hits and execute exits."""
        return self.executor.check_and_execute_exits()

    def get_tracked_positions(self) -> dict:
        """Return current stop-loss / take-profit tracking state."""
        return self.executor.get_tracked_positions()

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        try:
            self.trading_client.cancel_order(order_id)
            return True
        except Exception as e:
            print(f"Failed to cancel order: {e}")
            return False

    def print_status(self) -> None:
        """Print current account and position status."""
        print("\n" + "=" * 60)
        print("TRADING SYSTEM STATUS")
        print("=" * 60)
        
        account = self.get_account_status()
        if "error" in account:
            print(f"Error fetching account status: {account['error']}")
            return
        
        print(f"Account ID: {account.get('account_id', 'N/A')}")
        print(f"Mode: {'DEMO/PRACTICE' if self.is_demo else 'LIVE'}")
        print(f"Cash: ${account.get('cash', 0):.2f}")
        print(f"Portfolio Value: ${account.get('portfolio_value', 0):.2f}")
        print(f"Free Funds: ${account.get('free_funds', 0):.2f}")
        
        positions = account.get("positions", [])
        if positions:
            print(f"\nOpen Positions ({len(positions)}):")
            for pos in positions:
                print(f"  {pos['symbol']}: {pos['quantity']} shares @ ${pos['current_price']:.2f}")
                print(f"    Value: ${pos['value']:.2f}, P/L: ${pos['profit_loss']:.2f}")
        else:
            print("\nNo open positions")
        
        print("=" * 60 + "\n")
