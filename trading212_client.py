import os
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class OrderSide(Enum):
    """Order direction: BUY or SELL"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type options"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass
class Account:
    """Represents a Trading 212 account"""
    account_id: str
    cash: float
    portfolio_value: float
    free_funds: float


@dataclass
class Position:
    """Represents an open position"""
    instrument_code: str
    quantity: float
    average_price: float
    current_price: float
    value: float
    profit_loss: float


@dataclass
class Order:
    """Represents an executed order"""
    order_id: str
    instrument_code: str
    side: str
    quantity: float
    price: float
    status: str


class Trading212Client:
    """
    Client for Trading 212 API integration.
    Supports both live and practice/demo accounts.
    """

    BASE_URL = "https://api.trading212.com/v0"
    DEMO_BASE_URL = "https://demo.trading212.com/api/v0"

    def __init__(self, api_key: str, is_demo: bool = True):
        """
        Initialize the Trading 212 client.
        
        Args:
            api_key: Your Trading 212 API key
            is_demo: Whether to use demo/practice account (default: True)
        """
        self.api_key = api_key
        self.is_demo = is_demo
        self.base_url = self.DEMO_BASE_URL if is_demo else self.BASE_URL
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an API request to Trading 212.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint path
            data: Request body data
            
        Returns:
            Response JSON as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")

    def get_account_info(self) -> Account:
        """Get current account information."""
        data = self._make_request("GET", "/account")
        return Account(
            account_id=data.get("accountId"),
            cash=data.get("cash", 0),
            portfolio_value=data.get("portfolioValue", 0),
            free_funds=data.get("freeFunds", 0),
        )

    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        data = self._make_request("GET", "/positions")
        positions = []
        
        if isinstance(data, dict) and "positions" in data:
            for pos in data["positions"]:
                positions.append(
                    Position(
                        instrument_code=pos.get("instrumentCode"),
                        quantity=pos.get("quantity", 0),
                        average_price=pos.get("averagePrice", 0),
                        current_price=pos.get("currentPrice", 0),
                        value=pos.get("value", 0),
                        profit_loss=pos.get("profitLoss", 0),
                    )
                )
        elif isinstance(data, list):
            for pos in data:
                positions.append(
                    Position(
                        instrument_code=pos.get("instrumentCode"),
                        quantity=pos.get("quantity", 0),
                        average_price=pos.get("averagePrice", 0),
                        current_price=pos.get("currentPrice", 0),
                        value=pos.get("value", 0),
                        profit_loss=pos.get("profitLoss", 0),
                    )
                )
        
        return positions

    def get_orders(self) -> List[Order]:
        """Get all open orders."""
        data = self._make_request("GET", "/orders")
        orders = []
        
        if isinstance(data, dict) and "orders" in data:
            orders_list = data["orders"]
        elif isinstance(data, list):
            orders_list = data
        else:
            return orders
        
        for order in orders_list:
            orders.append(
                Order(
                    order_id=order.get("id"),
                    instrument_code=order.get("instrumentCode"),
                    side=order.get("side"),
                    quantity=order.get("quantity", 0),
                    price=order.get("price", 0),
                    status=order.get("status"),
                )
            )
        
        return orders

    def place_order(
        self,
        symbol: str,
        quantity: float,
        side: OrderSide,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Place a new order.
        
        Args:
            symbol: Instrument symbol (e.g., "AAPL")
            quantity: Number of shares to trade
            side: OrderSide.BUY or OrderSide.SELL
            order_type: Type of order (MARKET, LIMIT, STOP)
            limit_price: Price for LIMIT orders
            stop_price: Price for STOP orders
            
        Returns:
            Order response from API
        """
        order_data = {
            "instrumentCode": symbol,
            "quantity": quantity,
            "side": side.value,
            "type": order_type.value,
        }
        
        if order_type == OrderType.LIMIT and limit_price:
            order_data["limitPrice"] = limit_price
        
        if order_type == OrderType.STOP and stop_price:
            order_data["stopPrice"] = stop_price
        
        return self._make_request("POST", "/orders", order_data)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an open order."""
        return self._make_request("DELETE", f"/orders/{order_id}")

    def get_instrument_details(self, symbol: str) -> Dict[str, Any]:
        """Get details about an instrument."""
        return self._make_request("GET", f"/instruments/{symbol}")

    def search_instruments(self, query: str) -> List[Dict[str, Any]]:
        """Search for instruments by name or symbol."""
        data = self._make_request("GET", f"/instruments/search?query={query}")
        return data.get("results", []) if isinstance(data, dict) else data or []


# Convenience function to load API key from environment
def load_api_key_from_env(env_var: str = "TRADING212_API_KEY") -> str:
    """Load Trading 212 API key from environment variable."""
    api_key = os.getenv(env_var)
    if not api_key:
        raise ValueError(
            f"API key not found. Set the {env_var} environment variable."
        )
    return api_key
