from typing import Dict, Any, Optional
from dataclasses import dataclass
from trading212_client import Trading212Client, OrderSide, OrderType


@dataclass
class ExecutionResult:
    """Result of an order execution"""
    success: bool
    symbol: str
    action: str
    quantity: float
    message: str
    order_id: Optional[str] = None
    error: Optional[str] = None


class OrderExecutor:
    """
    Executes trading decisions using the Trading 212 API.
    Translates decision engine outputs into actual trades.
    """

    def __init__(self, trading_client: Trading212Client):
        """
        Initialize the order executor.
        
        Args:
            trading_client: Configured Trading212Client instance
        """
        self.client = trading_client
        self.trade_history = []

    def execute_decision(
        self,
        decision: Dict[str, Any],
        symbol: str,
        quantity: float = 1,
    ) -> ExecutionResult:
        """
        Execute a trade based on a decision engine output.
        
        Args:
            decision: Output from DecisionEngine.make_decision()
            symbol: Stock symbol to trade
            quantity: Number of shares to trade
            
        Returns:
            ExecutionResult with trade details
        """
        try:
            # Extract the decision action
            action = self._extract_action(decision)
            
            if action == "BUY":
                return self._execute_buy(symbol, quantity)
            elif action == "SELL":
                return self._execute_sell(symbol, quantity)
            elif action == "HOLD":
                return ExecutionResult(
                    success=True,
                    symbol=symbol,
                    action="HOLD",
                    quantity=0,
                    message="Holding position as per decision",
                )
            else:
                return ExecutionResult(
                    success=False,
                    symbol=symbol,
                    action=action,
                    quantity=quantity,
                    message=f"Unknown action: {action}",
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            return ExecutionResult(
                success=False,
                symbol=symbol,
                action="UNKNOWN",
                quantity=quantity,
                message=f"Execution failed: {str(e)}",
                error=str(e),
            )

    def _extract_action(self, decision: Dict[str, Any]) -> str:
        """Extract the buy/sell/hold action from decision output."""
        # Try different common formats from LLM responses
        if "action" in decision:
            return decision["action"].upper()
        
        if "decision" in decision:
            action = str(decision["decision"]).upper()
            for word in ["BUY", "SELL", "HOLD"]:
                if word in action:
                    return word
        
        if "recommendation" in decision:
            action = str(decision["recommendation"]).upper()
            for word in ["BUY", "SELL", "HOLD"]:
                if word in action:
                    return word
        
        # Default to HOLD if unclear
        return "HOLD"

    def _execute_buy(self, symbol: str, quantity: float) -> ExecutionResult:
        """Execute a BUY order."""
        try:
            # Check available funds
            account = self.client.get_account_info()
            
            if account.free_funds <= 0:
                return ExecutionResult(
                    success=False,
                    symbol=symbol,
                    action="BUY",
                    quantity=quantity,
                    message="Insufficient funds",
                    error="Insufficient free funds for trade",
                )
            
            # Place market buy order
            response = self.client.place_order(
                symbol=symbol,
                quantity=quantity,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
            )
            
            order_id = response.get("id") or response.get("orderId")
            message = f"BUY order placed: {quantity} shares of {symbol}"
            
            result = ExecutionResult(
                success=True,
                symbol=symbol,
                action="BUY",
                quantity=quantity,
                message=message,
                order_id=order_id,
            )
            
            self.trade_history.append(result)
            return result
        except Exception as e:
            return ExecutionResult(
                success=False,
                symbol=symbol,
                action="BUY",
                quantity=quantity,
                message=f"BUY order failed: {str(e)}",
                error=str(e),
            )

    def _execute_sell(self, symbol: str, quantity: float) -> ExecutionResult:
        """Execute a SELL order."""
        try:
            # Check if we have the position
            positions = self.client.get_positions()
            position = next(
                (p for p in positions if p.instrument_code == symbol),
                None,
            )
            
            if not position or position.quantity < quantity:
                available = position.quantity if position else 0
                return ExecutionResult(
                    success=False,
                    symbol=symbol,
                    action="SELL",
                    quantity=quantity,
                    message=f"Insufficient position. Available: {available}",
                    error=f"Only {available} shares available",
                )
            
            # Place market sell order
            response = self.client.place_order(
                symbol=symbol,
                quantity=quantity,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
            )
            
            order_id = response.get("id") or response.get("orderId")
            message = f"SELL order placed: {quantity} shares of {symbol}"
            
            result = ExecutionResult(
                success=True,
                symbol=symbol,
                action="SELL",
                quantity=quantity,
                message=message,
                order_id=order_id,
            )
            
            self.trade_history.append(result)
            return result
        except Exception as e:
            return ExecutionResult(
                success=False,
                symbol=symbol,
                action="SELL",
                quantity=quantity,
                message=f"SELL order failed: {str(e)}",
                error=str(e),
            )

    def get_account_summary(self) -> Dict[str, Any]:
        """Get current account summary."""
        try:
            account = self.client.get_account_info()
            positions = self.client.get_positions()
            
            return {
                "account_id": account.account_id,
                "cash": account.cash,
                "portfolio_value": account.portfolio_value,
                "free_funds": account.free_funds,
                "positions_count": len(positions),
                "positions": [
                    {
                        "symbol": p.instrument_code,
                        "quantity": p.quantity,
                        "current_price": p.current_price,
                        "value": p.value,
                        "profit_loss": p.profit_loss,
                    }
                    for p in positions
                ],
            }
        except Exception as e:
            return {"error": str(e)}

    def get_trade_history(self) -> list:
        """Get history of executed trades."""
        return self.trade_history
